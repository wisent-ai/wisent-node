//! `released-surface.json`: the surface of the version actually published,
//! its `source` opening with a marker naming the artifact it came from:
//!
//! - `npm-tarball:<registry path>` — the tarball npm serves (`dist.tarball`,
//!   taken, never assembled);
//! - `git-archive:<tag>` — a tag at `origin`, reproduced with `git archive`;
//! - `head:<sha>` — the working revision, the last resort.
//!
//! A tier that exists but cannot be recovered is a refusal, never a silent
//! drop to a lower one. The latest version is npm's `dist-tags.latest`, never
//! the version package.json declares.

mod registry;
mod repository;

use std::path::Path;

use serde_json::{json, Value};
use sha1::{Digest, Sha1};

use crate::surface::{compute, read_manifest};
use registry::Answer;

const TIER_NPM_TARBALL: &str = "npm-tarball";
const TIER_GIT_ARCHIVE: &str = "git-archive";
const TIER_HEAD: &str = "head";

/// Whether a marker's tier claims a registry (`registry`) or not (`none`).
pub fn marker_claim(marker: &str) -> &'static str {
    if marker.split(':').next() == Some(TIER_NPM_TARBALL) { "registry" } else { "none" }
}

/// Ask npm about `name` through the subject's own code path: `published <version> <path>`,
/// `absent <name>`, or `unproven <name>: <why>` (a refusal).
pub fn report_probe(name: &str) -> Result<String, String> {
    match registry::probe(name) {
        Answer::Published(document) => {
            let (version, tarball, _) = registry::latest_release(&document, name)?;
            let (path, _) = registry::tarball_path(&tarball)?;
            Ok(format!("published {version} {path}"))
        }
        Answer::Absent => Ok(format!("absent {name}")),
        Answer::Unproven(why) => Err(format!("unproven {name}: {why}")),
    }
}

fn fresh(scratch: &Path) -> Result<(), String> {
    if scratch.exists() {
        std::fs::remove_dir_all(scratch).map_err(|error| format!("{}: {error}", scratch.display()))?;
    }
    std::fs::create_dir_all(scratch).map_err(|error| format!("{}: {error}", scratch.display()))
}

fn cleaned<T>(scratch: &Path, result: Result<T, String>) -> Result<T, String> {
    let removed = std::fs::remove_dir_all(scratch);
    let value = result?;
    removed.map_err(|error| format!("{} was not removed: {error}", scratch.display()))?;
    Ok(value)
}

/// The baseline document of the best tier reachable now; `scratch` holds unpacked artifacts.
pub fn build(root: &Path, tolerant: bool, scratch: &Path) -> Result<Value, String> {
    let manifest = read_manifest(root)?;
    let name = manifest["name"].as_str().map(str::trim).filter(|name| !name.is_empty()).ok_or(
        "package.json declares no `name`, so there is no coordinate to ask npm about and no absence anybody could prove",
    )?;
    let remote = repository::origin_url(root)?;
    let github = repository::github_repository(remote.as_deref());

    let answer = registry::probe(name);
    if let Answer::Unproven(why) = &answer {
        return Err(format!("npm's answer about {name} is unproven, so neither its presence nor its absence may be relied on: {why}"));
    }
    if let Some(alias) = repository::scoped_spelling(name, github.as_deref()) {
        match registry::probe(&alias) {
            Answer::Unproven(why) => {
                return Err(format!("npm answered about {name} but not about {alias}, so a second coordinate cannot be ruled out: {why}"));
            }
            Answer::Published(_) => {
                return Err(format!(
                    "npm serves both {name} and {alias}, so no coordinate is canonical for this tree and a human has to choose which one the gate guards"
                ));
            }
            Answer::Absent => {}
        }
    }

    if let Answer::Published(document) = answer {
        let (version, tarball, shasum) = registry::latest_release(&document, name)?;
        let (path, host) = registry::tarball_path(&tarball)?;
        let payload = registry::download(&tarball)?;
        if let Some(expected) = &shasum {
            let got = hex::encode(Sha1::digest(&payload));
            if &got != expected {
                return Err(format!("the tarball npm served for {name} {version} hashes to {got}, not the {expected} the registry advertises"));
            }
        }
        fresh(scratch)?;
        let surface = cleaned(scratch, registry::unpack(&payload, scratch).and_then(|tree| compute(&tree, tolerant)))?;
        let checksum = shasum.map(|sum| format!(" (sha1 {sum})")).unwrap_or_default();
        let prose = format!("recovered from the tarball {host} serves for {name} {version}{checksum}; read statically from the published declarations, never built");
        return Ok(json!({ "source": format!("{TIER_NPM_TARBALL}:{path} {prose}"), "surface": surface, "version": version }));
    }

    if let Some(blocked) = repository::blocking_github_release(remote.as_deref(), github.as_deref())? {
        return Err(format!(
            "npm serves nothing for {name} but the GitHub Release {blocked} carries assets, which outranks the tag and head tiers; recover from that asset instead of filing a lower baseline underneath it"
        ));
    }

    if let Some((tag, version)) = repository::best_tag(root)? {
        fresh(scratch)?;
        let surface = cleaned(scratch, repository::surface_of_tag(&tag, tolerant, root, scratch))?;
        let prose = format!("reproduced with `git archive` from the tag {tag} at origin, whose tree declares {version}; npm serves no {name} today");
        return Ok(json!({ "source": format!("{TIER_GIT_ARCHIVE}:{tag} {prose}"), "surface": surface, "version": version }));
    }

    let declared = manifest["version"].as_str().map(str::trim).filter(|version| !version.is_empty()).ok_or(
        "package.json declares no `version`, and no published artifact supplies one, so the baseline would have nothing to compare against",
    )?;
    let surface = compute(root, tolerant)?;
    let prose = format!(
        "the working revision: npm serves no {name}, origin holds no usable tag, and no GitHub Release carries an asset, so nothing has been published to recover"
    );
    Ok(json!({ "source": format!("{TIER_HEAD}:{} {prose}", repository::head_sha(root)?), "surface": surface, "version": declared }))
}
