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

# ==============================================================================
# 2. TEST KASUS TEPI (EDGE CASES)
# ==============================================================================

def test_kasus_tepi_komentar_blok_tidak_ditutup():
    """Kasus Tepi 1: Komentar blok yang tidak ditutup harus menghasilkan LexError pada baris dimulainya komentar.
    Risiko: Tanpa pengecekan ketat, parser bisa terus memindai sampai EOF dan menelan seluruh sisa kode."""
    with pytest.raises(LexError) as exc_info:
        tokenize("/* ini komentar yang lupa ditutup\nSELECT * FROM t;")
    assert "komentar blok tidak ditutup" in str(exc_info.value)
    assert exc_info.value.line == 1


def test_kasus_tepi_subquery_from_tanpa_alias_warning():
    """Kasus Tepi 2: Subquery di klausa FROM tanpa alias harus memunculkan warning diagnostik.
    Risiko: Subquery turunan tanpa alias tidak dapat dirujuk oleh qualifier kolom mana pun."""
    sql = "SELECT x FROM (SELECT id FROM users);"
    script = parse_sql(sql)
    diags = Resolver().resolve_script(script)
    assert any(d.level == "warning" and "tanpa alias" in d.message for d in diags)


def test_kasus_tepi_kolom_tanpa_qualifier_ambigu_dua_tabel():
    """Kasus Tepi 3: Kolom tanpa qualifier jika ada lebih dari 1 tabel di scope harus warning dan resolved = None.
    Risiko: Jika parser/resolver salah memilih tabel secara asal, CRUD matrix dan analisis kolom akan salah."""
    sql = "SELECT nama FROM pelanggan p, pengguna u;"
    script = parse_sql(sql)
    diags = Resolver().resolve_script(script)
    assert any(d.level == "warning" and "ambigu" in d.message for d in diags)
    col = script.statements[0].columns[0].expr
    assert col.resolved is None


def test_kasus_tepi_titik_koma_berulang_dan_kosong():
    """Kasus Tepi 4: Skrip dengan titik koma berturut-turut atau di awal/akhir file.
    Risiko: Parser rekursif dapat mengalami crash atau mendeteksi error tak terduga pada empty statement."""
    sql = ";; SELECT 1 FROM t;; ;"
    script = parse_sql(sql)
    assert script.errors == []
    assert len(script.statements) == 1
    assert script.statements[0].sources[0].name == "t"


def test_kasus_tepi_insert_select_kompleks_dengan_join_dan_where():
    """Kasus Tepi 5: INSERT INTO ... SELECT yang menggabungkan JOIN dan subquery di WHERE.
    Risiko: Analisis tabel bisa tertukar antara tabel target C dan tabel-tabel sumber R dalam query berlapis."""
    sql = """
    INSERT INTO arsip (id, total)
    SELECT p.id, p.total
    FROM pesanan p
    JOIN pelanggan c ON c.id = p.pelanggan_id
    WHERE p.total > (SELECT AVG(nominal) FROM batas);
    """
    res = analyze_source(sql)
    assert res.parse_errors == []
    matrix = res.matrix()
    assert matrix == {
        "arsip": "C",
        "batas": "R",
        "pelanggan": "R",
        "pesanan": "R",
    }