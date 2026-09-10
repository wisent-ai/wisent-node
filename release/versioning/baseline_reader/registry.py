"""Registry evidence and artifact extraction for release baselines."""

import json
import os
import tarfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

ZERO, ONE = int("0"), int("1")

REGISTRY = "https://registry.npmjs.org"
USER_AGENT = "autoversion-baseline (+https://github.com/lbartoszcze/AutoVersion)"
TIMEOUT_SECONDS = float(os.environ.get("BASELINE_TIMEOUT_SECONDS", "30"))

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


