from crud import ast_nodes as ast
from crud.parser import parse_sql


def one(sql):
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    assert len(script.statements) == 1
    return script.statements[0]


def test_select_sederhana():
    s = one("SELECT id, nama FROM pelanggan;")
    assert isinstance(s, ast.Select)
    assert [c.expr.name for c in s.columns] == ["id", "nama"]
    assert s.sources[0].name == "pelanggan"


def test_alias_dengan_dan_tanpa_as():
    s = one("SELECT p.id FROM pelanggan AS p, pesanan o")
    assert [(t.name, t.alias) for t in s.sources] == [("pelanggan", "p"), ("pesanan", "o")]


def test_nama_tabel_berskema():
    s = one("SELECT id FROM CRM.Pelanggan")
    assert s.sources[0].name == "crm.pelanggan"


def test_left_join():
    s = one("SELECT a.id FROM a LEFT JOIN b ON b.a_id = a.id")
    assert s.joins[0].kind == "LEFT"
    assert s.joins[0].source.name == "b"


def test_where_and():
    s = one("SELECT id FROM t WHERE a = 1 AND b = 2")
    assert isinstance(s.where, ast.BinaryOp) and s.where.op == "AND"


def test_star_dan_perkalian():
    assert isinstance(one("SELECT * FROM t").columns[0], ast.Star)
    expr = one("SELECT harga * qty FROM t").columns[0].expr
    assert isinstance(expr, ast.BinaryOp) and expr.op == "*"


def test_insert_values():
    s = one("INSERT INTO log (id, pesan) VALUES (1, 'ok'), (2, 'gagal')")
    assert isinstance(s, ast.Insert)
    assert s.columns == ["id", "pesan"] and len(s.values) == 2 and s.query is None


def test_insert_select():
    s = one("INSERT INTO arsip (id) SELECT id FROM pesanan WHERE total > 10")
    assert isinstance(s, ast.Insert)
    assert s.columns == ["id"]
    assert isinstance(s.query, ast.Select) and s.query.sources[0].name == "pesanan"


def test_update():
    s = one("UPDATE pelanggan SET nama = 'x', level = 2 WHERE id = :id")
    assert isinstance(s, ast.Update)
    assert [a.column.name for a in s.assignments] == ["nama", "level"]


def test_delete():
    s = one("DELETE FROM sesi s WHERE s.id = ?")
    assert isinstance(s, ast.Delete) and s.table.alias == "s"


def test_subquery_in():
    s = one("SELECT id FROM a WHERE id IN (SELECT a_id FROM b)")
    assert isinstance(s.where, ast.InExpr) and s.where.query.sources[0].name == "b"


def test_pesan_error_berisi_baris():
    script = parse_sql("SELECT id\nFROM\n;")
    assert len(script.errors) == 1
    assert script.errors[0].line == 3
