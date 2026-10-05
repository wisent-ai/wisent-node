//! Module parsing and traversal of the exported dependency graph.

use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::rc::Rc;

use super::declarations::{parse_decl, parse_specifiers, Decl, Keyword};
use super::lexer::{at, lex, match_brackets, statement_end, Kind, Token};

/// Extensions tried when resolving a relative import, in preference order: a
/// declaration file describes the published shape best, a source file is what
/// a working tree has, the emitted JavaScript is the last thing worth reading.
const CANDIDATE_SUFFIXES: [&str; 9] = [".d.ts", ".ts", ".tsx", ".d.mts", ".mts", ".js", ".mjs", ".cjs", ".jsx"];

/// Exported name -> its declaration, `None` when it carries no members we can read.
pub type Table = BTreeMap<String, Option<Rc<Decl>>>;

#[derive(Default)]
struct Module {
    path: PathBuf,
    decls: HashMap<String, Rc<Decl>>,
    local_exports: Vec<(String, String)>,
    reexports: Vec<(String, String, String)>,
    star_reexports: Vec<String>,
    imports: HashMap<String, (String, String)>,
    default: Option<Rc<Decl>>,
    has_default: bool,
}

/// Where a module specifier leads.
pub enum Target {
    File(PathBuf),
    Package,
    Lost,
}

fn expect_spec(tokens: &[Token], cursor: usize, origin: &str) -> Result<String, String> {
    match tokens.get(cursor) {
        Some(token) if token.kind == Kind::Str => Ok(token.value.clone()),
        _ => Err(format!("{origin}: `from` without a module specifier")),
    }
}

fn skip_semicolon(tokens: &[Token], after: usize) -> usize {
    if tokens.get(after).is_some_and(|token| token.is_punct(";")) { after + 1 } else { after }
}

fn parse_export(tokens: &[Token], partner: &HashMap<usize, usize>, index: usize, module: &mut Module, origin: &str) -> Result<usize, String> {
    let size = tokens.len();
    let mut cursor = index + 1;
    while cursor < size && tokens[cursor].is_name("declare") {
        cursor += 1;
    }
    let token = tokens.get(cursor).ok_or_else(|| format!("{origin}: `export` at end of file"))?;
    if token.is_punct("{") {
        let pairs = parse_specifiers(tokens, partner, cursor);
        let mut after = partner[&cursor] + 1;
        let mut spec = None;
        if tokens.get(after).is_some_and(|token| token.is_name("from")) {
            spec = Some(expect_spec(tokens, after + 1, origin)?);
            after += 2;
        }
        for (exported, source) in pairs {
            match &spec {
                None => module.local_exports.push((exported, source)),
                Some(spec) => module.reexports.push((exported, source, spec.clone())),
            }
        }
        return Ok(skip_semicolon(tokens, after));
    }
    if token.is_punct("*") {
        let mut after = cursor + 1;
        let mut alias = None;
        if tokens.get(after).is_some_and(|token| token.is_name("as")) {
            alias = tokens.get(after + 1).map(|token| token.value.clone());
            after += 2;
        }
        if !tokens.get(after).is_some_and(|token| token.is_name("from")) {
            return Err(format!("{origin}: `export *` without `from`{}", at(token.line)));
        }
        let spec = expect_spec(tokens, after + 1, origin)?;
        match alias {
            None => module.star_reexports.push(spec),
            Some(alias) => module.reexports.push((alias.clone(), alias, spec)),
        }
        return Ok(skip_semicolon(tokens, after + 2));
    }
    if token.is_name("default") {
        module.has_default = true;
        let inner = cursor + 1;
        if tokens.get(inner).and_then(Keyword::of).is_some() {
            let (decl, after) = parse_decl(tokens, partner, inner, origin)?;
            module.default = decl.map(Rc::new);
            return Ok(after);
        }
        return Ok(statement_end(tokens, partner, inner, true).0);
    }
    if Keyword::of(token).is_some() {
        let (decl, after) = parse_decl(tokens, partner, cursor, origin)?;
        if let Some(decl) = decl {
            let name = decl.name.clone();
            module.decls.insert(name.clone(), Rc::new(decl));
            module.local_exports.push((name.clone(), name));
        }
        return Ok(after);
    }
    Err(format!("{origin}: unrecognised export form `export {}`{}", token.value, at(token.line)))
}

fn parse_import(tokens: &[Token], partner: &HashMap<usize, usize>, index: usize, module: &mut Module, origin: &str) -> Result<usize, String> {
    let size = tokens.len();
    let cursor = index + 1;
    if tokens.get(cursor).is_some_and(|token| token.kind == Kind::Str) {
        return Ok(cursor + 1);
    }
    let mut scan = cursor;
    let mut braces = Vec::new();
    while scan < size {
        let token = &tokens[scan];
        if token.is_punct("{") {
            braces.push(scan);
            scan = partner[&scan] + 1;
            continue;
        }
        if token.is_name("from") {
            let spec = expect_spec(tokens, scan + 1, origin)?;
            for brace in &braces {
                for (exported, source) in parse_specifiers(tokens, partner, *brace) {
                    module.imports.insert(exported, (spec.clone(), source));
                }
            }
            return Ok(skip_semicolon(tokens, scan + 2));
        }
        if token.is_punct(";") {
            return Ok(scan + 1);
        }
        scan += 1;
    }
    Ok(size)
}

fn parse_module(path: &Path) -> Result<Module, String> {
    let origin = path.display().to_string();
    let text = std::fs::read_to_string(path).map_err(|error| format!("{origin}: cannot be read: {error}"))?;
    let tokens = lex(&text, &origin)?;
    let partner = match_brackets(&tokens, &origin)?;
    let mut module = Module { path: path.to_path_buf(), ..Module::default() };
    let mut index = 0;
    while index < tokens.len() {
        let token = &tokens[index];
        index = if token.is_opener() {
            partner[&index] + 1
        } else if token.is_name("export") {
            parse_export(&tokens, &partner, index, &mut module, &origin)?
        } else if token.is_name("import") {
            parse_import(&tokens, &partner, index, &mut module, &origin)?
        } else if Keyword::of(token).is_some() {
            let (decl, after) = parse_decl(&tokens, &partner, index, &origin)?;
            if let Some(decl) = decl {
                module.decls.insert(decl.name.clone(), Rc::new(decl));
            }
            after
        } else {
            index + 1
        };
    }
    Ok(module)
}

/// A file for a relative import, `Package` for a package name, `Lost` when nothing matches.
pub fn resolve_spec(from: &Path, spec: &str) -> Target {
    if !spec.starts_with('.') {
        return Target::Package;
    }
    let base = from.parent().unwrap_or(Path::new("")).join(spec);
    let base = base.canonicalize().unwrap_or(base);
    for suffix in CANDIDATE_SUFFIXES {
        let probe = PathBuf::from(format!("{}{suffix}", base.display()));
        if probe.is_file() {
            return Target::File(probe);
        }
    }
    if base.is_file() {
        return Target::File(base);
    }
    for suffix in CANDIDATE_SUFFIXES {
        let probe = base.join(format!("index{suffix}"));
        if probe.is_file() {
            return Target::File(probe);
        }
    }
    Target::Lost
}

pub struct Reader {
    tolerant: bool,
    cache: HashMap<PathBuf, Rc<Module>>,
    pub skipped: Vec<String>,
}

impl Reader {
    pub fn new(tolerant: bool) -> Self {
        Self { tolerant, cache: HashMap::new(), skipped: Vec::new() }
    }

    fn module(&mut self, path: &Path) -> Result<Rc<Module>, String> {
        if let Some(module) = self.cache.get(path) {
            return Ok(Rc::clone(module));
        }
        let module = Rc::new(parse_module(path)?);
        self.cache.insert(path.to_path_buf(), Rc::clone(&module));
        Ok(module)
    }

    /// Exported names of `path`, following relative re-exports.
    pub fn exports_of(&mut self, path: &Path, stack: &[PathBuf]) -> Result<Table, String> {
        if stack.iter().any(|seen| seen == path) {
            return Err(format!("{}: circular re-export", path.display()));
        }
        let mut stack = stack.to_vec();
        stack.push(path.to_path_buf());
        let module = self.module(path)?;
        let mut found = Table::new();
        for spec in &module.star_reexports {
            if let Some(table) = self.follow(&module, spec, &stack)? {
                found.extend(table);
            }
        }
        for (exported, source) in &module.local_exports {
            let mut decl = module.decls.get(source).cloned();
            if decl.is_none() {
                if let Some((spec, original)) = module.imports.get(source) {
                    decl = self.follow(&module, spec, &stack)?.and_then(|table| table.get(original).cloned().flatten());
                }
            }
            found.insert(exported.clone(), decl);
        }
        for (exported, source, spec) in &module.reexports {
            let Some(table) = self.follow(&module, spec, &stack)? else {
                found.insert(exported.clone(), None);
                continue;
            };
            let decl = table.get(source).ok_or_else(|| {
                format!("{}: re-exports `{source}` from '{spec}', which does not export it", path.display())
            })?;
            found.insert(exported.clone(), decl.clone());
        }
        if module.has_default {
            found.insert("default".to_string(), module.default.clone());
        }
        Ok(found)
    }

    /// The table a specifier leads to; `None` for a package or a skipped module.
    fn follow(&mut self, module: &Module, spec: &str, stack: &[PathBuf]) -> Result<Option<Table>, String> {
        match resolve_spec(&module.path, spec) {
            Target::Package => {
                eprintln!("note: `{spec}` is a package, not a file, so the names it contributes are recorded without members");
                Ok(None)
            }
            Target::Lost => {
                let message = format!("{}: relative import '{spec}' does not resolve", module.path.display());
                if !self.tolerant {
                    return Err(message);
                }
                self.skipped.push(message);
                Ok(None)
            }
            Target::File(target) => match self.exports_of(&target, stack) {
                Ok(table) => Ok(Some(table)),
                Err(error) if self.tolerant => {
                    self.skipped.push(error);
                    Ok(None)
                }
                Err(error) => Err(error),
            },
        }
    }
}
