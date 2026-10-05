//! Public declarations and their members, independent of module resolution.
//! `export declare class C { m(): void; }` and `export class C { m(): void {} }`
//! yield the same names.

use std::collections::{BTreeSet, HashMap};

use super::lexer::{at, statement_end, walk, Kind, Token};

/// A declaration keyword of JavaScript or TypeScript.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Keyword {
    Class,
    Interface,
    Type,
    Enum,
    Const,
    Let,
    Var,
    Function,
    Abstract,
}

impl Keyword {
    pub fn of(token: &Token) -> Option<Self> {
        if token.kind != Kind::Name {
            return None;
        }
        Some(match token.value.as_str() {
            "class" => Self::Class,
            "interface" => Self::Interface,
            "type" => Self::Type,
            "enum" => Self::Enum,
            "const" => Self::Const,
            "let" => Self::Let,
            "var" => Self::Var,
            "function" => Self::Function,
            "abstract" => Self::Abstract,
            _ => return None,
        })
    }

    fn spelled(self) -> &'static str {
        match self {
            Self::Class => "class",
            Self::Interface => "interface",
            Self::Type => "type",
            Self::Enum => "enum",
            Self::Const => "const",
            Self::Let => "let",
            Self::Var => "var",
            Self::Function => "function",
            Self::Abstract => "abstract",
        }
    }

    /// Declarations whose brace group holds their members.
    fn has_member_body(self) -> bool {
        matches!(self, Self::Class | Self::Interface | Self::Enum)
    }

    /// Declarations a brace group ends. A type alias always ends at a
    /// semicolon: its braces are its members, not its body.
    fn body_terminated(self) -> bool {
        self.has_member_body() || matches!(self, Self::Function | Self::Const | Self::Let | Self::Var)
    }

    fn is_binding(self) -> bool {
        matches!(self, Self::Const | Self::Let | Self::Var)
    }
}

/// A member modifier, and whether it hides the member from consumers.
enum Modifier {
    Visible,
    Hidden,
}

fn modifier(value: &str) -> Option<Modifier> {
    match value {
        "private" | "protected" => Some(Modifier::Hidden),
        "public" | "static" | "readonly" | "abstract" | "declare" | "async" | "override" | "get" | "set" => {
            Some(Modifier::Visible)
        }
        _ => None,
    }
}

pub struct Decl {
    pub name: String,
    pub members: Vec<String>,
}

/// A brace group split into member declarations at its own level.
fn segments(tokens: &[Token], partner: &HashMap<usize, usize>, open: usize, body_ends_member: bool) -> Vec<Vec<usize>> {
    let mut found = Vec::new();
    let mut current = Vec::new();
    for index in walk(tokens, partner, open + 1, partner[&open]) {
        let token = &tokens[index];
        if token.is_punct(";") || token.is_punct(",") {
            if !current.is_empty() {
                found.push(std::mem::take(&mut current));
            }
            continue;
        }
        current.push(index);
        if body_ends_member && token.is_punct("{") {
            found.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        found.push(current);
    }
    found
}

fn is_modifier(tokens: &[Token], segment: &[usize], cursor: usize) -> Option<Modifier> {
    let token = &tokens[segment[cursor]];
    if token.kind != Kind::Name {
        return None;
    }
    let kind = modifier(&token.value)?;
    let next = &tokens[*segment.get(cursor + 1)?];
    (matches!(next.kind, Kind::Name | Kind::Str) || next.is_punct("[")).then_some(kind)
}

/// Public member names of a class body (direct members only) or a type
/// literal (recursing, because `response.usage.totalTokens` is read as such).
fn collect_members(tokens: &[Token], partner: &HashMap<usize, usize>, open: usize, path: &[String], is_class: bool, out: &mut BTreeSet<String>) {
    for segment in segments(tokens, partner, open, is_class) {
        let mut cursor = 0;
        let mut hidden = false;
        while cursor < segment.len() {
            match is_modifier(tokens, &segment, cursor) {
                Some(Modifier::Hidden) => hidden = true,
                Some(Modifier::Visible) => {}
                None => break,
            }
            cursor += 1;
        }
        let Some(&head_index) = segment.get(cursor) else { continue };
        let head = &tokens[head_index];
        if !matches!(head.kind, Kind::Name | Kind::Str) {
            continue;
        }
        let name = &head.value;
        if name == "constructor" || name.starts_with('_') || name.starts_with('#') || hidden {
            continue;
        }
        let mut member_path = path.to_vec();
        member_path.push(name.clone());
        out.insert(member_path.join("."));
        if is_class {
            continue;
        }
        for later in &segment[cursor + 1..] {
            if tokens[*later].is_punct("{") {
                collect_members(tokens, partner, *later, &member_path, false, out);
            }
        }
    }
}

/// The declaration at `index` and the index after it; `None` for a bare `abstract`.
pub fn parse_decl(tokens: &[Token], partner: &HashMap<usize, usize>, index: usize, origin: &str) -> Result<(Option<Decl>, usize), String> {
    let size = tokens.len();
    let mut keyword = Keyword::of(&tokens[index]).ok_or_else(|| format!("{origin}: not a declaration{}", at(tokens[index].line)))?;
    let mut cursor = index + 1;
    if keyword == Keyword::Abstract {
        if cursor >= size || !tokens[cursor].is_name("class") {
            return Ok((None, cursor));
        }
        keyword = Keyword::Class;
        cursor += 1;
    }
    while cursor < size && tokens[cursor].is_name("declare") {
        cursor += 1;
    }
    if cursor >= size || tokens[cursor].kind != Kind::Name {
        let line = tokens[cursor.min(size - 1)].line;
        return Err(format!("{origin}: unnamed {} declaration{}", keyword.spelled(), at(line)));
    }
    let name = tokens[cursor].value.clone();
    cursor += 1;
    let (end, braces) = statement_end(tokens, partner, cursor, keyword.body_terminated());
    let mut members = BTreeSet::new();
    if keyword.has_member_body() {
        let body = braces.first().ok_or_else(|| format!("{origin}: {} {name} has no body", keyword.spelled()))?;
        collect_members(tokens, partner, *body, &[], keyword == Keyword::Class, &mut members);
    } else if keyword == Keyword::Type {
        for brace in &braces {
            collect_members(tokens, partner, *brace, &[], false, &mut members);
        }
    } else if keyword.is_binding() {
        if let Some(comma) = walk(tokens, partner, cursor, end).into_iter().find(|position| tokens[*position].is_punct(",")) {
            return Err(format!(
                "{origin}: several declarators in one '{}'{}; the surface would be under-reported, so this is refused rather than guessed",
                keyword.spelled(),
                at(tokens[comma].line)
            ));
        }
    }
    Ok((Some(Decl { name, members: members.into_iter().collect() }), end))
}

/// `[(exported name, source name)]` out of a `{ a, b as c, type d }` list.
pub fn parse_specifiers(tokens: &[Token], partner: &HashMap<usize, usize>, open: usize) -> Vec<(String, String)> {
    let mut pairs = Vec::new();
    for segment in segments(tokens, partner, open, false) {
        let mut words: Vec<&Token> = segment.iter().map(|position| &tokens[*position]).filter(|token| matches!(token.kind, Kind::Name | Kind::Str)).collect();
        if words.len() > 1 && words[0].is_name("type") {
            words.remove(0);
        }
        let Some(first) = words.first() else { continue };
        let source = first.value.clone();
        let exported = if words.len() >= 3 && words[1].value == "as" { words[2].value.clone() } else { source.clone() };
        pairs.push((exported, source));
    }
    pairs
}
