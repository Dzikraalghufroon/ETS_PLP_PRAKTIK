"""Node AST untuk subset SQL. Struktur node adalah bagian dari API publik
(SPESIFIKASI.md bagian 7): jangan ganti nama kelas atau field."""
from dataclasses import dataclass, field, fields, is_dataclass


# ---- statement ----------------------------------------------------------
@dataclass
class Script:
    statements: list
    errors: list            # daftar ParseError


@dataclass
class Select:
    distinct: bool
    columns: list           # SelectItem atau Star
    sources: list           # TableRef atau DerivedTable (dipisah koma)
    joins: list = field(default_factory=list)
    where: object = None
    group_by: list = field(default_factory=list)
    order_by: list = field(default_factory=list)
    line: int = 0


@dataclass
class Insert:
    table: "TableRef"
    columns: list           # nama kolom (str), boleh kosong
    values: list            # list baris; tiap baris = list ekspresi
    query: "Select | None" = None
    line: int = 0


@dataclass
class Update:
    table: "TableRef"
    assignments: list
    where: object = None
    line: int = 0


@dataclass
class Delete:
    table: "TableRef"
    where: object = None
    line: int = 0


# ---- bagian dari statement ----------------------------------------------
@dataclass
class SelectItem:
    expr: object
    alias: str | None = None


@dataclass
class Star:
    pass


@dataclass
class TableRef:
    name: str               # huruf kecil, lengkap dengan skema: "crm.pelanggan"
    alias: str | None = None
    line: int = 0


@dataclass
class DerivedTable:
    query: Select
    alias: str | None = None
    line: int = 0


@dataclass
class Join:
    kind: str               # "INNER" atau "LEFT"
    source: object          # TableRef atau DerivedTable
    condition: object
    line: int = 0


@dataclass
class Assignment:
    column: "ColumnRef"
    value: object


@dataclass
class OrderItem:
    expr: object
    direction: str = "ASC"


# ---- ekspresi -----------------------------------------------------------
@dataclass
class BinaryOp:
    left: object
    op: str                 # "OR", "AND", "=", "<>", "!=", "<", "<=", ">", ">=", "+", "-", "*", "/", "LIKE"
    right: object


@dataclass
class UnaryOp:
    op: str                 # "NOT" atau "-"
    operand: object


@dataclass
class InExpr:
    expr: object
    values: list | None     # IN (1, 2, 3)
    query: Select | None    # IN (SELECT ...)
    negated: bool = False


@dataclass
class Between:
    expr: object
    low: object
    high: object
    negated: bool = False


@dataclass
class IsNull:
    expr: object
    negated: bool = False


@dataclass
class Exists:
    query: Select


@dataclass
class Subquery:
    query: Select           # subquery skalar: (SELECT ...)


@dataclass
class FunctionCall:
    name: str               # huruf besar
    args: list
    star: bool = False      # COUNT(*)


@dataclass
class ColumnRef:
    qualifier: str | None   # "p" pada p.nama; None jika tanpa qualifier
    name: str
    line: int = 0
    # Diisi resolver: nama tabel lengkap, "<subquery alias>", atau None.
    resolved: str | None = field(default=None, compare=False, repr=False)


@dataclass
class Literal:
    value: str | None
    kind: str               # "number", "string", "null"


@dataclass
class Param:
    name: str               # "?" atau ":nama"


# ---- utilitas -----------------------------------------------------------
def iter_nodes(node):
    """Menelusuri node dan seluruh keturunannya (pre-order)."""
    if isinstance(node, list):
        for item in node:
            yield from iter_nodes(item)
        return
    if not is_dataclass(node):
        return
    yield node
    for f in fields(node):
        if f.name == "resolved":
            continue
        yield from iter_nodes(getattr(node, f.name))


def pretty(node, indent: int = 0) -> str:
    """Mencetak AST sebagai pohon berindentasi, untuk latihan prediksi."""
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            return pad + "[]"
        return "\n".join(pretty(item, indent) for item in node)
    if not is_dataclass(node):
        return pad + repr(node)
    simple, nested = [], []
    for f in fields(node):
        if f.name in ("line", "errors"):
            continue
        value = getattr(node, f.name)
        if is_dataclass(value) or (isinstance(value, list) and value and is_dataclass(value[0])):
            nested.append((f.name, value))
        elif f.name == "resolved":
            if value is not None:
                simple.append(f"-> {value}")
        elif value not in (None, [], False):
            simple.append(f"{f.name}={value!r}")
    head = pad + type(node).__name__ + (" " + " ".join(simple) if simple else "")
    lines = [head]
    for name, value in nested:
        lines.append(pad + "  " + name + ":")
        lines.append(pretty(value, indent + 2))
    return "\n".join(lines)
