"""Repository identity, published tags and their recoverable surfaces."""

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from surface_reader.distribution import compute
from .registry import ONE, ZERO, BaselineError, fetch, first_line

GITHUB_API = "https://api.github.com"


def run(command, cwd=None):
    finished = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return finished.returncode, finished.stdout, finished.stderr


def origin_url(root):
    """Where `origin` points, or None when there is no remote to ask."""
    code, out, _ = run(["git", "remote", "get-url", "origin"], cwd=root)
    if code != ZERO:
        return None
    return out.strip() or None


def github_repository(url):
    """`owner/name` when `origin` is on GitHub, else None.

    Taken from `origin`, never from package.json's `repository`: this manifest
    names github.com/wisent/wisent-js, which does not exist, so believing it would
    make every tag and release question a question about nothing.
    """
    if url is None:
        return None
    text = url[len("git+"):] if url.startswith("git+") else url
    if text.endswith(".git"):
        text = text[:len(text) - len(".git")]
    if "github.com" not in text:
        return None
    tail = text.split("github.com", ONE)[-ONE].lstrip(":/")
    parts = [part for part in tail.split("/") if part]
    if len(parts) < ONE + ONE:
        return None
    return parts[ZERO] + "/" + parts[ONE]


def blocking_github_release(url, repository):
    """A GitHub Release with assets outranks every tier below npm, so its presence
    must stop the generator instead of being quietly skipped."""
    if url is None:
        raise BaselineError("this tree has no `origin`, so neither a Release nor a tag can "
                            "be asked about and no tier below the registry can be trusted")
    if repository is None:
        print("note: origin (" + url + ") is not on GitHub, so there is no GitHub Release "
              "tier to outrank a tag here", file=sys.stderr)
        return None
    status, body = fetch(GITHUB_API + "/repos/" + repository + "/releases")
    if status is None:
        raise BaselineError("GitHub did not answer about releases of " + repository
                            + ", so a higher tier cannot be ruled out: " + first_line(body))
    try:
        document = json.loads(body)
    except ValueError:
        raise BaselineError("GitHub answered about releases of " + repository
                            + " with something that is not JSON: " + first_line(body))
    if not isinstance(document, list):
        message = document.get("message") if isinstance(document, dict) else None
        raise BaselineError("GitHub refused to list releases of " + repository + ": "
                            + str(message or first_line(body)))
    for release in document:
        assets = release.get("assets") if isinstance(release, dict) else None
        if isinstance(assets, list) and assets:
            return str(release.get("tag_name"))
    return None


def origin_tags(root):
    """Tag names at `origin`.  A local listing is not evidence: a fork shares the
    upstream's objects, so a working copy can show tags that were never ours."""
    code, out, err = run(["git", "ls-remote", "--tags", "origin"], cwd=root)
    if code != ZERO:
        raise BaselineError("`git ls-remote --tags origin` failed, so whether this "
                            "distribution was ever tagged is unknown: " + first_line(err))
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < ONE + ONE:
            continue
        ref = parts[-ONE]
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            name = name[:len(name) - len("^{}")]
        names.add(name)
    return sorted(names)


def version_in_tag(tag, root):
    code, out, _ = run(["git", "show", tag + ":package.json"], cwd=root)
    if code != ZERO:
        return None
    try:
        return json.loads(out).get("version")
    except ValueError:
        return None


def is_newer(candidate, incumbent):
    code, out, err = run(["autoversion", "order", "--older", incumbent,
                          "--newer", candidate, "--json"])
    if code != ZERO:
        raise BaselineError("the rule could not order " + incumbent + " and " + candidate
                            + ": " + first_line(err))
    return json.loads(out).get("is_newer") == str(True)


def best_tag(root):
    """(tag, version) for the newest tag whose tree declares the version its name
    claims.  A tag that disagrees with its own tree is reported and skipped: filing
    a baseline under a version the artifact does not carry measures everything
    afterwards against the wrong tree."""
    chosen = None
    for tag in origin_tags(root):
        claimed = tag[len("v"):] if tag.startswith("v") else tag
        declared = version_in_tag(tag, root)
        if declared is None:
            print("note: tag " + tag + " has no readable package.json, so it is skipped",
                  file=sys.stderr)
            continue
        if declared != claimed:
            print("note: tag " + tag + " points at a tree declaring " + str(declared)
                  + ", so it is skipped rather than filed under " + claimed, file=sys.stderr)
            continue
        if chosen is None or is_newer(declared, chosen[ONE]):
            chosen = (tag, declared)
    return chosen


def surface_of_tag(tag, tolerant, root):
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "tree"
        tree.mkdir()
        code, out, err = run(["git", "archive", "--format=tar", "-o",
                              str(Path(scratch) / "tag.tar"), tag], cwd=root)
        if code != ZERO:
            raise BaselineError("`git archive " + tag + "` failed, so its tree cannot be "
                                "read: " + first_line(err))
        with tarfile.open(Path(scratch) / "tag.tar") as bundle:
            try:
                bundle.extractall(tree, filter="data")
            except TypeError:
                bundle.extractall(tree)
        return compute(tree, tolerant)


def head_sha(root):
    code, out, err = run(["git", "rev-parse", "HEAD"], cwd=root)
    if code != ZERO:
        raise BaselineError("`git rev-parse HEAD` failed, so even the last-resort tier "
                            "has no marker: " + first_line(err))
    return out.strip()


def scoped_spelling(name, repository):
    """The owner's scoped spelling of an unscoped name, or None.

    Asking npm about the scope as well as the bare name is not decoration: a second
    coordinate serving this same distribution would mean no version is canonical,
    and if the manifest's bare name were the absent one it would be the *scoped*
    coordinate carrying the real releases.
    """
    if name.startswith("@"):
        return None
    if repository is None:
        print("note: origin is not on GitHub, so this owner's npm scope cannot be derived "
              "and only the bare name " + name + " was asked about", file=sys.stderr)
        return None
    return "@" + repository.split("/")[ZERO] + "/" + name


