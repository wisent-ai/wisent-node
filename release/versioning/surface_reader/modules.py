"""Module parsing and traversal of the exported dependency graph."""

import sys
from pathlib import Path

from .declarations import DECL_KEYWORDS, parse_decl, parse_specifiers
from .lexer import NAME, ONE, OPENERS, PUNCT, STR, TWO, ZERO, SurfaceError, at, lex, match_brackets, statement_end

# Extensions tried when resolving a relative import, in preference order: a
# declaration file describes the published shape best, a source file is what a
# working tree has, and the emitted JavaScript is the last thing worth reading.
CANDIDATE_SUFFIXES = (".d.ts", ".ts", ".tsx", ".d.mts", ".mts", ".js", ".mjs", ".cjs", ".jsx")
BARE_SPEC = object()


class Module:
    """What one file declares, exports, re-exports and imports by name."""

    def __init__(self, path):
        self.path = path
        self.decls = {}
        self.local_exports = []      # (exported name, local name)
        self.reexports = []          # (exported name, source name, module spec)
        self.star_reexports = []     # module spec
        self.imports = {}            # local name -> (module spec, source name)
        self.default = None          # None, or a Decl (possibly with no members)
        self.has_default = False


def expect_spec(tokens, cursor, origin):
    if cursor >= len(tokens) or tokens[cursor].kind != STR:
        raise SurfaceError(origin + ": `from` without a module specifier")
    return tokens[cursor].value


def parse_export(tokens, partner, index, module, origin):
    size = len(tokens)
    cursor = index + ONE
    while cursor < size and tokens[cursor].kind == NAME and tokens[cursor].value == "declare":
        cursor += ONE
    if cursor >= size:
        raise SurfaceError(origin + ": `export` at end of file")
    token = tokens[cursor]
    if token.kind == PUNCT and token.value == "{":
        pairs = parse_specifiers(tokens, partner, cursor)
        after = partner[cursor] + ONE
        spec = None
        if after < size and tokens[after].kind == NAME and tokens[after].value == "from":
            spec = expect_spec(tokens, after + ONE, origin)
            after += TWO
        if after < size and tokens[after].kind == PUNCT and tokens[after].value == ";":
            after += ONE
        for exported, source in pairs:
            if spec is None:
                module.local_exports.append((exported, source))
            else:
                module.reexports.append((exported, source, spec))
        return after
    if token.kind == PUNCT and token.value == "*":
        after = cursor + ONE
        alias = None
        if after < size and tokens[after].kind == NAME and tokens[after].value == "as":
            alias = tokens[after + ONE].value
            after += TWO
        if after >= size or tokens[after].kind != NAME or tokens[after].value != "from":
            raise SurfaceError(origin + ": `export *` without `from`" + at("", token.line))
        spec = expect_spec(tokens, after + ONE, origin)
        after += TWO
        if after < size and tokens[after].kind == PUNCT and tokens[after].value == ";":
            after += ONE
        if alias is None:
            module.star_reexports.append(spec)
        else:
            module.reexports.append((alias, alias, spec))
        return after
    if token.kind == NAME and token.value == "default":
        module.has_default = True
        inner = cursor + ONE
        if inner < size and tokens[inner].kind == NAME and tokens[inner].value in DECL_KEYWORDS:
            decl, after = parse_decl(tokens, partner, inner, origin)
            module.default = decl
            return after
        after, _ = statement_end(tokens, partner, inner, True)
        return after
    if token.kind == NAME and token.value in DECL_KEYWORDS:
        decl, after = parse_decl(tokens, partner, cursor, origin)
        if decl is not None:
            module.decls[decl.name] = decl
            module.local_exports.append((decl.name, decl.name))
        return after
    raise SurfaceError(origin + ": unrecognised export form `export " + str(token.value) + "`"
                       + at("", token.line))


def parse_import(tokens, partner, index, module, origin):
    size = len(tokens)
    cursor = index + ONE
    if cursor < size and tokens[cursor].kind == STR:
        return cursor + ONE                      # side-effect import
    scan = cursor
    braces = []
    while scan < size:
        token = tokens[scan]
        if token.kind == PUNCT and token.value == "{":
            braces.append(scan)
            scan = partner[scan] + ONE
            continue
        if token.kind == NAME and token.value == "from":
            spec = expect_spec(tokens, scan + ONE, origin)
            for brace in braces:
                for exported, source in parse_specifiers(tokens, partner, brace):
                    module.imports[exported] = (spec, source)
            after = scan + TWO
            if after < size and tokens[after].kind == PUNCT and tokens[after].value == ";":
                after += ONE
            return after
        if token.kind == PUNCT and token.value == ";":
            return scan + ONE
        scan += ONE
    return size


def parse_module(path):
    origin = str(path)
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except OSError as error:
        raise SurfaceError(origin + ": cannot be read: " + str(error))
    tokens = lex(text, origin)
    partner = match_brackets(tokens, origin)
    module = Module(path)
    index = ZERO
    size = len(tokens)
    while index < size:
        token = tokens[index]
        if token.kind == PUNCT and token.value in OPENERS:
            index = partner[index] + ONE
            continue
        if token.kind == NAME and token.value == "export":
            index = parse_export(tokens, partner, index, module, origin)
            continue
        if token.kind == NAME and token.value == "import":
            index = parse_import(tokens, partner, index, module, origin)
            continue
        if token.kind == NAME and token.value in DECL_KEYWORDS:
            decl, index = parse_decl(tokens, partner, index, origin)
            if decl is not None:
                module.decls[decl.name] = decl
            continue
        index += ONE
    return module


def resolve_spec(from_path, spec):
    """A file for a relative import, BARE_SPEC for a package name, None if lost."""
    if not spec.startswith("."):
        return BARE_SPEC
    base = (from_path.parent / spec).resolve()
    for suffix in CANDIDATE_SUFFIXES:
        probe = Path(str(base) + suffix)
        if probe.is_file():
            return probe
    if base.is_file():
        return base
    for suffix in CANDIDATE_SUFFIXES:
        probe = base / ("index" + suffix)
        if probe.is_file():
            return probe
    return None


class Reader:
    def __init__(self, tolerant):
        self.tolerant = tolerant
        self.cache = {}
        self.skipped = []

    def module(self, path):
        key = str(path)
        if key not in self.cache:
            self.cache[key] = parse_module(path)
        return self.cache[key]

    def exports_of(self, path, stack):
        """Exported name -> Decl or None, following relative re-exports."""
        key = str(path)
        if key in stack:
            raise SurfaceError(key + ": circular re-export")
        stack = stack + (key,)
        module = self.module(path)
        found = {}
        for spec in module.star_reexports:
            target = self.follow(module, spec, stack)
            if isinstance(target, dict):
                found.update(target)
        for exported, source in module.local_exports:
            decl = module.decls.get(source)
            if decl is None and source in module.imports:
                spec, original = module.imports[source]
                table = self.follow(module, spec, stack)
                decl = table.get(original) if isinstance(table, dict) else None
            found[exported] = decl
        for exported, source, spec in module.reexports:
            table = self.follow(module, spec, stack)
            if not isinstance(table, dict):
                found[exported] = None
                continue
            if source not in table:
                raise SurfaceError(str(path) + ": re-exports `" + source + "` from '" + spec
                                   + "', which does not export it")
            found[exported] = table[source]
        if module.has_default:
            found["default"] = module.default
        return found

    def follow(self, module, spec, stack):
        target = resolve_spec(module.path, spec)
        if target is BARE_SPEC:
            print("note: `" + spec + "` is a package, not a file, so the names it "
                  "contributes are recorded without members", file=sys.stderr)
            return BARE_SPEC
        if target is None:
            message = str(module.path) + ": relative import '" + spec + "' does not resolve"
            if not self.tolerant:
                raise SurfaceError(message)
            self.skipped.append(message)
            return BARE_SPEC
        try:
            return self.exports_of(target, stack)
        except SurfaceError as error:
            if not self.tolerant:
                raise
            self.skipped.append(str(error))
            return BARE_SPEC


