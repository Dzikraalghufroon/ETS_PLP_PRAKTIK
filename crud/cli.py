"""Antarmuka baris perintah.

Contoh:
    python -m crud.cli data/sample/*.sql --out crud_matrix.csv --detail detail.csv
    python -m crud.cli data/sample/audit.sql --ast
"""
import argparse
import csv
import sys
from pathlib import Path

from .ast_nodes import pretty
from .parser import parse_sql
from .pipeline import analyze_source
from .resolver import Resolver


def _print_ast(path: Path) -> None:
    script = parse_sql(path.read_text(encoding="utf-8"))
    Resolver().resolve_script(script)
    for stmt in script.statements:
        print(f"--- baris {stmt.line} ---")
        print(pretty(stmt))
    for err in script.errors:
        print(f"PARSE ERROR: {err}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ekstraktor CRUD matrix dari file SQL")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("crud_matrix.csv"), help="CRUD matrix per file")
    ap.add_argument("--detail", type=Path, help="CSV per statement: file,baris,jenis,tabel,operasi")
    ap.add_argument("--kolom", type=Path, help="CSV penggunaan kolom: file,baris,tabel,kolom,operasi")
    ap.add_argument("--ast", action="store_true", help="cetak AST (setelah resolusi), lalu keluar")
    args = ap.parse_args(argv)

    if args.ast:
        for path in args.files:
            print(f"===== {path} =====")
            _print_ast(path)
        return 0

    had_error = False
    results = {}
    for path in args.files:
        res = analyze_source(path.read_text(encoding="utf-8"))
        results[path.name] = res
        if res.lex_error:
            had_error = True
            print(f"{path.name}: LEX ERROR: {res.lex_error}", file=sys.stderr)
        for err in res.parse_errors:
            had_error = True
            print(f"{path.name}: PARSE ERROR: {err}", file=sys.stderr)
        for diag in res.diagnostics:
            print(f"{path.name}: {diag}", file=sys.stderr)

    tables = sorted({t for r in results.values() for t in r.matrix()})
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", *tables])
        for name, res in results.items():
            m = res.matrix()
            w.writerow([name, *[m.get(t, "") for t in tables]])
    print(f"CRUD matrix ditulis ke {args.out}")

    if args.detail:
        with args.detail.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "baris", "jenis", "tabel", "operasi"])
            for name, res in results.items():
                for st in res.statements:
                    for table, ops in st.tables.items():
                        w.writerow([name, st.line, st.kind, table, ops])
        print(f"Detail per statement ditulis ke {args.detail}")

    if args.kolom:
        with args.kolom.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "baris", "tabel", "kolom", "operasi"])
            for name, res in results.items():
                for st in res.statements:
                    for table, col, op in sorted(st.columns):
                        w.writerow([name, st.line, table, col, op])
        print(f"Penggunaan kolom ditulis ke {args.kolom}")

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
