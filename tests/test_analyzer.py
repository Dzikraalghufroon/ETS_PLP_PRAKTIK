from pathlib import Path

from crud.analyzer import analyze_statement
from crud.parser import parse_sql
from crud.pipeline import analyze_source

DATA = Path(__file__).resolve().parents[1] / "data" / "sample"


def crud(sql):
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    return analyze_statement(script.statements[0])


def test_crud_select_join():
    assert crud("SELECT p.id FROM pelanggan p JOIN pesanan o ON o.pelanggan_id = p.id") == {
        "pelanggan": {"R"}, "pesanan": {"R"}}


def test_crud_insert_values():
    assert crud("INSERT INTO log (id) VALUES (1)") == {"log": {"C"}}


def test_crud_update_sederhana():
    assert crud("UPDATE produk SET stok = stok - 1 WHERE id = 3") == {"produk": {"U"}}


def test_crud_delete():
    assert crud("DELETE FROM sesi WHERE dibuat < :batas") == {"sesi": {"D"}}


def test_matrix_laporan_penjualan():
    res = analyze_source((DATA / "laporan_penjualan.sql").read_text(encoding="utf-8"))
    assert res.lex_error is None and res.parse_errors == []
    assert res.matrix() == {"arsip_pesanan": "C", "pelanggan": "RU", "pesanan": "RD"}
