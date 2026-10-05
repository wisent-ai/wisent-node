//! What npm serves, read as three states — published, absent, unproven —
//! from the answer's content, never from a transport status: a request that
//! never completed and a package that does not exist must not look alike.

use std::io::Read;
use std::path::{Path, PathBuf};

use serde_json::Value;

const REGISTRY: &str = "https://registry.npmjs.org";
const USER_AGENT: &str = "wisent-node-release baseline";

pub enum Answer {
    Published(Value),
    Absent,
    Unproven(String),
}

fn first_line(text: &str) -> String {
    text.lines().next().unwrap_or_default().trim().to_string()
}

/// `(status, body)`; a request that never completed is `None` with the transport error.
pub fn fetch(url: &str) -> (Option<u16>, String) {
    let request = ureq::get(url).set("User-Agent", USER_AGENT).set("Accept", "application/json");
    match request.call() {
        Ok(response) => {
            let status = response.status();
            (Some(status), response.into_string().unwrap_or_default())
        }
        Err(ureq::Error::Status(status, response)) => (Some(status), response.into_string().unwrap_or_default()),
        Err(ureq::Error::Transport(error)) => (None, error.to_string()),
    }
}

/// npm addresses a scoped package with the sigil kept and the slash encoded.
fn registry_url(name: &str) -> String {
    format!("{REGISTRY}/{}", name.replace('/', "%2f"))
}

pub fn probe(name: &str) -> Answer {
    if name.is_empty() {
        return Answer::Unproven(
            "the package name is empty, and npm's absence answer names nothing, so this lookup would read as proven absence".to_string(),
        );
    }
    let (status, body) = fetch(&registry_url(name));
    if status.is_none() {
        return Answer::Unproven(format!("no request to npm completed: {}", first_line(&body)));
    }
    let Ok(document) = serde_json::from_str::<Value>(&body) else {
        return Answer::Unproven(format!("npm answered with something that is not JSON: {}", first_line(&body)));
    };
    if !document.is_object() {
        return Answer::Unproven(format!("npm answered with {document}"));
    }
    if let Some(served) = document.get("name").and_then(Value::as_str).filter(|served| !served.is_empty()) {
        if served != name {
            return Answer::Unproven(format!(
                "npm answered about '{served}' when asked about '{name}', so the answer is about a different package"
            ));
        }
        return Answer::Published(document);
    }
    let stated = document.get("error").and_then(Value::as_str).unwrap_or_default();
    if stated.to_lowercase().contains("not found") {
        return Answer::Absent;
    }
    Answer::Unproven(format!("npm neither named a package nor stated not-found: {}", first_line(&body)))
}

/// `(version, tarball url, sha1)` of the newest published version.
pub fn latest_release(document: &Value, name: &str) -> Result<(String, String, Option<String>), String> {
    let latest = document["dist-tags"]["latest"]
        .as_str()
        .filter(|latest| !latest.is_empty())
        .ok_or_else(|| format!("npm serves {name} but names no `dist-tags.latest`, so the latest published version is unknown"))?;
    let entry = &document["versions"][latest];
    if !entry.is_object() {
        return Err(format!("npm names {latest} as latest for {name} but serves no metadata for it"));
    }
    let tarball = entry["dist"]["tarball"]
        .as_str()
        .filter(|tarball| !tarball.is_empty())
        .ok_or_else(|| format!("npm serves {name} {latest} with no `dist.tarball`, so there is no artifact to recover"))?;
    let shasum = entry["dist"]["shasum"].as_str().filter(|sum| !sum.is_empty()).map(str::to_string);
    Ok((latest.to_string(), tarball.to_string(), shasum))
}

/// `(registry path, host)` npm addresses the artifact by — taken, never assembled.
pub fn tarball_path(tarball: &str) -> Result<(String, String), String> {
    let refuse = || format!("npm gave a tarball location this script cannot address: {tarball}");
    let rest = tarball.strip_prefix("https://").or_else(|| tarball.strip_prefix("http://")).ok_or_else(refuse)?;
    let (host, path) = rest.split_once('/').ok_or_else(refuse)?;
    if host.is_empty() || path.is_empty() {
        return Err(refuse());
    }
    Ok((path.to_string(), host.to_string()))
}

pub fn download(url: &str) -> Result<Vec<u8>, String> {
    let response = ureq::get(url)
        .set("User-Agent", USER_AGENT)
        .call()
        .map_err(|error| format!("the published tarball {url} could not be fetched: {error}"))?;
    let mut payload = Vec::new();
    response.into_reader().read_to_end(&mut payload).map_err(|error| format!("the published tarball {url} could not be read: {error}"))?;
    Ok(payload)
}

/// Unpack a `.tgz` under `destination` and return the directory of its shallowest `package.json`.
pub fn unpack(payload: &[u8], destination: &Path) -> Result<PathBuf, String> {
    let tree = destination.join("tree");
    std::fs::create_dir_all(&tree).map_err(|error| format!("{}: {error}", tree.display()))?;
    let mut archive = tar::Archive::new(flate2::read::GzDecoder::new(payload));
    for entry in archive.entries().map_err(|error| format!("the tarball does not read: {error}"))? {
        let mut entry = entry.map_err(|error| format!("the tarball does not read: {error}"))?;
        // unpack_in refuses a path that would leave `tree`.
        let inside = entry.unpack_in(&tree).map_err(|error| format!("the tarball does not unpack: {error}"))?;
        if !inside {
            let name = entry.path().map(|path| path.display().to_string()).unwrap_or_default();
            return Err(format!("the tarball contains a path outside itself: {name}"));
        }
    }
    shallowest_manifest(&tree)?.ok_or_else(|| "the published tarball contains no package.json".to_string())
}

fn shallowest_manifest(directory: &Path) -> Result<Option<PathBuf>, String> {
    if directory.join("package.json").is_file() {
        return Ok(Some(directory.to_path_buf()));
    }
    let mut children: Vec<PathBuf> = std::fs::read_dir(directory)
        .map_err(|error| format!("{}: {error}", directory.display()))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.is_dir())
        .collect();
    children.sort();
    let mut best: Option<(usize, PathBuf)> = None;
    for child in children {
        if let Some(found) = shallowest_manifest(&child)? {
            let depth = found.components().count();
            if best.as_ref().map_or(true, |(known, _)| depth < *known) {
                best = Some((depth, found));
            }
        }
    }
    Ok(best.map(|(_, path)| path))
}
