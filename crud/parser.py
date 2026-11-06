"""Parser recursive descent untuk subset SQL.

Grammar lengkap ada di SPESIFIKASI.md bagian 3. Setiap fungsi `_nama`
kurang lebih berpadanan dengan satu aturan grammar.
"""
from . import ast_nodes as ast
from .lexer import Token, TokenType as T, tokenize

COMPARISON_OPS = {"=", "<>", "!=", "<", "<=", ">", ">="}


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        found = "akhir input" if token.type == T.EOF else repr(token.value)
        super().__init__(f"Baris {token.line}, kolom {token.col}: {message}, ditemukan {found}")
        self.line = token.line
        self.col = token.col
        self.token = token


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ---- helper ---------------------------------------------------------
    def _peek(self, offset: int = 0) -> Token:
        i = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[i]

    def _at_end(self) -> bool:
        return self._peek().type == T.EOF

    def _advance(self) -> Token:
        tok = self._peek()
        if not self._at_end():
            self.pos += 1
        return tok

    def _check(self, type_: T, value: str | None = None) -> bool:
        tok = self._peek()
        return tok.type == type_ and (value is None or tok.value == value)

    def _check_kw(self, *words: str) -> bool:
        tok = self._peek()
        return tok.type == T.KEYWORD and tok.value in words

    def _next_is_select(self) -> bool:
        nxt = self._peek(1)
        return nxt.type == T.KEYWORD and nxt.value == "SELECT"

    def _match(self, type_: T, value: str | None = None) -> bool:
        if self._check(type_, value):
            self._advance()
            return True
        return False

    def _match_kw(self, *words: str) -> Token | None:
        if self._check_kw(*words):
            return self._advance()
        return None

    def _expect(self, type_: T, what: str, value: str | None = None) -> Token:
        if self._check(type_, value):
            return self._advance()
        raise ParseError(f"diharapkan {what}", self._peek())

    def _expect_kw(self, word: str) -> Token:
        return self._expect(T.KEYWORD, word, word)

    def _expect_ident(self, what: str) -> Token:
        return self._expect(T.IDENT, what)

    # ---- script ---------------------------------------------------------
    def parse_script(self) -> ast.Script:
        statements, errors = [], []
        while not self._at_end():
            if self._match(T.SEMICOLON):
                continue
            try:
                stmt = self._statement()
                if not self._at_end():
                    self._expect(T.SEMICOLON, "';' di akhir statement")
                statements.append(stmt)
            except ParseError as err:
                errors.append(err)
                self._synchronize()
        return ast.Script(statements, errors)

    def _synchronize(self) -> None:
        # Panic mode (Crafting Interpreters bab 6): buang token sampai
        # titik aman, lalu lanjutkan parsing.
        while not self._at_end():
            self._advance()

    def _statement(self):
        if self._check_kw("SELECT"):
            return self._select()
        if self._check_kw("INSERT"):
            return self._insert()
        if self._check_kw("UPDATE"):
            return self._update()
        if self._check_kw("DELETE"):
            return self._delete()
        raise ParseError("diharapkan awal statement (SELECT, INSERT, UPDATE, DELETE)", self._peek())

    # ---- SELECT ---------------------------------------------------------
    def _select(self) -> ast.Select:
        start = self._expect_kw("SELECT")
        distinct = self._match_kw("DISTINCT") is not None
        columns = self._select_list()
        self._expect_kw("FROM")
        sources = [self._table_ref()]
        while self._match(T.COMMA):
            sources.append(self._table_ref())
        joins = []
        while self._check_kw("JOIN", "INNER", "LEFT"):
            joins.append(self._join())
        where = self._expr() if self._match_kw("WHERE") else None
        group_by = []
        if self._match_kw("GROUP"):
            self._expect_kw("BY")
            group_by = self._expr_list()
        order_by = []
        if self._match_kw("ORDER"):
            self._expect_kw("BY")
            order_by = self._order_list()
        return ast.Select(distinct=distinct, columns=columns, sources=sources,
                          joins=joins, where=where, group_by=group_by,
                          order_by=order_by, line=start.line)

    def _select_list(self) -> list:
        if self._match(T.STAR):
            return [ast.Star()]
        items = [self._select_item()]
        while self._match(T.COMMA):
            items.append(self._select_item())
        return items

    def _select_item(self) -> ast.SelectItem:
        expr = self._expr()
        alias = None
        if self._match_kw("AS"):
            alias = self._expect_ident("alias kolom").value.lower()
        elif self._check(T.IDENT):
            alias = self._advance().value.lower()
        return ast.SelectItem(expr, alias)

    def _table_ref(self):
        tok = self._peek()
        if self._check(T.LPAREN) and self._next_is_select():
            self._advance()
            query = self._select()
            self._expect(T.RPAREN, "')' penutup subquery")
            return ast.DerivedTable(query, self._alias(), line=tok.line)
        name = self._table_name()
        return ast.TableRef(name, self._alias(), line=tok.line)

    def _table_name(self) -> str:
        name = self._expect_ident("nama tabel").value
        if self._match(T.DOT):
            name += "." + self._expect_ident("nama tabel setelah '.'").value
        return name.lower()

    def _alias(self) -> str | None:
        if self._match_kw("AS"):
            return self._expect_ident("alias").value.lower()
        if self._check(T.IDENT):
            return self._advance().value.lower()
        return None

    def _join(self) -> ast.Join:
        tok = self._peek()
        kind = "INNER"
        if self._match_kw("INNER"):
            kind = "INNER"
        elif self._match_kw("LEFT"):
            kind = "LEFT"
        self._expect_kw("JOIN")
        source = self._table_ref()
        self._expect_kw("ON")
        condition = self._expr()
        return ast.Join(kind, source, condition, line=tok.line)

    def _order_list(self) -> list:
        items = []
        while True:
            expr = self._expr()
            direction = self._match_kw("ASC", "DESC")
            items.append(ast.OrderItem(expr, direction.value if direction else "ASC"))
            if not self._match(T.COMMA):
                return items

    # ---- INSERT, UPDATE, DELETE -----------------------------------------
    def _insert(self) -> ast.Insert:
        start = self._expect_kw("INSERT")
        self._expect_kw("INTO")
        tok = self._peek()
        table = ast.TableRef(self._table_name(), None, line=tok.line)
        columns = []
        if self._check(T.LPAREN) and not self._next_is_select():
            self._advance()
            columns.append(self._expect_ident("nama kolom").value.lower())
            while self._match(T.COMMA):
                columns.append(self._expect_ident("nama kolom").value.lower())
            self._expect(T.RPAREN, "')' penutup daftar kolom")
        if self._match_kw("VALUES"):
            rows = [self._value_row()]
            while self._match(T.COMMA):
                rows.append(self._value_row())
            return ast.Insert(table, columns, rows, None, line=start.line)
        if self._check_kw("SELECT"):
            # TODO(T1): dukung INSERT INTO ... SELECT ... (SPESIFIKASI.md bagian 3 dan 5).
            raise ParseError("INSERT ... SELECT belum didukung", self._peek())
        raise ParseError("diharapkan VALUES atau SELECT", self._peek())

    def _value_row(self) -> list:
        self._expect(T.LPAREN, "'(' pembuka VALUES")
        values = self._expr_list()
        self._expect(T.RPAREN, "')' penutup VALUES")
        return values

    def _update(self) -> ast.Update:
        start = self._expect_kw("UPDATE")
        tok = self._peek()
        table = ast.TableRef(self._table_name(), self._alias(), line=tok.line)
        self._expect_kw("SET")
        assignments = [self._assignment()]
        while self._match(T.COMMA):
            assignments.append(self._assignment())
        where = self._expr() if self._match_kw("WHERE") else None
        return ast.Update(table, assignments, where, line=start.line)

    def _assignment(self) -> ast.Assignment:
        column = self._column_ref()
        self._expect(T.OP, "'='", "=")
        return ast.Assignment(column, self._expr())

    def _delete(self) -> ast.Delete:
        start = self._expect_kw("DELETE")
        self._expect_kw("FROM")
        tok = self._peek()
        table = ast.TableRef(self._table_name(), self._alias(), line=tok.line)
        where = self._expr() if self._match_kw("WHERE") else None
        return ast.Delete(table, where, line=start.line)

    # ---- ekspresi (dari presedensi terendah ke tertinggi) ---------------
    def _expr(self):
        return self._logical()

    def _logical(self):
        # OR dan AND: operator logika biner, asosiatif kiri.
        left = self._not()
        while self._check_kw("AND", "OR"):
            op = self._advance().value
            left = ast.BinaryOp(left, op, self._not())
        return left

    def _not(self):
        if self._match_kw("NOT"):
            return ast.UnaryOp("NOT", self._not())
        return self._comparison()

    def _comparison(self):
        left = self._additive()
        tok = self._peek()
        if tok.type == T.OP and tok.value in COMPARISON_OPS:
            self._advance()
            return ast.BinaryOp(left, tok.value, self._additive())
        negated = False
        nxt = self._peek(1)
        if self._check_kw("NOT") and nxt.type == T.KEYWORD and nxt.value in ("IN", "LIKE", "BETWEEN"):
            self._advance()
            negated = True
        if self._match_kw("IN"):
            return self._in_rest(left, negated)
        if self._match_kw("LIKE"):
            node = ast.BinaryOp(left, "LIKE", self._additive())
            return ast.UnaryOp("NOT", node) if negated else node
        if self._match_kw("BETWEEN"):
            low = self._additive()
            self._expect_kw("AND")
            high = self._additive()
            return ast.Between(left, low, high, negated)
        if self._match_kw("IS"):
            is_not = self._match_kw("NOT") is not None
            self._expect_kw("NULL")
            return ast.IsNull(left, is_not)
        return left

    def _in_rest(self, left, negated: bool):
        self._expect(T.LPAREN, "'(' setelah IN")
        if self._check_kw("SELECT"):
            query = self._select()
            self._expect(T.RPAREN, "')' penutup subquery")
            return ast.InExpr(left, None, query, negated)
        values = self._expr_list()
        self._expect(T.RPAREN, "')' penutup daftar IN")
        return ast.InExpr(left, values, None, negated)

    def _additive(self):
        left = self._multiplicative()
        while self._check(T.OP, "+") or self._check(T.OP, "-"):
            op = self._advance().value
            left = ast.BinaryOp(left, op, self._multiplicative())
        return left

    def _multiplicative(self):
        left = self._unary()
        while self._check(T.STAR) or self._check(T.OP, "/"):
            op = "*" if self._advance().type == T.STAR else "/"
            left = ast.BinaryOp(left, op, self._unary())
        return left

    def _unary(self):
        if self._match(T.OP, "-"):
            return ast.UnaryOp("-", self._unary())
        return self._primary()

    def _primary(self):
        tok = self._peek()
        if tok.type == T.NUMBER:
            self._advance()
            return ast.Literal(tok.value, "number")
        if tok.type == T.STRING:
            self._advance()
            return ast.Literal(tok.value, "string")
        if tok.type == T.PARAM:
            self._advance()
            return ast.Param(tok.value)
        if self._match_kw("NULL"):
            return ast.Literal(None, "null")
        if self._match_kw("EXISTS"):
            self._expect(T.LPAREN, "'(' setelah EXISTS")
            query = self._select()
            self._expect(T.RPAREN, "')' penutup subquery")
            return ast.Exists(query)
        if tok.type == T.LPAREN:
            self._advance()
            if self._check_kw("SELECT"):
                query = self._select()
                self._expect(T.RPAREN, "')' penutup subquery")
                return ast.Subquery(query)
            inner = self._expr()
            self._expect(T.RPAREN, "')'")
            return inner
        if tok.type == T.IDENT:
            if self._peek(1).type == T.LPAREN:
                return self._function_call()
            return self._column_ref()
        raise ParseError("diharapkan ekspresi", tok)

    def _function_call(self) -> ast.FunctionCall:
        name = self._advance().value.upper()
        self._expect(T.LPAREN, "'('")
        args, star = [], False
        if self._match(T.STAR):
            star = True
        elif not self._check(T.RPAREN):
            self._match_kw("DISTINCT")
            args = self._expr_list()
        self._expect(T.RPAREN, "')' penutup argumen fungsi")
        return ast.FunctionCall(name, args, star)

    def _column_ref(self) -> ast.ColumnRef:
        first = self._expect_ident("nama kolom")
        if self._match(T.DOT):
            second = self._expect_ident("nama kolom setelah '.'")
            return ast.ColumnRef(first.value.lower(), second.value.lower(), line=first.line)
        return ast.ColumnRef(None, first.value.lower(), line=first.line)

    def _expr_list(self) -> list:
        items = [self._expr()]
        while self._match(T.COMMA):
            items.append(self._expr())
        return items


def parse_sql(source: str) -> ast.Script:
    """Tokenize lalu parse satu file SQL. LexError tidak ditangkap di sini."""
    return Parser(tokenize(source)).parse_script()
