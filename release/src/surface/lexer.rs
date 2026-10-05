//! Tokenization and bracket traversal for the JavaScript surface reader.
//! Comments are dropped, string and template bodies kept as values, and every
//! bracket is paired: brace depth is what tells a class member from a local
//! in a method body, so an imbalance stops the read instead of truncating it.

use std::collections::HashMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Name,
    Str,
    Num,
    Punct,
}

#[derive(Clone, Debug)]
pub struct Token {
    pub kind: Kind,
    pub value: String,
    pub line: usize,
}

impl Token {
    pub fn is_punct(&self, value: &str) -> bool {
        self.kind == Kind::Punct && self.value == value
    }

    pub fn is_name(&self, value: &str) -> bool {
        self.kind == Kind::Name && self.value == value
    }

    pub fn is_opener(&self) -> bool {
        self.kind == Kind::Punct && closer_of(&self.value).is_some()
    }
}

/// The closing bracket of an opening one.
pub fn closer_of(open: &str) -> Option<&'static str> {
    match open {
        "(" => Some(")"),
        "[" => Some("]"),
        "{" => Some("}"),
        _ => None,
    }
}

fn opener_of(close: &str) -> Option<&'static str> {
    match close {
        ")" => Some("("),
        "]" => Some("["),
        "}" => Some("{"),
        _ => None,
    }
}

pub fn at(line: usize) -> String {
    format!(" (line {line})")
}

fn identifier_start(character: char) -> bool {
    character.is_ascii_alphabetic() || character == '_' || character == '$' || character == '#'
}

fn identifier_part(character: char) -> bool {
    character.is_ascii_alphanumeric() || character == '_' || character == '$'
}

/// Tokens with comments dropped and string bodies preserved as values.
pub fn lex(text: &str, origin: &str) -> Result<Vec<Token>, String> {
    let characters: Vec<char> = text.chars().collect();
    let size = characters.len();
    let mut tokens = Vec::new();
    let (mut index, mut line) = (0, 1);
    while index < size {
        let character = characters[index];
        if character == '\n' {
            line += 1;
            index += 1;
            continue;
        }
        if character.is_whitespace() {
            index += 1;
            continue;
        }
        let next = characters.get(index + 1).copied();
        if character == '/' && next == Some('/') {
            while index < size && characters[index] != '\n' {
                index += 1;
            }
            continue;
        }
        if character == '/' && next == Some('*') {
            let start_line = line;
            index += 2;
            loop {
                if index + 1 >= size {
                    return Err(format!("{origin}: unterminated block comment{}", at(start_line)));
                }
                if characters[index] == '*' && characters[index + 1] == '/' {
                    index += 2;
                    break;
                }
                if characters[index] == '\n' {
                    line += 1;
                }
                index += 1;
            }
            continue;
        }
        if character == '"' || character == '\'' || character == '`' {
            let mut body = String::new();
            let mut cursor = index + 1;
            loop {
                if cursor >= size {
                    return Err(format!("{origin}: unterminated string{}", at(line)));
                }
                let inner = characters[cursor];
                if inner == '\\' {
                    cursor += 2;
                    continue;
                }
                if inner == character {
                    break;
                }
                if inner == '\n' {
                    line += 1;
                }
                body.push(inner);
                cursor += 1;
            }
            tokens.push(Token { kind: Kind::Str, value: body, line });
            index = cursor + 1;
            continue;
        }
        if identifier_start(character) {
            let start = index;
            index += 1;
            while index < size && identifier_part(characters[index]) {
                index += 1;
            }
            tokens.push(Token { kind: Kind::Name, value: characters[start..index].iter().collect(), line });
            continue;
        }
        let number_start = character.is_ascii_digit() || (character == '.' && next.is_some_and(|c| c.is_ascii_digit()));
        if number_start {
            let start = index;
            index += 1;
            while index < size && (characters[index].is_alphanumeric() || characters[index] == '_' || characters[index] == '.') {
                index += 1;
            }
            tokens.push(Token { kind: Kind::Num, value: characters[start..index].iter().collect(), line });
            continue;
        }
        tokens.push(Token { kind: Kind::Punct, value: character.to_string(), line });
        index += 1;
    }
    Ok(tokens)
}

/// Every bracket's partner index; an imbalance is an error.
pub fn match_brackets(tokens: &[Token], origin: &str) -> Result<HashMap<usize, usize>, String> {
    let mut stack: Vec<usize> = Vec::new();
    let mut partner = HashMap::new();
    for (index, token) in tokens.iter().enumerate().filter(|(_, token)| token.kind == Kind::Punct) {
        if closer_of(&token.value).is_some() {
            stack.push(index);
        } else if let Some(expected_open) = opener_of(&token.value) {
            let open = stack.pop().ok_or_else(|| format!("{origin}: stray '{}'{}", token.value, at(token.line)))?;
            if tokens[open].value != expected_open {
                return Err(format!(
                    "{origin}: '{}'{} closed by '{}'{}",
                    tokens[open].value,
                    at(tokens[open].line),
                    token.value,
                    at(token.line)
                ));
            }
            partner.insert(open, index);
            partner.insert(index, open);
        }
    }
    if let Some(open) = stack.last() {
        return Err(format!("{origin}: unclosed '{}'{}", tokens[*open].value, at(tokens[*open].line)));
    }
    Ok(partner)
}

/// Indices in `start..stop` whose immediate enclosing bracket group is the caller's own.
pub fn walk(tokens: &[Token], partner: &HashMap<usize, usize>, start: usize, stop: usize) -> Vec<usize> {
    let mut found = Vec::new();
    let mut index = start;
    while index < stop {
        found.push(index);
        index = if tokens[index].is_opener() { partner[&index] + 1 } else { index + 1 };
    }
    found
}

/// End of a declaration, plus every brace group opened at its own level.
/// With `stop_at_body`, the first brace group ends it (a function or class body).
pub fn statement_end(tokens: &[Token], partner: &HashMap<usize, usize>, cursor: usize, stop_at_body: bool) -> (usize, Vec<usize>) {
    let size = tokens.len();
    let mut braces = Vec::new();
    let mut index = cursor;
    while index < size {
        let token = &tokens[index];
        if token.is_punct("{") {
            braces.push(index);
            index = partner[&index] + 1;
            if stop_at_body {
                if index < size && tokens[index].is_punct(";") {
                    index += 1;
                }
                return (index, braces);
            }
            continue;
        }
        if token.is_opener() {
            index = partner[&index] + 1;
            continue;
        }
        if token.is_punct(";") {
            return (index + 1, braces);
        }
        index += 1;
    }
    (size, braces)
}
