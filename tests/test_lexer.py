import pytest

from crud.lexer import LexError, TokenType as T, tokenize


def types(src):
    return [t.type for t in tokenize(src)]


def values(src):
    return [t.value for t in tokenize(src) if t.type != T.EOF]


def test_token_dasar():
    assert types("SELECT id FROM t;") == [T.KEYWORD, T.IDENT, T.KEYWORD, T.IDENT, T.SEMICOLON, T.EOF]


def test_keyword_huruf_kecil():
    toks = tokenize("select id from t")
    assert toks[0].type == T.KEYWORD and toks[0].value == "SELECT"
    assert toks[2].type == T.KEYWORD and toks[2].value == "FROM"


def test_operator_multi_karakter():
    assert values("a <= 1 >= 2 != 3") == ["a", "<=", "1", ">=", "2", "!=", "3"]


def test_parameter():
    toks = tokenize("? :id :batas_awal")
    assert [t.type for t in toks[:3]] == [T.PARAM, T.PARAM, T.PARAM]
    assert [t.value for t in toks[:3]] == ["?", ":id", ":batas_awal"]


def test_komentar_baris():
    toks = tokenize("-- hapus data lama\nSELECT")
    assert toks[0].value == "SELECT" and toks[0].line == 2


def test_komentar_blok():
    toks = tokenize("/* komentar\n   dua baris */ SELECT")
    assert toks[0].value == "SELECT" and toks[0].line == 2


def test_string_biasa():
    toks = tokenize("'LUNAS'")
    assert toks[0].type == T.STRING and toks[0].value == "LUNAS"


def test_posisi_token():
    toks = tokenize("SELECT a\n  FROM t")
    assert (toks[2].line, toks[2].col) == (2, 3)


def test_karakter_tidak_dikenal():
    with pytest.raises(LexError) as info:
        tokenize("SELECT\n$")
    assert info.value.line == 2
