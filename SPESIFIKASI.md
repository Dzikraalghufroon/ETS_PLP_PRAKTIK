# Spesifikasi Ekstraktor CRUD Matrix

Dokumen ini adalah acuan kebenaran. Test tersembunyi disusun berdasarkan dokumen ini.

## 1. Tujuan dan keluaran

Tool menerima file SQL dan menghasilkan, untuk setiap statement, daftar tabel beserta
operasi C (create), R (read), U (update), dan D (delete). Hasil per file adalah gabungan
seluruh statement di file itu. Tool juga melaporkan error sintaks dan diagnostik resolusi.

## 2. Lexer

### 2.1 Jenis token

`KEYWORD`, `IDENT`, `NUMBER`, `STRING`, `PARAM`, `OP`, `STAR`, `LPAREN`, `RPAREN`, `COMMA`,
`DOT`, `SEMICOLON`, `EOF`. Setiap token menyimpan baris dan kolom awalnya (mulai dari 1).

### 2.2 Keyword dan identifier

- Daftar keyword ada di `KEYWORDS` (`crud/lexer.py`).
- Keyword **tidak peka huruf besar/kecil**: `select`, `Select`, dan `SELECT` sama-sama
  keyword. Nilai token keyword selalu dinormalisasi ke huruf besar.
- Kata yang bukan keyword adalah `IDENT`, termasuk kata yang hanya *diawali* keyword
  (`selection`, `fromage`). Nama tabel, alias, dan kolom dinormalisasi ke huruf kecil oleh parser.
- Quoted identifier (`"nama"`, `[nama]`) di luar lingkup.

### 2.3 Komentar

- `--` sampai akhir baris.
- `/* ... */`, boleh lintas baris, tidak bersarang, boleh berisi `*`.
- Komentar blok yang tidak ditutup adalah `LexError`.
- Komentar tidak menghasilkan token.

### 2.4 String

- Diapit kutip tunggal. Nilai token tidak termasuk kutip pembuka dan penutup.
- Dua kutip berturut-turut di dalam string (`''`) mewakili **satu** karakter kutip:
  `'O''Brien'` adalah satu token `STRING` bernilai `O'Brien`.
- String yang tidak ditutup adalah `LexError`.

### 2.5 Operator

`=`, `<>`, `!=`, `<`, `<=`, `>`, `>=`, `+`, `-`, `/` (token `OP`), dan `*` (token `STAR`).
Lexer selalu mengambil operator **terpanjang** yang cocok (maximal munch): `<>` adalah satu
token, bukan `<` lalu `>`.

### 2.6 Parameter dan angka

- Parameter: `?` atau `:nama` (huruf, angka, garis bawah).
- Angka: bilangan bulat atau desimal (`10`, `2.5`).

### 2.7 Error

Karakter lain menghasilkan `LexError` dengan baris dan kolom. `LexError` menghentikan
pemrosesan file tersebut.

## 3. Grammar

```text
script         = { ";" | statement ( ";" | EOF ) } ;
statement      = select_stmt | insert_stmt | update_stmt | delete_stmt ;

select_stmt    = "SELECT" [ "DISTINCT" ] select_list
                 "FROM" table_ref { "," table_ref }
                 { join }
                 [ "WHERE" expr ]
                 [ "GROUP" "BY" expr_list ]
                 [ "ORDER" "BY" order_item { "," order_item } ] ;
select_list    = "*" | select_item { "," select_item } ;
select_item    = expr [ [ "AS" ] IDENT ] ;
table_ref      = ( table_name | "(" select_stmt ")" ) [ [ "AS" ] IDENT ] ;
table_name     = IDENT [ "." IDENT ] ;
join           = [ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN" table_ref "ON" expr ;
order_item     = expr [ "ASC" | "DESC" ] ;

insert_stmt    = "INSERT" "INTO" table_name [ "(" IDENT { "," IDENT } ")" ]
                 ( "VALUES" value_row { "," value_row } | select_stmt ) ;
value_row      = "(" expr_list ")" ;
update_stmt    = "UPDATE" table_name [ [ "AS" ] IDENT ]
                 "SET" assignment { "," assignment } [ "WHERE" expr ] ;
assignment     = column_ref "=" expr ;
delete_stmt    = "DELETE" "FROM" table_name [ [ "AS" ] IDENT ] [ "WHERE" expr ] ;

expr           = or_expr ;
or_expr        = and_expr { "OR" and_expr } ;
and_expr       = not_expr { "AND" not_expr } ;
not_expr       = "NOT" not_expr | comparison ;
comparison     = additive [ comp_op additive
                          | [ "NOT" ] "IN" "(" ( select_stmt | expr_list ) ")"
                          | [ "NOT" ] "LIKE" additive
                          | [ "NOT" ] "BETWEEN" additive "AND" additive
                          | "IS" [ "NOT" ] "NULL" ] ;
comp_op        = "=" | "<>" | "!=" | "<" | "<=" | ">" | ">=" ;
additive       = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative = unary { ( "*" | "/" ) unary } ;
unary          = "-" unary | primary ;
primary        = NUMBER | STRING | PARAM | "NULL"
               | "EXISTS" "(" select_stmt ")"
               | "(" select_stmt ")"
               | "(" expr ")"
               | function_call
               | column_ref ;
function_call  = IDENT "(" [ "*" | [ "DISTINCT" ] expr_list ] ")" ;
column_ref     = IDENT [ "." IDENT ] ;
expr_list      = expr { "," expr } ;
```

### 3.1 Presedensi (terendah ke tertinggi)

| Tingkat | Operator | Asosiatif |
| --- | --- | --- |
| 1 | `OR` | kiri |
| 2 | `AND` | kiri |
| 3 | `NOT` (prefiks) | kanan |
| 4 | perbandingan, `IN`, `LIKE`, `BETWEEN`, `IS NULL` | tidak berantai |
| 5 | `+`, `-` | kiri |
| 6 | `*`, `/` | kiri |
| 7 | `-` (prefiks) | kanan |

Contoh: `a = 1 OR b = 2 AND c = 3` berarti `a = 1 OR (b = 2 AND c = 3)`.

### 3.2 Catatan

- `*` di awal `select_list` berarti "semua kolom"; di dalam ekspresi berarti perkalian.
- `(` di `table_ref` atau `primary` diikuti `SELECT` berarti subquery.
- `BETWEEN a AND b`: `AND` di sini milik `BETWEEN` karena batas bawahnya adalah `additive`,
  bukan `expr`.

## 4. Resolver

### 4.1 Pembentukan scope

- Scope baru dibuat untuk setiap `SELECT` (termasuk subquery), `UPDATE`, dan `DELETE`.
- `INSERT` tidak membuat scope; `SELECT` di dalam `INSERT` membuat scope sendiri.
- Scope dalam punya induk, yaitu scope tempat ia berada.

### 4.2 Isi scope

- Setiap tabel di `FROM`, `JOIN`, atau target `UPDATE`/`DELETE` masuk scope dengan nama
  **alias**-nya, atau bagian terakhir nama tabel bila tanpa alias (`crm.pelanggan` menjadi
  `pelanggan`).
- Subquery di `FROM` masuk dengan aliasnya; kolom yang merujuknya di-resolve ke
  `"<subquery alias>"`. Subquery di `FROM` tanpa alias menghasilkan warning.
- Nama yang dideklarasikan dua kali di scope yang sama adalah error.

### 4.3 Resolusi kolom

- **Dengan qualifier** (`p.nama`): qualifier dicari mulai dari **scope terdalam ke luar**.
  Yang pertama ditemukan dipakai. Akibatnya alias di subquery menutupi alias yang sama di luar
  (shadowing), dan subquery tetap bisa merujuk alias luar (correlated subquery). Jika tidak
  ditemukan di mana pun: error `alias 'x' tidak terdefinisi`.
- **Tanpa qualifier** (`nama`): hanya scope **terdalam** yang dilihat.
    - tepat satu tabel: kolom di-resolve ke tabel itu;
    - lebih dari satu tabel: warning `kolom 'nama' ambigu tanpa skema`, `resolved` tetap `None`;
    - tidak ada tabel: warning.
- Hasil resolusi disimpan di `ColumnRef.resolved` (nama tabel lengkap).

### 4.4 Subquery di FROM

Di-resolve sebelum scope `SELECT` yang memuatnya dibuat, sehingga tidak melihat tabel lain di
`FROM` yang sama, tetapi tetap melihat scope di luar `SELECT` tersebut.

### 4.5 Setiap statement berdiri sendiri

Setelah satu statement selesai di-resolve, tidak boleh ada scope tersisa. Alias dari statement
sebelumnya **tidak boleh** terlihat oleh statement berikutnya.

### 4.6 Diagnostik

`Diagnostic(level, message, line)` dengan `level` berupa `"error"` atau `"warning"`.

## 5. Aturan CRUD (aturan lokal proyek)

| Statement | Tabel target | Tabel lain (subquery, sumber SELECT) |
| --- | --- | --- |
| `SELECT` | semua tabel di `FROM`/`JOIN`: R | R |
| `INSERT ... VALUES` | C | R |
| `INSERT ... SELECT` | C | tabel sumber: R |
| `UPDATE` | U | R (subquery di `SET` maupun `WHERE`) |
| `DELETE` | D | R |

- Membaca tabel lewat subquery **selalu** R, apa pun jenis statement luarnya.
- Nama tabel ditulis huruf kecil lengkap dengan skema (`crm.pelanggan`).
- Gabungan operasi selalu ditulis berurutan C, R, U, D (`RU`, bukan `UR`).
- Statement yang gagal di-parse tidak dihitung.

## 6. Error sintaks

- Format pesan: `Baris L, kolom K: diharapkan X, ditemukan Y`, menunjuk token tempat error terdeteksi.
- **Error recovery** (panic mode): setelah error, buang token sampai dan termasuk `;`
  berikutnya, lalu lanjutkan dengan statement setelahnya. Setiap statement rusak menghasilkan
  tepat satu error, dan statement valid setelahnya tetap diproses.

## 7. API publik dan batasan arsitektur

Test tersembunyi memakai API berikut. Nama dan perilakunya tidak boleh diubah:

- `crud.lexer`: `tokenize`, `Token`, `TokenType`, `LexError`, `KEYWORDS`
- `crud.parser`: `parse_sql`, `Parser`, `ParseError` (atribut `line`, `col`)
- `crud.ast_nodes`: semua kelas node beserta nama field-nya, `iter_nodes`, `pretty`
- `crud.resolver`: `Resolver().resolve_script(script)` mengembalikan list `Diagnostic`
- `crud.analyzer`: `analyze_statement(stmt)` mengembalikan `{tabel: {operasi}}`, `column_usage(stmt)`
- `crud.pipeline`: `analyze_source(text)` mengembalikan `FileResult` (`statements`, `parse_errors`,
  `diagnostics`, `lex_error`, `matrix()`)

Batasan arsitektur:

1. Urutan pipeline tetap: lexer, parser, resolver, analyzer.
2. Resolver adalah pass terpisah setelah parsing. Parser tidak melakukan resolusi.
3. Analyzer bekerja di atas AST, tidak membaca teks SQL mentah dan tidak memakai regex.
4. Tidak ada skema database; semua keputusan diambil dari teks query.
5. `baseline/regex_extractor.py` tidak boleh diubah.

## 8. Format keluaran

- `crud_matrix.csv`: `file,<tabel1>,<tabel2>,...`, satu baris per file.
- `--detail`: `file,baris,jenis,tabel,operasi`, satu baris per (statement, tabel).
  `baris` adalah baris keyword awal statement.
- `--kolom`: `file,baris,tabel,kolom,operasi`.
- `data/ground_truth.csv`: `file,baris,tabel,operasi`, **satu huruf operasi per baris**.

## 9. Di luar lingkup

CTE (`WITH`), `UNION`, `MERGE`, DDL, quoted identifier, `t.*`, window function, alias kolom di
`ORDER BY`, komentar bersarang, stored procedure, trigger, dan view.
