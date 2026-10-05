//! Repository identity, published tags and their recoverable surfaces.

use std::path::Path;
use std::process::Command;

use serde_json::Value;

use super::registry::fetch;
use crate::surface::compute;

fn run(command: &[&str], cwd: Option<&Path>) -> Result<(bool, String, String), String> {
    let (program, arguments) = command.split_first().ok_or("an empty command")?;
    let mut process = Command::new(program);
    process.args(arguments);
    if let Some(cwd) = cwd {
        process.current_dir(cwd);
    }
    let output = process.output().map_err(|error| format!("`{program}` could not start: {error}"))?;
    Ok((output.status.success(), String::from_utf8_lossy(&output.stdout).into_owned(), String::from_utf8_lossy(&output.stderr).into_owned()))
}

fn first_line(text: &str) -> String {
    text.lines().next().unwrap_or_default().trim().to_string()
}

/// Where `origin` points, or `None` when there is no remote to ask.
pub fn origin_url(root: &Path) -> Result<Option<String>, String> {
    let (ok, out, _) = run(&["git", "remote", "get-url", "origin"], Some(root))?;
    Ok(ok.then(|| out.trim().to_string()).filter(|url| !url.is_empty()))
}

/// `owner/name` when `origin` is on GitHub. Taken from `origin`, never from
/// package.json's `repository`, which names a repository that does not exist.
pub fn github_repository(url: Option<&str>) -> Option<String> {
    let url = url?;
    let text = url.strip_prefix("git+").unwrap_or(url);
    let text = text.strip_suffix(".git").unwrap_or(text);
    let (_, tail) = text.split_once("github.com")?;
    let parts: Vec<&str> = tail.trim_start_matches([':', '/']).split('/').filter(|part| !part.is_empty()).collect();
    match parts.as_slice() {
        [owner, name, ..] => Some(format!("{owner}/{name}")),
        _ => None,
    }
}

/// The tag of a GitHub Release carrying assets, which outranks every tier below npm.
pub fn blocking_github_release(url: Option<&str>, repository: Option<&str>) -> Result<Option<String>, String> {
    let Some(url) = url else {
        return Err("this tree has no `origin`, so neither a Release nor a tag can be asked about and no tier below the registry can be trusted".to_string());
    };
    let Some(repository) = repository else {
        eprintln!("note: origin ({url}) is not on GitHub, so there is no GitHub Release tier to outrank a tag here");
        return Ok(None);
    };
    let (status, body) = fetch(&format!("https://api.github.com/repos/{repository}/releases"));
    if status.is_none() {
        return Err(format!("GitHub did not answer about releases of {repository}, so a higher tier cannot be ruled out: {}", first_line(&body)));
    }
    let document: Value = serde_json::from_str(&body)
        .map_err(|_| format!("GitHub answered about releases of {repository} with something that is not JSON: {}", first_line(&body)))?;
    let Some(releases) = document.as_array() else {
        let message = document.get("message").and_then(Value::as_str).map(str::to_string).unwrap_or_else(|| first_line(&body));
        return Err(format!("GitHub refused to list releases of {repository}: {message}"));
    };
    Ok(releases
        .iter()
        .find(|release| release["assets"].as_array().is_some_and(|assets| !assets.is_empty()))
        .map(|release| release["tag_name"].as_str().unwrap_or_default().to_string()))
}

/// Tag names at `origin`; a local listing is not evidence, a fork shares the upstream's objects.
fn origin_tags(root: &Path) -> Result<Vec<String>, String> {
    let (ok, out, err) = run(&["git", "ls-remote", "--tags", "origin"], Some(root))?;
    if !ok {
        return Err(format!("`git ls-remote --tags origin` failed, so whether this distribution was ever tagged is unknown: {}", first_line(&err)));
    }
    let mut names: Vec<String> = out
        .lines()
        .filter_map(|line| line.split_whitespace().nth(1))
        .filter_map(|reference| reference.strip_prefix("refs/tags/"))
        .map(|name| name.strip_suffix("^{}").unwrap_or(name).to_string())
        .collect();
    names.sort();
    names.dedup();
    Ok(names)
}

fn version_in_tag(tag: &str, root: &Path) -> Result<Option<String>, String> {
    let (ok, out, _) = run(&["git", "show", &format!("{tag}:package.json")], Some(root))?;
    if !ok {
        return Ok(None);
    }
    Ok(serde_json::from_str::<Value>(&out).ok().and_then(|manifest| manifest["version"].as_str().map(str::to_string)))
}

/// Whether `candidate` is newer than `incumbent`, as the fleet rule orders versions.
fn is_newer(candidate: &str, incumbent: &str) -> Result<bool, String> {
    let (ok, out, err) = run(&["autoversion", "order", "--older", incumbent, "--newer", candidate, "--json"], None)?;
    if !ok {
        return Err(format!("the rule could not order {incumbent} and {candidate}: {}", first_line(&err)));
    }
    let answer: Value = serde_json::from_str(&out).map_err(|error| format!("autoversion order printed no JSON: {error}"))?;
    Ok(answer["is_newer"] == Value::Bool(true) || answer["is_newer"].as_str() == Some("True"))
}

/// `(tag, version)` of the newest tag whose tree declares the version its name claims.
pub fn best_tag(root: &Path) -> Result<Option<(String, String)>, String> {
    let mut chosen: Option<(String, String)> = None;
    for tag in origin_tags(root)? {
        let claimed = tag.strip_prefix('v').unwrap_or(&tag).to_string();
        let Some(declared) = version_in_tag(&tag, root)? else {
            eprintln!("note: tag {tag} has no readable package.json, so it is skipped");
            continue;
        };
        if declared != claimed {
            eprintln!("note: tag {tag} points at a tree declaring {declared}, so it is skipped rather than filed under {claimed}");
            continue;
        }
        let newer = match &chosen {
            None => true,
            Some((_, incumbent)) => is_newer(&declared, incumbent)?,
        };
        if newer {
            chosen = Some((tag, declared));
        }
    }
    Ok(chosen)
}

/// The surface of `tag`'s tree, reproduced with `git archive` under `scratch`.
pub fn surface_of_tag(tag: &str, tolerant: bool, root: &Path, scratch: &Path) -> Result<Vec<String>, String> {
    let tree = scratch.join("tree");
    std::fs::create_dir_all(&tree).map_err(|error| format!("{}: {error}", tree.display()))?;
    let archive = scratch.join("tag.tar");
    let (ok, _, err) = run(&["git", "archive", "--format=tar", "-o", &archive.display().to_string(), tag], Some(root))?;
    if !ok {
        return Err(format!("`git archive {tag}` failed, so its tree cannot be read: {}", first_line(&err)));
    }
    let file = std::fs::File::open(&archive).map_err(|error| format!("{}: {error}", archive.display()))?;
    tar::Archive::new(file).unpack(&tree).map_err(|error| format!("`git archive {tag}` does not unpack: {error}"))?;
    compute(&tree, tolerant)
}

pub fn head_sha(root: &Path) -> Result<String, String> {
    let (ok, out, err) = run(&["git", "rev-parse", "HEAD"], Some(root))?;
    if !ok {
        return Err(format!("`git rev-parse HEAD` failed, so even the last-resort tier has no marker: {}", first_line(&err)));
    }
    Ok(out.trim().to_string())
}

/// The owner's scoped spelling of an unscoped name, asked about as well: a
/// second coordinate serving this distribution means no version is canonical.
pub fn scoped_spelling(name: &str, repository: Option<&str>) -> Option<String> {
    if name.starts_with('@') {
        return None;
    }
    let Some(repository) = repository else {
        eprintln!("note: origin is not on GitHub, so this owner's npm scope cannot be derived and only the bare name {name} was asked about");
        return None;
    };
    Some(format!("@{}/{name}", repository.split('/').next().unwrap_or(repository)))
}
