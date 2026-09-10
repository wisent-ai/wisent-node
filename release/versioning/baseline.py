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
by release/versioning/surface.py, from the unpacked tarball on the registry tier and from the
checked-out tree otherwise, so the baseline is a property of the artifact rather
than of the runner's toolchain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from baseline_reader.registry import (
    ABSENT, ONE, PUBLISHED, UNPROVEN, ZERO, BaselineError,
    download, latest_release, probe_npm, tarball_path, unpack,
)
from baseline_reader.repository import (
    best_tag, blocking_github_release, github_repository, head_sha,
    origin_url, scoped_spelling, surface_of_tag,
)
from surface_reader.distribution import compute, read_manifest
from surface_reader.lexer import SurfaceError

# The marker vocabulary, and which tiers claim a registry.  The workflow asks this
# script rather than restating the list, so the two files cannot drift apart.
TIER_NPM_TARBALL = "npm-tarball"
TIER_GIT_ARCHIVE = "git-archive"
TIER_HEAD = "head"
REGISTRY_TIERS = frozenset({TIER_NPM_TARBALL})
CLAIMS_REGISTRY, CLAIMS_NOTHING = "registry", "none"

def build(root, tolerant):
    manifest = read_manifest(root)
    name = manifest.get("name")
    if not isinstance(name, str) or not name.strip():
        raise BaselineError("package.json declares no `name`, so there is no coordinate to "
                            "ask npm about and no absence anybody could prove")
    name = name.strip()
    declared = manifest.get("version")
    remote = origin_url(root)
    repository = github_repository(remote)

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
            surface = compute(unpacked, tolerant)
        prose = ("recovered from the tarball " + host + " serves for " + name + " " + version
                 + (" (sha1 " + shasum + ")" if shasum else "")
                 + "; read statically from the published declarations, never built")
        return {"version": version, "source": TIER_NPM_TARBALL + ":" + path + " " + prose,
                "surface": surface}

    blocked = blocking_github_release(remote, repository)
    if blocked is not None:
        raise BaselineError("npm serves nothing for " + name + " but the GitHub Release "
                            + blocked + " carries assets, which outranks the tag and head "
                            "tiers; recover from that asset instead of filing a lower "
                            "baseline underneath it")

    tagged = best_tag(root)
    if tagged is not None:
        tag, version = tagged
        surface = surface_of_tag(tag, tolerant, root)
        prose = ("reproduced with `git archive` from the tag " + tag + " at origin, whose tree "
                 "declares " + version + "; npm serves no " + name + " today")
        return {"version": version, "source": TIER_GIT_ARCHIVE + ":" + tag + " " + prose,
                "surface": surface}

    if not isinstance(declared, str) or not declared.strip():
        raise BaselineError("package.json declares no `version`, and no published artifact "
                            "supplies one, so the baseline would have nothing to compare against")
    surface = compute(root, tolerant)
    prose = ("the working revision: npm serves no " + name + ", origin holds no usable tag, "
             "and no GitHub Release carries an asset, so nothing has been published to recover")
    return {"version": declared.strip(), "source": TIER_HEAD + ":" + head_sha(root) + " " + prose,
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
