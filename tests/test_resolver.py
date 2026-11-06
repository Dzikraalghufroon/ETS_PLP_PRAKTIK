from crud import ast_nodes as ast
from crud.parser import parse_sql
from crud.resolver import Resolver


def resolve(sql):
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    diagnostics = Resolver().resolve_script(script)
    return script, diagnostics


def columns(node):
    return [n for n in ast.iter_nodes(node) if isinstance(n, ast.ColumnRef)]


def test_alias_qualified_teresolusi():
    script, diags = resolve("SELECT p.nama FROM pelanggan p JOIN pesanan o ON o.pelanggan_id = p.id")
    resolved = {(c.qualifier, c.name): c.resolved for c in columns(script)}
    assert resolved[("p", "nama")] == "pelanggan"
    assert resolved[("o", "pelanggan_id")] == "pesanan"
    assert diags == []


def test_alias_tidak_terdefinisi():
    _, diags = resolve("SELECT q.nama FROM pelanggan p")
    assert [d.level for d in diags] == ["error"]
    assert "'q'" in diags[0].message


def test_kolom_tanpa_qualifier_satu_tabel():
    script, diags = resolve("SELECT nama FROM pelanggan WHERE aktif = 1")
    assert {c.resolved for c in columns(script)} == {"pelanggan"}
    assert diags == []


def test_subquery_in_alias_dalam():
    script, diags = resolve(
        "SELECT p.id FROM pelanggan p WHERE p.id IN (SELECT o.pelanggan_id FROM pesanan o)")
    inner = [c for c in columns(script) if c.qualifier == "o"][0]
    assert inner.resolved == "pesanan"
    assert diags == []
