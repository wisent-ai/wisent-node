"""Resolve a package entrypoint and extract the distribution's public names."""

import json
import sys
from pathlib import Path

from .lexer import ONE, ZERO, SurfaceError
from .modules import Reader, resolve_spec

BUILD_DIRS = (("dist/", "src/"), ("lib/", "src/"), ("build/", "src/"), ("out/", "src/"))
BUILT_SUFFIXES = ((".d.ts", ".ts"), (".d.mts", ".ts"), (".js", ".ts"), (".mjs", ".ts"), (".cjs", ".ts"))


def exports_field_candidates(exports):
    """Every file string the `exports` map points at, types-first."""
    subtree = exports
    if isinstance(exports, dict):
        if "." in exports:
            subtree = exports["."]
        elif any(key.startswith(".") for key in exports):
            subtree = None
    ordered = []

    def visit(node, types_first):
        if isinstance(node, str):
            ordered.append((types_first, node))
            return
        if isinstance(node, dict):
            for key, value in node.items():
                visit(value, types_first or key in ("types", "typings"))

    if subtree is not None:
        visit(subtree, False)
    return [path for _, path in sorted(ordered, key=lambda pair: not pair[ZERO])]


def source_twin(relative):
    text = relative
    for built, source in BUILD_DIRS:
        if text.startswith(built):
            text = source + text[len(built):]
            break
        if text.startswith("./" + built):
            text = "./" + source + text[len("./" + built):]
            break
    for suffix, replacement in BUILT_SUFFIXES:
        if text.endswith(suffix):
            return text[:len(text) - len(suffix)] + replacement
    return text


def pick_entry(root, manifest):
    """The file the entry point's names are read out of.

    The source twin is preferred over the built path the manifest names, and the
    order is load-bearing rather than tidy.  This repository commits its `dist/`,
    and `package.json` runs `npm run build` from `prepare`, so `npm publish`
    rebuilds `dist/` out of `src/` -- which makes `src/` what decides the surface
    a consumer will hold, and the committed `dist/` a build output that may lag it.
    A reader that trusted the committed `dist/` would see no change when an export
    is added or removed in `src/` and never rebuilt, and pass a real surface change
    through.  An unpacked published tarball ships no `src/`, so there the built
    declarations are read, which is exactly what that artifact is.
    """
    candidates = []
    if "exports" in manifest:
        candidates.extend(exports_field_candidates(manifest["exports"]))
    for key in ("types", "typings", "main"):
        value = manifest.get(key)
        if isinstance(value, str):
            candidates.append(value)
    if not candidates:
        raise SurfaceError(str(root) + "/package.json declares no `exports`, `types` or `main`, "
                           "so the package has no entry point and no importable surface")
    tried = []
    for candidate in candidates:
        for relative in (source_twin(candidate), candidate):
            probe = (root / relative).resolve()
            tried.append(str(probe))
            if probe.is_file():
                return probe
            resolved = resolve_spec(probe, "./" + probe.name)
            if isinstance(resolved, Path) and resolved.is_file():
                return resolved
    raise SurfaceError("no entry point exists on disk; tried: " + ", ".join(tried))


def bin_names(manifest):
    value = manifest.get("bin")
    if isinstance(value, dict):
        return sorted(value)
    if isinstance(value, str):
        name = manifest.get("name") or ""
        if not name:
            raise SurfaceError("package.json has a string `bin` but no `name`, so the "
                               "installed command name is undecidable")
        return [name.split("/")[-ONE]]
    return []


def read_manifest(root):
    path = root / "package.json"
    if not path.is_file():
        raise SurfaceError(str(path) + " does not exist, so there is no distribution to read")
    return json.loads(path.read_text(encoding="utf-8"))


def compute(root, tolerant):
    manifest = read_manifest(root)
    entry = pick_entry(root, manifest)
    reader = Reader(tolerant)
    table = reader.exports_of(entry, ())
    names = set()
    for exported, decl in table.items():
        names.add("export:" + exported)
        if decl is not None:
            for member in decl.members:
                names.add("member:" + exported + "." + member)
    for command in bin_names(manifest):
        names.add("bin:" + command)
    if not names:
        raise SurfaceError(str(entry) + " exports nothing; an empty surface would make every "
                           "later comparison vacuous")
    for message in reader.skipped:
        print("skipped: " + message, file=sys.stderr)
    return sorted(names)


