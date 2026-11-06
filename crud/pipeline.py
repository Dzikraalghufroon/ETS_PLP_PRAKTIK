"""Menjalankan seluruh pipeline: lexer -> parser -> resolver -> analyzer."""
from dataclasses import dataclass, field

from .analyzer import analyze_statement, column_usage
from .lexer import LexError
from .parser import parse_sql
from .resolver import Resolver

CRUD_ORDER = "CRUD"


def format_ops(ops) -> str:
    """{'U', 'R'} -> 'RU' (selalu urut C, R, U, D)."""
    return "".join(c for c in CRUD_ORDER if c in ops)


@dataclass
class StatementResult:
    line: int
    kind: str                         # SELECT, INSERT, UPDATE, DELETE
    tables: dict[str, str]            # tabel -> operasi, misalnya {"pesanan": "R"}
    columns: set = field(default_factory=set)


@dataclass
class FileResult:
    statements: list
    parse_errors: list
    diagnostics: list
    lex_error: LexError | None = None

    def matrix(self) -> dict[str, str]:
        """CRUD matrix level file: gabungan operasi semua statement."""
        merged: dict[str, set[str]] = {}
        for st in self.statements:
            for table, ops in st.tables.items():
                merged.setdefault(table, set()).update(ops)
        return {t: format_ops(o) for t, o in sorted(merged.items())}


def analyze_source(text: str) -> FileResult:
    try:
        script = parse_sql(text)
    except LexError as err:
        return FileResult([], [], [], err)
    diagnostics = Resolver().resolve_script(script)
    results = []
    for stmt in script.statements:
        usage = analyze_statement(stmt)
        results.append(StatementResult(
            line=stmt.line,
            kind=type(stmt).__name__.upper(),
            tables={t: format_ops(o) for t, o in sorted(usage.items())},
            columns=column_usage(stmt),
        ))
    return FileResult(results, script.errors, diagnostics)
