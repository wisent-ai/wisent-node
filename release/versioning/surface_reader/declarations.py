"""Public declarations and members, independent of module resolution."""

from .lexer import NAME, ONE, PUNCT, STR, TWO, ZERO, SurfaceError, at, statement_end, walk

DECL_KEYWORDS = {"class", "interface", "type", "enum", "const", "let", "var", "function", "abstract"}
# Declarations whose brace group holds their members.
BODY_KEYWORDS = {"class", "interface", "enum"}
# Declarations a brace group ENDS.  A `.d.ts` writes `export declare function f():
# number;` and a source file writes `export function f(): number { ... }`; a reader
# that only stopped at the semicolon would run past the body of the second and
# swallow every declaration after it -- reporting a shorter surface, which the rule
# reads as removed capability.  A type alias is the exception: it always ends at a
# semicolon, and its braces are its members rather than its body.
BODY_TERMINATED = BODY_KEYWORDS | {"function", "const", "let", "var"}
MEMBER_MODIFIERS = {
    "public", "private", "protected", "static", "readonly",
    "abstract", "declare", "async", "override", "get", "set",
}
HIDDEN_MODIFIERS = {"private", "protected"}

class Decl:
    __slots__ = ("kind", "name", "members")

    def __init__(self, kind, name, members):
        self.kind = kind
        self.name = name
        self.members = members


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
    end, braces = statement_end(tokens, partner, cursor, keyword in BODY_TERMINATED)
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


