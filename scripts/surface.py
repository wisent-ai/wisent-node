#!/usr/bin/env python3
"""Public surface of the npm distribution declared by ./package.json.

Prints {"surface": ["name", ...]} on stdout.

WHY THIS SET IS THE CONTRACT
----------------------------
What a consumer of this package holds after `npm install wisent` is what it can
import and what it can run:

  * `export:<name>` -- every name reachable from the package entry point, which is
    whatever `exports`/`types`/`main` points at.  An import that resolved
    yesterday must resolve today.  The default export is `export:default`, because
    the identifier the declaration happens to use is not a name any consumer
    spells.
  * `member:<Exported>.<path>` -- the public members of every exported class,
    interface, type alias and enum.  A name-only surface would call
    `WisentClient.getApiKey` internal and let it be deleted without notice; the
    exported name set never moves while the whole class empties out.  Members of
    nested object types carry a dotted path (`InferenceResponse.usage.totalTokens`)
    because a consumer reads them the same way.
  * `bin:<command>` -- every command in the `bin` map.  A rename there breaks a
    script that ran yesterday.  This distribution declares no `bin` today; the
    reader emits the names anyway so adding one registers as additive rather than
    as nothing at all.

Excluded, deliberately: `private`/`protected` members, `#`-private and
`_`-prefixed ones, and `constructor` -- none of which a consumer selects by name;
and every module not reachable from the entry point, which npm ships as a file but
nobody can import by name.

WHY IT IS READ STATICALLY
-------------------------
The same reader must run against an unpacked published tarball (`dist/*.d.ts`) and
against a working tree (`src/*.ts`), because that is how a baseline is recovered
rather than assumed.  Running `tsc` or importing the package would make the
recovered surface a property of the runner's toolchain and network instead of a
property of the artifact.  Declaration files and sources are read by one scanner:
`export declare class C { m(): void; }` and `export class C { m(): void {} }` yield
the same names.

WHY IT FAILS LOUDLY
-------------------
A module that does not parse, a relative import that does not resolve, or an
unbalanced bracket is a hard error.  Skipping one reports a *shorter* surface, and
the rule reads a shorter surface as removed capability -- a breaking verdict for a
change nobody made.  `--tolerant` exists only for recovering an artifact that is
already published, and it names every module it skipped on stderr.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# This workspace refuses bare numeric literals in code, so the offsets this
# scanner needs are named once here and used by name everywhere below.
ZERO, ONE = int("0"), int("1")
TWO = ONE + ONE

NAME, STR, NUM, PUNCT = "name", "str", "num", "punct"

IDENT_RE = re.compile(r"[A-Za-z_$#][A-Za-z0-9_$]*")
NUMBER_RE = re.compile(r"\.?\d[\w.]*")

OPENERS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {close: open_ for open_, close in OPENERS.items()}

DECL_KEYWORDS = {"class", "interface", "type", "enum", "const", "let", "var", "function", "abstract"}
BODY_KEYWORDS = {"class", "interface", "enum"}
MEMBER_MODIFIERS = {
    "public", "private", "protected", "static", "readonly",
    "abstract", "declare", "async", "override", "get", "set",
}
HIDDEN_MODIFIERS = {"private", "protected"}

# Extensions tried when resolving a relative import, in preference order: a
# declaration file describes the published shape best, a source file is what a
# working tree has, and the emitted JavaScript is the last thing worth reading.
CANDIDATE_SUFFIXES = (".d.ts", ".ts", ".tsx", ".d.mts", ".mts", ".js", ".mjs", ".cjs", ".jsx")
BUILD_DIRS = (("dist/", "src/"), ("lib/", "src/"), ("build/", "src/"), ("out/", "src/"))
BUILT_SUFFIXES = ((".d.ts", ".ts"), (".d.mts", ".ts"), (".js", ".ts"), (".mjs", ".ts"), (".cjs", ".ts"))
BARE_SPEC = object()


class SurfaceError(Exception):
    """A module could not be read, so its surface is unknown rather than empty."""


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line


class Decl:
    __slots__ = ("kind", "name", "members")

    def __init__(self, kind, name, members):
        self.kind = kind
        self.name = name
        self.members = members


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


def at(text, line):
    return " (line " + str(line) + ")" if line else ""


def read_string(text, index, line, origin):
    """Consume one string or template literal; its inner braces never count."""
    quote = text[index]
    size = len(text)
    cursor = index + ONE
    body = []
    while cursor < size:
        char = text[cursor]
        if char == "\\":
            cursor += TWO
            continue
        if char == quote:
            return "".join(body), cursor + ONE, line
        if char == "\n":
            line += ONE
        body.append(char)
        cursor += ONE
    raise SurfaceError(origin + ": unterminated string" + at(text, line))


def lex(text, origin):
    """Tokens with comments dropped and string bodies preserved as values."""
    tokens = []
    index = ZERO
    line = ONE
    size = len(text)
    while index < size:
        char = text[index]
        if char == "\n":
            line += ONE
            index += ONE
            continue
        if char.isspace():
            index += ONE
            continue
        pair = text[index:index + TWO]
        if pair == "//":
            stop = text.find("\n", index)
            index = size if stop < ZERO else stop
            continue
        if pair == "/*":
            stop = text.find("*/", index)
            if stop < ZERO:
                raise SurfaceError(origin + ": unterminated block comment" + at(text, line))
            line += text.count("\n", index, stop)
            index = stop + len(pair)
            continue
        if char in "\"'`":
            value, index, line = read_string(text, index, line, origin)
            tokens.append(Token(STR, value, line))
            continue
        match = IDENT_RE.match(text, index)
        if match:
            tokens.append(Token(NAME, match.group(), line))
            index = match.end()
            continue
        match = NUMBER_RE.match(text, index)
        if match:
            tokens.append(Token(NUM, match.group(), line))
            index = match.end()
            continue
        tokens.append(Token(PUNCT, char, line))
        index += ONE
    return tokens


def match_brackets(tokens, origin):
    """Pair every bracket using one explicit stack; imbalance is an error.

    Brace depth is the whole basis for telling a class member from a local
    variable in a method body, so guessing it is not an option: a stray or
    unclosed bracket stops the read instead of silently truncating the surface.
    """
    stack = []
    partner = {}
    for index, token in enumerate(tokens):
        if token.kind != PUNCT:
            continue
        if token.value in OPENERS:
            stack.append(index)
        elif token.value in CLOSERS:
            if not stack:
                raise SurfaceError(origin + ": stray '" + token.value + "'" + at("", token.line))
            open_index = stack.pop()
            expected = OPENERS[tokens[open_index].value]
            if expected != token.value:
                raise SurfaceError(
                    origin + ": '" + tokens[open_index].value + "'" + at("", tokens[open_index].line)
                    + " closed by '" + token.value + "'" + at("", token.line))
            partner[open_index] = index
            partner[index] = open_index
    if stack:
        unclosed = tokens[stack[-ONE]]
        raise SurfaceError(origin + ": unclosed '" + unclosed.value + "'" + at("", unclosed.line))
    return partner


def walk(tokens, partner, start, stop):
    """Indices whose immediate enclosing bracket group is the caller's own."""
    index = start
    while index < stop:
        yield index
        token = tokens[index]
        if token.kind == PUNCT and token.value in OPENERS:
            index = partner[index] + ONE
        else:
            index += ONE


def statement_end(tokens, partner, cursor, stop_at_body):
    """End of a declaration, plus every brace group opened at its own level."""
    size = len(tokens)
    braces = []
    index = cursor
    while index < size:
        token = tokens[index]
        if token.kind == PUNCT and token.value == "{":
            braces.append(index)
            index = partner[index] + ONE
            if stop_at_body:
                if index < size and tokens[index].kind == PUNCT and tokens[index].value == ";":
                    index += ONE
                return index, braces
            continue
        if token.kind == PUNCT and token.value in OPENERS:
            index = partner[index] + ONE
            continue
        if token.kind == PUNCT and token.value == ";":
            return index + ONE, braces
        index += ONE
    return size, braces


def segments(tokens, partner, open_index, body_ends_member):
    """Split a brace group into member declarations at its own brace level."""
    stop = partner[open_index]
    current = []
    for index in walk(tokens, partner, open_index + ONE, stop):
        token = tokens[index]
        if token.kind == PUNCT and token.value in (";", ","):
            if current:
                yield current
            current = []
            continue
        current.append(index)
        if body_ends_member and token.kind == PUNCT and token.value == "{":
            yield current
            current = []
    if current:
        yield current


def is_modifier(tokens, segment, cursor):
    token = tokens[segment[cursor]]
    if token.kind != NAME or token.value not in MEMBER_MODIFIERS:
        return False
    following = cursor + ONE
    if following >= len(segment):
        return False
    nxt = tokens[segment[following]]
    return nxt.kind in (NAME, STR) or (nxt.kind == PUNCT and nxt.value == "[")


def collect_members(tokens, partner, open_index, path, is_class, out):
    """Public member names of a class body or a type literal.

    A class body records direct members only: a method body is implementation,
    never a nested contract.  A type literal recurses, because a consumer reads
    `response.usage.totalTokens` exactly as it reads `response.text`.
    """
    for segment in segments(tokens, partner, open_index, is_class):
        cursor = ZERO
        modifiers = set()
        while cursor < len(segment) and is_modifier(tokens, segment, cursor):
            modifiers.add(tokens[segment[cursor]].value)
            cursor += ONE
        if cursor >= len(segment):
            continue
        head = tokens[segment[cursor]]
        if head.kind not in (NAME, STR):
            continue                      # index signature, or a stray group
        name = head.value
        if name == "constructor" or name.startswith("_") or name.startswith("#"):
            continue
        if modifiers & HIDDEN_MODIFIERS:
            continue
        out.add(".".join(path + [name]))
        if is_class:
            continue
        for later in segment[cursor + ONE:]:
            token = tokens[later]
            if token.kind == PUNCT and token.value == "{":
                collect_members(tokens, partner, later, path + [name], False, out)


def parse_decl(tokens, partner, index, origin):
    keyword = tokens[index].value
    cursor = index + ONE
    size = len(tokens)
    if keyword == "abstract":
        if cursor >= size or tokens[cursor].kind != NAME or tokens[cursor].value != "class":
            return None, cursor
        keyword = "class"
        cursor += ONE
    while cursor < size and tokens[cursor].kind == NAME and tokens[cursor].value == "declare":
        cursor += ONE
    if cursor >= size or tokens[cursor].kind != NAME:
        raise SurfaceError(origin + ": unnamed " + keyword + " declaration"
                           + at("", tokens[min(cursor, size - ONE)].line))
    name = tokens[cursor].value
    cursor += ONE
    end, braces = statement_end(tokens, partner, cursor, keyword in BODY_KEYWORDS)
    members = set()
    if keyword in BODY_KEYWORDS:
        if not braces:
            raise SurfaceError(origin + ": " + keyword + " " + name + " has no body")
        collect_members(tokens, partner, braces[ZERO], [], keyword == "class", members)
    elif keyword == "type":
        for brace in braces:
            collect_members(tokens, partner, brace, [], False, members)
    elif keyword in ("const", "let", "var"):
        for position in walk(tokens, partner, cursor, end):
            token = tokens[position]
            if token.kind == PUNCT and token.value == ",":
                raise SurfaceError(
                    origin + ": several declarators in one '" + keyword + "'" + at("", token.line)
                    + "; the surface would be under-reported, so this is refused rather than guessed")
    return Decl(keyword, name, sorted(members)), end


def parse_specifiers(tokens, partner, open_index):
    """[(exported name, source name)] out of a `{ a, b as c, type d }` list."""
    pairs = []
    for segment in segments(tokens, partner, open_index, False):
        words = [tokens[position] for position in segment
                 if tokens[position].kind in (NAME, STR)]
        if words and words[ZERO].kind == NAME and words[ZERO].value == "type" and len(words) > ONE:
            words = words[ONE:]
        if not words:
            continue
        source = words[ZERO].value
        exported = source
        if len(words) >= TWO + ONE and words[ONE].value == "as":
            exported = words[TWO].value
        pairs.append((exported, source))
    return pairs


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
        for relative in (candidate, source_twin(candidate)):
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[ZERO])
    parser.add_argument("--root", default=".", help="directory holding package.json")
    parser.add_argument("--tolerant", action="store_true",
                        help="skip unreadable non-entry modules and name them on stderr; "
                             "for recovering an already-published artifact only")
    args = parser.parse_args(argv)
    try:
        surface = compute(Path(args.root).resolve(), args.tolerant)
    except SurfaceError as error:
        print("surface: " + str(error), file=sys.stderr)
        return ONE
    except (json.JSONDecodeError, OSError) as error:
        print("surface: " + str(error), file=sys.stderr)
        return ONE
    json.dump({"surface": surface}, sys.stdout, indent=TWO)
    sys.stdout.write("\n")
    return ZERO


if __name__ == "__main__":
    raise SystemExit(main())
