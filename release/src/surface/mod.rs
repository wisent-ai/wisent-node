//! The public surface of the npm distribution declared by `package.json`:
//!
//! - `export:<name>` — every name reachable from the package entry point
//!   (`exports`/`types`/`main`); the default export is `export:default`;
//! - `member:<Exported>.<path>` — public members of every exported class,
//!   interface, type alias and enum, nested object types as dotted paths;
//! - `bin:<command>` — every command in the `bin` map.
//!
//! Private, protected, `#`- and `_`-prefixed members and `constructor` are
//! left out, as is every module not reachable from the entry point. The same
//! reader runs against an unpacked published tarball and a working tree,
//! without `tsc`, `npm` or `node`. An unreadable module is a refusal, never a
//! shorter surface; `tolerant` skips (and names) them only when recovering an
//! artifact that is already published.

mod declarations;
mod lexer;
mod modules;

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

use serde_json::Value;

use modules::{resolve_spec, Reader, Target};

/// A built directory and the source directory `npm publish` rebuilds it from.
const BUILD_DIRS: [(&str, &str); 4] = [("dist/", "src/"), ("lib/", "src/"), ("build/", "src/"), ("out/", "src/")];
/// A built file suffix and the source suffix it is emitted from.
const BUILT_SUFFIXES: [(&str, &str); 5] = [(".d.ts", ".ts"), (".d.mts", ".ts"), (".js", ".ts"), (".mjs", ".ts"), (".cjs", ".ts")];

/// Whether an `exports` condition names type declarations (npm's `types`, or its older spelling).
fn is_types_condition(key: &str) -> bool {
    key == "types" || key == "typings"
}

/// Every file string the `exports` map points at, types-first.
fn exports_field_candidates(exports: &Value) -> Vec<String> {
    let subtree = match exports {
        Value::Object(map) if map.contains_key(".") => Some(&map["."]),
        Value::Object(map) if map.keys().any(|key| key.starts_with('.')) => None,
        other => Some(other),
    };
    let mut ordered: Vec<(bool, String)> = Vec::new();
    fn visit(node: &Value, types_first: bool, ordered: &mut Vec<(bool, String)>) {
        match node {
            Value::String(path) => ordered.push((types_first, path.clone())),
            Value::Object(map) => {
                for (key, value) in map {
                    visit(value, types_first || is_types_condition(key), ordered);
                }
            }
            _ => {}
        }
    }
    if let Some(subtree) = subtree {
        visit(subtree, false, &mut ordered);
    }
    ordered.sort_by_key(|(types_first, _)| !types_first);
    ordered.into_iter().map(|(_, path)| path).collect()
}

fn source_twin(relative: &str) -> String {
    let mut text = relative.to_string();
    for (built, source) in BUILD_DIRS {
        if let Some(rest) = text.strip_prefix(built) {
            text = format!("{source}{rest}");
            break;
        }
        if let Some(rest) = text.strip_prefix(&format!("./{built}")) {
            text = format!("./{source}{rest}");
            break;
        }
    }
    for (suffix, replacement) in BUILT_SUFFIXES {
        if let Some(stem) = text.strip_suffix(suffix) {
            return format!("{stem}{replacement}");
        }
    }
    text
}

/// The manifest's entry-point candidates: `exports` (types first), then the
/// `types` field, its older `typings` spelling, then `main`.
fn entry_candidates(manifest: &Value) -> Vec<String> {
    let mut candidates = manifest.get("exports").map(exports_field_candidates).unwrap_or_default();
    let field = |key: &str| manifest.get(key).and_then(Value::as_str).map(str::to_string);
    candidates.extend(field("types"));
    candidates.extend(field("typings"));
    candidates.extend(field("main"));
    candidates
}

/// The file the entry point's names are read from: the source twin first,
/// because `prepare` rebuilds `dist/` from `src/` on publish, so `src/` decides
/// what a consumer will hold; an unpacked tarball ships no `src/`.
fn pick_entry(root: &Path, manifest: &Value) -> Result<PathBuf, String> {
    let candidates = entry_candidates(manifest);
    if candidates.is_empty() {
        return Err(format!(
            "{}/package.json declares no `exports`, `types` or `main`, so the package has no entry point and no importable surface",
            root.display()
        ));
    }
    let mut tried = Vec::new();
    for candidate in &candidates {
        for relative in [source_twin(candidate), candidate.clone()] {
            let joined = root.join(&relative);
            let probe = joined.canonicalize().unwrap_or(joined);
            tried.push(probe.display().to_string());
            if probe.is_file() {
                return Ok(probe);
            }
            let name = probe.file_name().map(|name| name.to_string_lossy().into_owned()).unwrap_or_default();
            if let Target::File(resolved) = resolve_spec(&probe, &format!("./{name}")) {
                return Ok(resolved);
            }
        }
    }
    Err(format!("no entry point exists on disk; tried: {}", tried.join(", ")))
}

fn bin_names(manifest: &Value) -> Result<Vec<String>, String> {
    match manifest.get("bin") {
        Some(Value::Object(map)) => Ok(map.keys().cloned().collect()),
        Some(Value::String(_)) => {
            let name = manifest.get("name").and_then(Value::as_str).unwrap_or_default();
            if name.is_empty() {
                return Err("package.json has a string `bin` but no `name`, so the installed command name is undecidable".to_string());
            }
            Ok(vec![name.rsplit('/').next().unwrap_or(name).to_string()])
        }
        _ => Ok(Vec::new()),
    }
}

pub fn read_manifest(root: &Path) -> Result<Value, String> {
    let path = root.join("package.json");
    if !path.is_file() {
        return Err(format!("{} does not exist, so there is no distribution to read", path.display()));
    }
    let text = std::fs::read_to_string(&path).map_err(|error| format!("{}: {error}", path.display()))?;
    serde_json::from_str(&text).map_err(|error| format!("{}: {error}", path.display()))
}

/// The sorted surface of the distribution at `root`.
pub fn compute(root: &Path, tolerant: bool) -> Result<Vec<String>, String> {
    let manifest = read_manifest(root)?;
    let entry = pick_entry(root, &manifest)?;
    let mut reader = Reader::new(tolerant);
    let table = reader.exports_of(&entry, &[])?;
    let mut names = BTreeSet::new();
    for (exported, decl) in &table {
        names.insert(format!("export:{exported}"));
        for member in decl.iter().flat_map(|decl| decl.members.iter()) {
            names.insert(format!("member:{exported}.{member}"));
        }
    }
    for command in bin_names(&manifest)? {
        names.insert(format!("bin:{command}"));
    }
    if names.is_empty() {
        return Err(format!("{} exports nothing; an empty surface would make every later comparison vacuous", entry.display()));
    }
    for message in &reader.skipped {
        eprintln!("skipped: {message}");
    }
    Ok(names.into_iter().collect())
}
