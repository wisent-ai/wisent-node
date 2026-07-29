#!/usr/bin/env python3
"""Generate released-surface.json for the npm distribution in ./package.json.

The baseline describes the surface of the version **actually published**, and its
`source` field opens with a marker naming the artifact it was recovered from;
everything after the first space is prose for humans.  Tiers, best first:

    npm-tarball:<registry path>   the tarball npm serves, addressed as npm
                                  addresses it -- taken from
                                  .versions[<v>].dist.tarball and never assembled,
                                  because a scoped package's tarball is served
                                  under the UNSCOPED filename and the basename
                                  alone is not unique (`express` and
                                  `@types/express` both serve express-<v>.tgz)
    git-archive:<tag>             a tag at `origin`, reproduced with `git archive`
    head:<full sha>               the working revision -- last resort

A tier this generator cannot recover is a refusal, never a silent drop to a lower
one: a GitHub Release carrying assets outranks a tag, so if one appears while npm
serves nothing, this script fails and says so rather than filing a `git-archive:`
or `head:` baseline underneath it.

WHAT IT ASKS THE REGISTRY, AND HOW IT READS THE ANSWER
------------------------------------------------------
The latest published version comes from the registry's own `dist-tags.latest`,
never from the version package.json declares: the moment someone bumps ahead of a
release, looking up the declared version finds nothing and a naive generator throws
the real published baseline away.

Every registry answer is read as three states -- published, absent, unproven -- from
its **content**, because `curl -sSf`-style exit-status reading fails identically on
not-found and on no egress, and the wrong reading is the passing one.  npm's absence
answer is generic (`{"error":"Not found"}`) and does not name what you asked about,
so a lookup of an empty or wrong name reads as proven absence.  Two guards close
that: the name is asserted non-empty before any request, and npm must echo the
subject back in `.name` or the answer is unproven.

The lookup uses the full name package.json declares, scope included; the *filename*
inside the marker drops the scope but the *question* must not, because `node` and
`@types/node` are both real packages that answer.  The owner's scoped spelling is
probed as well: if a second coordinate also serves this distribution, no version is
canonical and a human has to choose, so that is a refusal too.

Never runs `npm`, never runs `node`, never builds.  The surface is read statically
by scripts/surface.py, from the unpacked tarball on the registry tier and from the
checked-out tree otherwise, so the baseline is a property of the artifact rather
than of the runner's toolchain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

sys.path.insert(int("0"), str(Path(__file__).resolve().parent))
import surface as surface_reader                                   # noqa: E402
from surface import SurfaceError                                   # noqa: E402

ZERO, ONE = int("0"), int("1")

REGISTRY = "https://registry.npmjs.org"
GITHUB_API = "https://api.github.com"
USER_AGENT = "autoversion-baseline (+https://github.com/lbartoszcze/AutoVersion)"
TIMEOUT_SECONDS = float(os.environ.get("BASELINE_TIMEOUT_SECONDS", "30"))

# The marker vocabulary, and which tiers claim a registry.  The workflow asks this
# script rather than restating the list, so the two files cannot drift apart.
TIER_NPM_TARBALL = "npm-tarball"
TIER_GIT_ARCHIVE = "git-archive"
TIER_HEAD = "head"
REGISTRY_TIERS = frozenset({TIER_NPM_TARBALL})
CLAIMS_REGISTRY, CLAIMS_NOTHING = "registry", "none"

PUBLISHED, ABSENT, UNPROVEN = "published", "absent", "unproven"
NOT_FOUND_PHRASE = "not found"


class BaselineError(Exception):
    """The best reachable tier could not be established, so nothing is written."""


def first_line(text):
    return next(iter(text.splitlines()), "").strip()


def fetch(url):
    """(status, body).  A transport failure is a status of None, never a 404."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
            return answer.status, answer.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return error.code, body
    except (URLError, OSError, ValueError) as error:
        return None, str(error)


def registry_url(name):
    """npm addresses a scoped package with the scope sigil kept and the slash
    encoded; an unencoded slash and no sigil is a different question that answers
    405, which a two-state check would read as proven absence."""
    return REGISTRY + "/" + name.replace("/", "%2f")


def probe_npm(name):
    """(state, why, document) read out of the answer's content."""
    if not name:
        return (UNPROVEN,
                "the package name is empty, and npm's absence answer names nothing, "
                "so this lookup would read as proven absence", None)
    status, body = fetch(registry_url(name))
    if status is None:
        return UNPROVEN, "no request to npm completed: " + first_line(body), None
    try:
        document = json.loads(body)
    except ValueError:
        return (UNPROVEN, "npm answered with something that is not JSON: "
                + first_line(body), None)
    if not isinstance(document, dict):
        return UNPROVEN, "npm answered with a " + type(document).__name__, None
    served = document.get("name")
    if isinstance(served, str) and served:
        if served != name:
            return (UNPROVEN, "npm answered about '" + served + "' when asked about '"
                    + name + "', so the answer is about a different package", None)
        return PUBLISHED, "", document
    stated = document.get("error")
    if isinstance(stated, str) and NOT_FOUND_PHRASE in stated.lower():
        return ABSENT, "", None
    return (UNPROVEN, "npm neither named a package nor stated not-found: "
            + first_line(body), None)


def latest_release(document, name):
    """(version, tarball url, sha1 or None) for the newest published version."""
    tags = document.get("dist-tags")
    latest = tags.get("latest") if isinstance(tags, dict) else None
    if not isinstance(latest, str) or not latest:
        raise BaselineError("npm serves " + name + " but names no `dist-tags.latest`, "
                            "so the latest published version is unknown")
    versions = document.get("versions")
    entry = versions.get(latest) if isinstance(versions, dict) else None
    if not isinstance(entry, dict):
        raise BaselineError("npm names " + latest + " as latest for " + name
                            + " but serves no metadata for it")
    dist = entry.get("dist")
    tarball = dist.get("tarball") if isinstance(dist, dict) else None
    if not isinstance(tarball, str) or not tarball:
        raise BaselineError("npm serves " + name + " " + latest
                            + " with no `dist.tarball`, so there is no artifact to recover")
    shasum = dist.get("shasum") if isinstance(dist, dict) else None
    return latest, tarball, shasum if isinstance(shasum, str) and shasum else None


def tarball_path(tarball):
    """The registry path npm addresses the artifact by -- taken, never assembled."""
    parts = urlsplit(tarball)
    if parts.scheme not in ("http", "https") or not parts.netloc or not parts.path:
        raise BaselineError("npm gave a tarball location this script cannot address: " + tarball)
    return parts.path.lstrip("/"), parts.netloc


def download(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
            return answer.read()
    except (HTTPError, URLError, OSError) as error:
        raise BaselineError("the published tarball " + url + " could not be fetched: " + str(error))


def unpack(payload, destination):
    archive = destination / "artifact.tgz"
    archive.write_bytes(payload)
    tree = destination / "tree"
    tree.mkdir()
    with tarfile.open(archive, mode="r:gz") as bundle:
        for member in bundle.getmembers():
            target = (tree / member.name).resolve()
            if not str(target).startswith(str(tree.resolve())):
                raise BaselineError("the tarball contains a path outside itself: " + member.name)
        try:
            bundle.extractall(tree, filter="data")
        except TypeError:
            bundle.extractall(tree)
    manifests = sorted(tree.rglob("package.json"), key=lambda path: len(path.parts))
    if not manifests:
        raise BaselineError("the published tarball contains no package.json")
    return manifests[ZERO].parent


def run(command, cwd=None):
    finished = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return finished.returncode, finished.stdout, finished.stderr


def origin_repository():
    """`owner/name` at `origin`, which is where tags and releases must be asked
    about -- never package.json's `repository`, which can name a repository that
    does not exist."""
    code, out, _ = run(["git", "remote", "get-url", "origin"])
    if code != ZERO:
        return None
    url = out.strip()
    if not url:
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


def blocking_github_release(repository):
    """A GitHub Release with assets outranks every tier below npm, so its presence
    must stop the generator instead of being quietly skipped."""
    if repository is None:
        raise BaselineError("`origin` does not name a GitHub repository, so whether a "
                            "Release outranks the tag and head tiers is unknown")
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


def origin_tags():
    """Tag names at `origin`.  A local listing is not evidence: a fork shares the
    upstream's objects, so a working copy can show tags that were never ours."""
    code, out, err = run(["git", "ls-remote", "--tags", "origin"])
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


def version_in_tag(tag):
    code, out, _ = run(["git", "show", tag + ":package.json"])
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


def best_tag():
    """(tag, version) for the newest tag whose tree declares the version its name
    claims.  A tag that disagrees with its own tree is reported and skipped: filing
    a baseline under a version the artifact does not carry measures everything
    afterwards against the wrong tree."""
    chosen = None
    for tag in origin_tags():
        claimed = tag[len("v"):] if tag.startswith("v") else tag
        declared = version_in_tag(tag)
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


def surface_of_tag(tag, tolerant):
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "tree"
        tree.mkdir()
        code, out, err = run(["git", "archive", "--format=tar", "-o",
                              str(Path(scratch) / "tag.tar"), tag])
        if code != ZERO:
            raise BaselineError("`git archive " + tag + "` failed, so its tree cannot be "
                                "read: " + first_line(err))
        with tarfile.open(Path(scratch) / "tag.tar") as bundle:
            try:
                bundle.extractall(tree, filter="data")
            except TypeError:
                bundle.extractall(tree)
        return surface_reader.compute(tree, tolerant)


def head_sha():
    code, out, err = run(["git", "rev-parse", "HEAD"])
    if code != ZERO:
        raise BaselineError("`git rev-parse HEAD` failed, so even the last-resort tier "
                            "has no marker: " + first_line(err))
    return out.strip()


def scoped_spelling(name, repository):
    """The owner's scoped spelling of an unscoped name, or None."""
    if name.startswith("@") or repository is None:
        return None
    return "@" + repository.split("/")[ZERO] + "/" + name


def build(root, tolerant):
    manifest = surface_reader.read_manifest(root)
    name = manifest.get("name")
    if not isinstance(name, str) or not name.strip():
        raise BaselineError("package.json declares no `name`, so there is no coordinate to "
                            "ask npm about and no absence anybody could prove")
    name = name.strip()
    declared = manifest.get("version")
    repository = origin_repository()

    state, why, document = probe_npm(name)
    if state == UNPROVEN:
        raise BaselineError("npm's answer about " + name + " is unproven, so neither its "
                            "presence nor its absence may be relied on: " + why)

    alias = scoped_spelling(name, repository)
    if alias is not None:
        alias_state, alias_why, _ = probe_npm(alias)
        if alias_state == UNPROVEN:
            raise BaselineError("npm answered about " + name + " but not about " + alias
                                + ", so a second coordinate cannot be ruled out: " + alias_why)
        if alias_state == PUBLISHED:
            raise BaselineError("npm serves both " + name + " and " + alias
                                + ", so no coordinate is canonical for this tree and a human "
                                "has to choose which one the gate guards")

    if state == PUBLISHED:
        version, tarball, shasum = latest_release(document, name)
        path, host = tarball_path(tarball)
        payload = download(tarball)
        if shasum is not None:
            got = hashlib.sha1(payload).hexdigest()
            if got != shasum:
                raise BaselineError("the tarball npm served for " + name + " " + version
                                    + " hashes to " + got + ", not the " + shasum
                                    + " the registry advertises")
        with tempfile.TemporaryDirectory() as scratch:
            unpacked = unpack(payload, Path(scratch))
            surface = surface_reader.compute(unpacked, tolerant)
        prose = ("recovered from the tarball " + host + " serves for " + name + " " + version
                 + (" (sha1 " + shasum + ")" if shasum else "")
                 + "; read statically from the published declarations, never built")
        return {"version": version, "source": TIER_NPM_TARBALL + ":" + path + " " + prose,
                "surface": surface}

    blocked = blocking_github_release(repository)
    if blocked is not None:
        raise BaselineError("npm serves nothing for " + name + " but the GitHub Release "
                            + blocked + " carries assets, which outranks the tag and head "
                            "tiers; recover from that asset instead of filing a lower "
                            "baseline underneath it")

    tagged = best_tag()
    if tagged is not None:
        tag, version = tagged
        surface = surface_of_tag(tag, tolerant)
        prose = ("reproduced with `git archive` from the tag " + tag + " at origin, whose tree "
                 "declares " + version + "; npm serves no " + name + " today")
        return {"version": version, "source": TIER_GIT_ARCHIVE + ":" + tag + " " + prose,
                "surface": surface}

    if not isinstance(declared, str) or not declared.strip():
        raise BaselineError("package.json declares no `version`, and no published artifact "
                            "supplies one, so the baseline would have nothing to compare against")
    surface = surface_reader.compute(root, tolerant)
    prose = ("the working revision: npm serves no " + name + ", origin holds no usable tag, "
             "and no GitHub Release carries an asset, so nothing has been published to recover")
    return {"version": declared.strip(), "source": TIER_HEAD + ":" + head_sha() + " " + prose,
            "surface": surface}


def marker_claim(marker):
    tier = marker.split(":")[ZERO] if marker else ""
    return CLAIMS_REGISTRY if tier in REGISTRY_TIERS else CLAIMS_NOTHING


def report_probe(name):
    state, why, document = probe_npm(name)
    if state == PUBLISHED:
        version, tarball, _ = latest_release(document, name)
        path, _ = tarball_path(tarball)
        print(PUBLISHED + " " + version + " " + path)
        return ZERO
    if state == ABSENT:
        print(ABSENT + " " + name)
        return ZERO
    print(UNPROVEN + " " + name + ": " + why)
    return ONE


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[ZERO])
    parser.add_argument("--root", default=".", help="directory holding package.json")
    parser.add_argument("--output", default="released-surface.json",
                        help="where to write the baseline")
    parser.add_argument("--stdout", action="store_true",
                        help="print the baseline instead of writing it, so a check can "
                             "compare tiers without ever rewriting the committed file")
    parser.add_argument("--tolerant", action="store_true",
                        help="pass --tolerant semantics to the surface reader")
    parser.add_argument("--probe", metavar="NAME",
                        help="ask npm about NAME through exactly the code path the subject "
                             "uses, and print published/absent/unproven")
    parser.add_argument("--marker-claims", metavar="MARKER",
                        help="print whether MARKER's tier claims a registry")
    args = parser.parse_args(argv)

    if args.marker_claims is not None:
        print(marker_claim(args.marker_claims))
        return ZERO
    try:
        if args.probe is not None:
            return report_probe(args.probe)
        document = build(Path(args.root).resolve(), args.tolerant)
    except (BaselineError, SurfaceError) as error:
        print("baseline: " + str(error), file=sys.stderr)
        return ONE
    except (json.JSONDecodeError, OSError) as error:
        print("baseline: " + str(error), file=sys.stderr)
        return ONE
    text = json.dumps(document, indent=ONE + ONE, sort_keys=True) + "\n"
    if args.stdout:
        sys.stdout.write(text)
        return ZERO
    Path(args.output).write_text(text, encoding="utf-8")
    print("wrote " + args.output + ": " + document["source"].split()[ZERO], file=sys.stderr)
    return ZERO


if __name__ == "__main__":
    raise SystemExit(main())
