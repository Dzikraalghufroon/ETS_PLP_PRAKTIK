"""Lexer untuk subset SQL. Aturan lengkap: SPESIFIKASI.md bagian 2."""
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()
    IDENT = auto()
    NUMBER = auto()
    STRING = auto()
    PARAM = auto()
    OP = auto()          # = <> != < <= > >= + - /
    STAR = auto()        # * : "semua kolom" atau perkalian, dibedakan oleh parser
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    DOT = auto()
    SEMICOLON = auto()
    EOF = auto()


KEYWORDS = frozenset({
    "SELECT", "DISTINCT", "FROM", "WHERE", "AS", "JOIN", "INNER", "LEFT",
    "OUTER", "ON", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "AND", "OR", "NOT", "IN", "EXISTS", "IS", "NULL", "LIKE", "BETWEEN",
    "GROUP", "ORDER", "BY", "ASC", "DESC",
})

_SINGLE = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    ",": TokenType.COMMA,
    ".": TokenType.DOT,
    ";": TokenType.SEMICOLON,
    "*": TokenType.STAR,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


class LexError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Baris {line}, kolom {col}: {message}")
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        while not self._at_end():
            self._scan_token()
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    # ---- helper ---------------------------------------------------------
    def _at_end(self) -> bool:
        return self.pos >= len(self.src)

    def _peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else "\0"

    def _advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self._peek() == expected:
            self._advance()
            return True
        return False

    def _add(self, type_: TokenType, value: str, line: int, col: int) -> None:
        self.tokens.append(Token(type_, value, line, col))

    # ---- pemindaian -----------------------------------------------------
    def _scan_token(self) -> None:
        line, col = self.line, self.col
        ch = self._advance()

        if ch in " \t\r\n":
            return
        if ch == "-" and self._peek() == "-":
            while not self._at_end() and self._peek() != "\n":
                self._advance()
            return
        if ch == "/" and self._peek() == "*":
            # TODO(T3): dukung komentar blok /* ... */ (SPESIFIKASI.md bagian 2.3).
            raise LexError("komentar blok belum didukung", line, col)
        if ch in _SINGLE:
            self._add(_SINGLE[ch], ch, line, col)
            return
        if ch in "+-/=":
            self._add(TokenType.OP, ch, line, col)
            return
        if ch == "<":
            op = "<=" if self._match("=") else "<"
            self._add(TokenType.OP, op, line, col)
            return
        if ch == ">":
            op = ">=" if self._match("=") else ">"
            self._add(TokenType.OP, op, line, col)
            return
        if ch == "!":
            if self._match("="):
                self._add(TokenType.OP, "!=", line, col)
                return
            raise LexError("karakter '!' harus diikuti '='", line, col)
        if ch == "'":
            self._string(line, col)
            return
        if ch == "?":
            self._add(TokenType.PARAM, "?", line, col)
            return
        if ch == ":":
            if self._peek().isalpha() or self._peek() == "_":
                start = self.pos
                while self._peek().isalnum() or self._peek() == "_":
                    self._advance()
                self._add(TokenType.PARAM, ":" + self.src[start:self.pos], line, col)
                return
            raise LexError("parameter ':' harus diikuti nama", line, col)
        if ch.isdigit():
            self._number(line, col)
            return
        if ch.isalpha() or ch == "_":
            self._word(line, col)
            return
        raise LexError(f"karakter tidak dikenal {ch!r}", line, col)

    def _string(self, line: int, col: int) -> None:
        chars: list[str] = []
        while True:
            if self._at_end():
                raise LexError("string tidak ditutup", line, col)
            ch = self._advance()
            if ch == "'":
                break
            chars.append(ch)
        self._add(TokenType.STRING, "".join(chars), line, col)

    def _number(self, line: int, col: int) -> None:
        start = self.pos - 1
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek(1).isdigit():
            self._advance()
            while self._peek().isdigit():
                self._advance()
        self._add(TokenType.NUMBER, self.src[start:self.pos], line, col)

    def _word(self, line: int, col: int) -> None:
        start = self.pos - 1
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        text = self.src[start:self.pos]
        if text in KEYWORDS:
            self._add(TokenType.KEYWORD, text, line, col)
        else:
            self._add(TokenType.IDENT, text, line, col)


def tokenize(source: str) -> list[Token]:
    return Lexer(source).tokenize()
