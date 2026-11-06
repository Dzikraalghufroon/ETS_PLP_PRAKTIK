"""Test tambahan buatan kelompok.

1. Satu test regresi untuk setiap bug yang diperbaiki (gagal sebelum perbaikan, lulus sesudahnya).
2. Lima test kasus tepi dengan penjelasan risiko kasus tersebut.
"""
import pytest
from crud import ast_nodes as ast
from crud.analyzer import analyze_statement
from crud.lexer import LexError, TokenType as T, tokenize
from crud.parser import parse_sql
from crud.pipeline import analyze_source
from crud.resolver import Resolver


def parse_one(sql: str):
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    assert len(script.statements) == 1
    return script.statements[0]


# ==============================================================================
# 1. TEST REGRESI UNTUK SETIAP BUG
# ==============================================================================

def test_regresi_keyword_case_insensitive():
    """Bug 1: Keyword huruf kecil/campuran harus dikenali sebagai KEYWORD dinormalisasi ke huruf besar."""
    tokens = tokenize("select u.id From users u where u.active = 1")
    keywords = [(t.type, t.value) for t in tokens if t.type == T.KEYWORD]
    assert keywords == [(T.KEYWORD, "SELECT"), (T.KEYWORD, "FROM"), (T.KEYWORD, "WHERE")]


def test_regresi_operator_tidak_sama_dengan():
    """Bug 2: Operator '<>' harus di-lex sebagai satu token OP, bukan dua token terpisah ('<' dan '>')."""
    tokens = tokenize("status <> 'CLOSED'")
    ops = [t.value for t in tokens if t.type == T.OP]
    assert ops == ["<>"]


def test_regresi_string_kutip_ganda_escaped():
    """Bug 3: Karakter kutip tunggal ganda di dalam string ('') harus di-lex sebagai satu karakter kutip tunggal."""
    tokens = tokenize("'O''Brien dan O''Neil'")
    assert tokens[0].type == T.STRING
    assert tokens[0].value == "O'Brien dan O'Neil"


def test_regresi_presedensi_and_or():
    """Bug 4: AND memiliki presedensi lebih tinggi daripada OR (a OR b AND c -> a OR (b AND c))."""
    stmt = parse_one("SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3")
    # Root WHERE clause harus berupa BinaryOp 'OR'
    assert isinstance(stmt.where, ast.BinaryOp)
    assert stmt.where.op == "OR"
    # Sisi kanan dari 'OR' harus berupa BinaryOp 'AND'
    assert isinstance(stmt.where.right, ast.BinaryOp)
    assert stmt.where.right.op == "AND"


def test_regresi_panic_mode_lanjut_setelah_semicolon():
    """Bug 5: Panic mode pada parser harus berhenti di titik koma ';' dan melanjutkan statement berikutnya."""
    sql = "SELECT id FROM ; SELECT id FROM valid_table;"
    script = parse_sql(sql)
    assert len(script.errors) == 1
    assert len(script.statements) == 1
    assert script.statements[0].sources[0].name == "valid_table"


def test_regresi_left_outer_join():
    """Bug 6: Parser harus mendukung LEFT OUTER JOIN sesuai grammar, bukan hanya LEFT JOIN."""
    stmt = parse_one("SELECT a.id FROM a LEFT OUTER JOIN b ON b.a_id = a.id")
    assert len(stmt.joins) == 1
    assert stmt.joins[0].kind == "LEFT"
    assert stmt.joins[0].source.name == "b"


def test_regresi_scope_lookup_innermost_first():
    """Bug 7: Pencarian scope harus dimulai dari scope terdalam ke luar (shadowing)."""
    sql = "SELECT x.id FROM luar x WHERE x.id IN (SELECT x.id FROM dalam x)"
    script = parse_sql(sql)
    diags = Resolver().resolve_script(script)
    assert diags == []

    # Kolom x.id di dalam subquery harus ter-resolve ke 'dalam', bukan 'luar'
    inner_in = script.statements[0].where
    inner_select = inner_in.query
    inner_col = inner_select.columns[0].expr
    assert inner_col.resolved == "dalam"


def test_regresi_delete_scope_tidak_bocor():
    """Bug 8: Scope dari statement DELETE harus di-pop agar tidak bocor ke statement berikutnya."""
    sql = "DELETE FROM sesi s WHERE s.id = 1; SELECT s.id FROM user u;"
    script = parse_sql(sql)
    diags = Resolver().resolve_script(script)
    # Statement kedua tidak memiliki alias 's', sehingga harus menghasilkan error diagnostik
    assert any(d.level == "error" and "'s'" in d.message for d in diags)


def test_regresi_update_subquery_operasi_read():
    """Bug 9: Subquery di dalam UPDATE (baik SET maupun WHERE) harus dicatat sebagai operasi 'R', bukan 'U'."""
    sql = "UPDATE pelanggan SET level = 'gold' WHERE id IN (SELECT pelanggan_id FROM pesanan);"
    stmt = parse_one(sql)
    usage = analyze_statement(stmt)
    assert usage["pelanggan"] == {"U"}
    assert usage["pesanan"] == {"R"}
