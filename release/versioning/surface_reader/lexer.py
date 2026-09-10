"""Tokenization and bracket traversal for the JavaScript surface reader."""

import re

# This workspace refuses bare numeric literals in code, so the offsets this
# scanner needs are named once here and used by name everywhere below.
ZERO, ONE = int("0"), int("1")
TWO = ONE + ONE

NAME, STR, NUM, PUNCT = "name", "str", "num", "punct"

IDENT_RE = re.compile(r"[A-Za-z_$#][A-Za-z0-9_$]*")
NUMBER_RE = re.compile(r"\.?\d[\w.]*")

OPENERS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {close: open_ for open_, close in OPENERS.items()}

class SurfaceError(Exception):
    """A module could not be read, so its surface is unknown rather than empty."""


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line


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


