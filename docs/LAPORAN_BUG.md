# Laporan Bug

Dokumen ini mencatat seluruh bug yang ditemukan dalam codebase awal Ekstraktor CRUD Matrix, akar masalah berbasis konsep *Crafting Interpreters*, perbaikan yang diterapkan, test regresi pemverifikasi, dan peran AI.

---

## Bug 1: Keyword Huruf Kecil/Campuran Tidak Dikenali sebagai Keyword

**Ditemukan oleh:** Nadhief Musyaffa · **Diperbaiki oleh:** Nadhief Musyaffa

**Gejala.** 
Saat menginput SQL dengan huruf kecil atau campuran seperti `select id from t`, lexer menghasilkan token `IDENT` bernilai `'select'` alih-alih token `KEYWORD` bernilai `'SELECT'`. Menurut SPESIFIKASI.md Bagian 2.2, keyword bersifat *case-insensitive* dan nilai tokennya wajib dinormalisasi ke huruf besar. Akibatnya, parser gagal mengidentifikasi awal statement SELECT dan melemparkan ParseError.

**Reproduksi minimal.**
```sql
select id from t;
```

**Akar masalah.**
Pada konsep *Scanning* (Crafting Interpreters Bab 4), pemindaian kata kunci (*reserved words*) memetakan teks identifier ke tabel kamus kata kunci. Kode awal di `Lexer._word` melakukan pengecekan `if text in KEYWORDS:`, di mana `text` masih mempertahankan casing asli dari kode sumber, sedangkan set konstanta `KEYWORDS` hanya berisi string huruf besar. Karena perbandingan string peka huruf kapital (*case-sensitive*), kata kunci berhuruf kecil/campuran tidak cocok sehingga salah diklasifikasikan sebagai `TokenType.IDENT`.

**Perbaikan.**
File `crud/lexer.py`, fungsi `_word`: Mengubah pencocokan dengan mengonversi teks ke huruf besar terlebih dahulu menggunakan `upper = text.upper()`. Jika `upper in KEYWORDS`, tambahkan token `TokenType.KEYWORD` dengan nilai `upper`. Jika tidak, simpan sebagai identifier dengan teks aslinya. Alternatif lain adalah menyimpan seluruh variasi casing di `KEYWORDS`, namun alternatif ini ditolak karena boros memori dan tidak praktis.

**Test regresi.**
`test_regresi_keyword_case_insensitive` di `tests/test_tambahan.py`.

**Peran AI.**
AI membantu menemukan penyebab mengapa `tests/test_lexer.py::test_keyword_huruf_kecil` gagal, serta memverifikasi dengan menjalankan test suite lexer.

---

## Bug 2: Operator Perbandingan `<>` Dipecah Menjadi Dua Token Terpisah

**Ditemukan oleh:** Nadhief Musyaffa · **Diperbaiki oleh:** Nadhief Musyaffa

**Gejala.**
SQL yang memuat operator perbandingan tidak sama dengan `<>` (seperti pada `data/sample/laporan_penjualan.sql` baris 6) memicu `ParseError: Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'`. Berdasarkan SPESIFIKASI.md Bagian 2.5, `<>` adalah satu token `OP`.

**Reproduksi minimal.**
```sql
SELECT id FROM t WHERE status <> 'BATAL';
```

**Akar masalah.**
Berdasarkan prinsip *Maximal Munch* pada Scanning (Crafting Interpreters Bab 4), ketika karakter yang dibaca dapat membentuk bagian dari operator yang lebih panjang, lexer wajib mengonsumsi karakter berikutnya untuk membentuk token terpanjang yang valid. Kode awal pada `Lexer._scan_token` hanya mengecek `self._match("=")` ketika menemukan karakter `'<'` (menghasilkan `'<='` atau `'<'`), tanpa memeriksa kemungkinan karakter `'>'`. Karakter `'<'` dipancarkan sebagai satu token `OP`, dan `'>'` berikutnya dipancarkan sebagai token `OP` terpisah sehingga melanggar tata bahasa parser.

**Perbaikan.**
File `crud/lexer.py`, fungsi `_scan_token`: Menambahkan percabangan `elif self._match(">"): self._add(TokenType.OP, "<>", line, col)` setelah pengecekan `"="`. Alternatif lain adalah menyatukan semua operator multi-karakter dalam tabel lookahead regex, namun ditolak agar tetap konsisten dengan arsitektur scanner recursive-descent.

**Test regresi.**
`test_regresi_operator_tidak_sama_dengan` di `tests/test_tambahan.py`.

**Peran AI.**
AI mendeteksi kesalahan pada baris 6 `laporan_penjualan.sql` di mana operator `<>` memicu error ekspresi, dan memverifikasi koreksi maximal munch.

---

## Bug 3: Karakter Kutip Tunggal Ganda (`''`) Memotong Literal String Lebih Awal

**Ditemukan oleh:** Dzikra Al Ghufroon · **Diperbaiki oleh:** Dzikra Al Ghufroon

**Gejala.**
Literal string yang mengandung kutip ganda ter-escape seperti `'O''Brien'` dipotong paksa menjadi token string `'O'`, menyisakan `'Brien'` sebagai identifier atau error sintaks. SPESIFIKASI.md Bagian 2.4 menetapkan bahwa dua kutip berturut-turut di dalam string mewakili satu karakter kutip tunggal dalam nilai string.

**Reproduksi minimal.**
```sql
SELECT 'O''Brien' FROM pelanggan;
```

**Akar masalah.**
Pada pemindaian string literal (Crafting Interpreters Bab 4), tanda kutip penutup mengakhiri token kecuali terdapat mekanisme escape. Kode awal di `Lexer._string` langsung mengeksekusi `break` begitu mendeteksi karakter `'` tanpa memeriksa apakah karakter tepat setelahnya juga berupa `'`.

**Perbaikan.**
File `crud/lexer.py`, fungsi `_string`: Ketika `ch == "'"` terbaca, dilakukan pengecekan lanjutan `if self._match("'"): chars.append("'") else: break`. Jika terdapat kutip kedua, kutip tersebut dikonsumsi dan satu tanda kutip ditambahkan ke buffer string; jika tidak ada, perulangan berhenti sebagai penutup string yang sah.

**Test regresi.**
`test_regresi_string_kutip_ganda_escaped` di `tests/test_tambahan.py`.

**Peran AI.**
AI mengidentifikasi kegagalan parsing pada data `pemeliharaan.sql` yang memiliki nama `'O''Brien'`, lalu menerapkan pola escape SQL baku.

---

## Bug 4: Presedensi Operator Logika `AND` dan `OR` Dianggap Setara

**Ditemukan oleh:** Dzikra Al Ghufroon · **Diperbaiki oleh:** Dzikra Al Ghufroon

**Gejala.**
Ekspresi logika `a = 1 OR b = 2 AND c = 3` diparsing menjadi pohon asosiatif kiri `((a = 1 OR b = 2) AND c = 3)`. Menurut SPESIFIKASI.md Bagian 3.1, `AND` memiliki tingkat presedensi 2 yang lebih tinggi dari `OR` (tingkat 1), sehingga ekspresi wajib diparsing sebagai `(a = 1 OR (b = 2 AND c = 3))`.

**Reproduksi minimal.**
```sql
SELECT id FROM t WHERE a = 1 OR b = 2 AND c = 3;
```

**Akar masalah.**
Sesuai teori *Parsing Expressions* (Crafting Interpreters Bab 6), setiap tingkat presedensi operator wajib dipisahkan ke dalam fungsi grammar tersendiri dalam parser recursive descent. Fungsi yang memproses operator berpresedensi lebih rendah harus memanggil fungsi operator berpresedensi lebih tinggi. Kode awal menggabungkan penanganan `AND` dan `OR` dalam satu fungsi `_logical` dengan satu perulangan `while self._check_kw("AND", "OR"):`, yang secara keliru menempatkan keduanya pada tingkat hierarki yang sama.

**Perbaikan.**
File `crud/parser.py`: Memisahkan fungsi `_logical` menjadi dua fungsi terpisah: `_or(self)` yang menangani operator `OR` dan memanggil `_and(self)`, serta `_and(self)` yang menangani operator `AND` dan memanggil `_not(self)`. Dengan demikian, ikatan `AND` diproses lebih dalam pada AST daripada `OR`.

**Test regresi.**
`test_regresi_presedensi_and_or` di `tests/test_tambahan.py`.

**Peran AI.**
AI memeriksa hierarki grammar pada SPESIFIKASI Bagian 3 dan merestrukturisasi method recursive descent sesuai Bab 6 Crafting Interpreters.

---

## Bug 5: Error Recovery (Panic Mode) Membuang Seluruh Sisa Token File

**Ditemukan oleh:** Dzikra Al Ghufroon · **Diperbaiki oleh:** Dzikra Al Ghufroon

**Gejala.**
Ketika terjadi kesalahan sintaks pada satu statement dalam skrip multi-statement (misalnya baris 4 pada `campuran_error.sql`), seluruh statement valid setelahnya (baris 6 dan 8) ikut terabaikan dan tidak masuk ke dalam hasil CRUD matrix. SPESIFIKASI.md Bagian 6 menyatakan bahwa error recovery harus membuang token sampai dan termasuk `;` berikutnya, lalu melanjutkan proses statement setelahnya.

**Reproduksi minimal.**
```sql
SELECT id FROM ;
SELECT id FROM tabel_valid;
```

**Akar masalah.**
Konsep *Panic Mode Error Recovery* (Crafting Interpreters Bab 6) bertujuan mengembalikan parser ke status stabil (*synchronization point*) agar parser dapat terus menemukan error berikutnya tanpa *cascade failures*. Titik aman yang ditentukan spesifikasi adalah tanda titik koma `;`. Pada implementasi awal `Parser._synchronize`, perulangan membuang token tanpa henti hingga mencapai `self._at_end()` (EOF), sehingga menghentikan parsing untuk seluruh sisa file.

**Perbaikan.**
File `crud/parser.py`, fungsi `_synchronize`: Mengubah perulangan menjadi `while not self._at_end(): if self._advance().type == T.SEMICOLON: return`. Parser membuang token hingga token `;` dikonsumsi, lalu kembali ke loop utama `parse_script` untuk melanjutkan statement berikutnya.

**Test regresi.**
`test_regresi_panic_mode_lanjut_setelah_semicolon` di `tests/test_tambahan.py`.

**Peran AI.**
AI menganalisis hilangnya data baris 6 dan 8 pada `campuran_error.sql` dan menyesuaikan metode `_synchronize` sesuai Bab 6.

---

## Bug 6: Parser Menolak Sintaks `LEFT OUTER JOIN`

**Ditemukan oleh:** Dzikra Al Ghufroon · **Diperbaiki oleh:** Dzikra Al Ghufroon

**Gejala.**
Pernyataan yang menggunakan klausa `LEFT OUTER JOIN` (seperti pada `data/sample/pemeliharaan.sql` baris 5) memunculkan `ParseError: diharapkan JOIN, ditemukan 'OUTER'`. Menurut SPESIFIKASI.md Bagian 3, aturan join adalah `[ "INNER" | "LEFT" [ "OUTER" ] ] "JOIN"`.

**Reproduksi minimal.**
```sql
SELECT a.id FROM a LEFT OUTER JOIN b ON b.a_id = a.id;
```

**Akar masalah.**
Pada aturan grammar join, keyword `OUTER` bersifat opsional setelah `LEFT`. Kode lama di `Parser._join` hanya memeriksa `LEFT`, kemudian langsung melakukan `self._expect_kw("JOIN")`. Ketika token `OUTER` muncul di antara `LEFT` dan `JOIN`, parser menganggapnya sebagai pelanggaran sintaks.

**Perbaikan.**
File `crud/parser.py`, fungsi `_join`: Menambahkan `self._match_kw("OUTER")` setelah mendeteksi `LEFT` untuk mengonsumsi keyword `OUTER` jika ada, sebelum mengecek keberadaan `JOIN`.

**Test regresi.**
`test_regresi_left_outer_join` di `tests/test_tambahan.py`.

**Peran AI.**
AI mencocokkan grammar SPESIFIKASI bagian 3 dengan implementasi `_join` dan menemukan bahwa keyword `OUTER` belum dikonsumsi.

---

## Bug 7: Urutan Penelusuran Scope Terbalik (Outermost First alih-alih Innermost First)

**Ditemukan oleh:** Nadhief Musyaffa · **Diperbaiki oleh:** Nadhief Musyaffa

**Gejala.**
Ketika alias yang sama digunakan pada subquery dan outer query (seperti alias `x` pada `data/sample/audit.sql` baris 12-14), referensi `x.id` di dalam subquery salah ter-resolve ke tabel luar (`pelanggan`) alih-alih tabel dalam (`pesanan`). Hal ini melanggar aturan lexical scoping dan *shadowing* (SPESIFIKASI.md Bagian 4.3).

**Reproduksi minimal.**
```sql
SELECT x.id FROM luar x WHERE x.id IN (SELECT x.id FROM dalam x);
```

**Akar masalah.**
Berdasarkan konsep *Resolving and Binding* (Crafting Interpreters Bab 11), resolusi identifier dengan *lexical scope* harus mencari simbol dari *lingkungan lokal (innermost scope)* lalu merambat keluar ke *parent scope*. Pada kode awal `Resolver._lookup`, rantai scope dikumpulkan dari anak ke induk (`chain = [dalam, luar]`), namun kemudian diiterasi dengan `for scope in reversed(chain):`. Pembalikan list ini menyebabkan pencarian berjalan dari terluar ke terdalam, sehingga alias luar menutupi alias lokal (*inverted shadowing*).

**Perbaikan.**
File `crud/resolver.py`, fungsi `_lookup`: Menghilangkan `reversed(chain)` dan langsung menelusuri pointer rantai scope dari `self.scope` ke `scope.parent`:
```python
scope = self.scope
while scope is not None:
    if name in scope.entries:
        return scope.entries[name]
    scope = scope.parent
return None
```

**Test regresi.**
`test_regresi_scope_lookup_innermost_first` di `tests/test_tambahan.py`.

**Peran AI.**
AI menginspeksi trace pohon resolusi AST pada `audit.sql` baris 12 dan memvalidasi koreksi penelusuran hierarki scope.

---

## Bug 8: Statement `DELETE` Tidak Melakukan `_pop()` Menyebabkan Kebocoran Scope

**Ditemukan oleh:** Nadhief Musyaffa · **Diperbaiki oleh:** Nadhief Musyaffa

**Gejala.**
Alias tabel dari statement `DELETE` tetap terbaca dan dapat diakses oleh statement berikutnya dalam satu file. Pada `data/sample/audit.sql`, statement `DELETE FROM sesi s` pada baris 16 menyebabkan statement `SELECT s.id FROM pengguna u` pada baris 18 berhasil me-resolve `s` ke `sesi`, padahal menurut SPESIFIKASI.md Bagian 4.5 setiap statement berdiri sendiri dan baris 18 seharusnya memunculkan error diagnostik `alias 's' tidak terdefinisi`.

**Reproduksi minimal.**
```sql
DELETE FROM sesi s WHERE s.id = 1;
SELECT s.id FROM pengguna u;
```

**Akar masalah.**
Setiap scope baru yang dibuat dengan `self._push()` wajib ditutup dengan `self._pop()` saat blok statement selesai diproses (Crafting Interpreters Bab 11). Di fungsi `Resolver._delete`, `self._push()` dipanggil untuk memasukkan tabel target ke dalam scope, namun tidak ada pemanggilan `self._pop()` di akhir fungsi. Akibatnya, scope milik statement DELETE tetap aktif dan menjadi induk dari scope statement berikutnya.

**Perbaikan.**
File `crud/resolver.py`:
1. Menambahkan `self._pop()` di akhir fungsi `_delete`.
2. Pada `resolve_statement(stmt)`, secara eksplisit mereset `self.scope = None` sebelum dan sesudah eksekusi statement untuk menjamin isolasi penuh antar-statement.

**Test regresi.**
`test_regresi_delete_scope_tidak_bocor` di `tests/test_tambahan.py`.

**Peran AI.**
AI mendeteksi anomali pada AST audit.sql baris 18 di mana `s.id` ter-resolve padahal tidak ada tabel `sesi` di statement tersebut.

---

## Bug 9: Subquery pada Statement `UPDATE` Dideteksi sebagai Operasi `'U'`

**Ditemukan oleh:** Dzikra Al Ghufroon · **Diperbaiki oleh:** Dzikra Al Ghufroon

**Gejala.**
Tabel yang dirujuk melalui subquery di dalam klausa `SET` maupun `WHERE` pada query `UPDATE` (seperti `pesanan` pada `laporan_penjualan.sql` baris 12-13) tercatat dengan operasi `'U'` (*Update*). Berdasarkan SPESIFIKASI.md Bagian 5, membaca tabel lewat subquery selalu menghasilkan operasi `'R'` (*Read*). Kesalahan ini menyebabkan tabel `pesanan` memiliki operasi gabungan `'RUD'` alih-alih `'RD'`.

**Reproduksi minimal.**
```sql
UPDATE pelanggan SET level = 'gold'
WHERE id IN (SELECT pelanggan_id FROM pesanan);
```

**Akar masalah.**
Pada AST Traversal / Analisis Semantik (Crafting Interpreters Bab 5 dan 11), operasi yang diterapkan pada sub-ekspresi ditentukan oleh semantik lokal statement. Pada `crud/analyzer.py` fungsi `analyze_statement`, cabang `ast.Update` memanggil `_collect(assignment.value, usage, "U")` dan `_collect(stmt.where, usage, "U")`. Karena argumen operasi yang dikirimkan adalah `"U"`, fungsi rekursif `_collect` menandai seluruh tabel subquery dengan status modifikasi (*Update*), bertentangan dengan semantik SQL di mana pembacaan data di subquery bersifat *Read-only*.

**Perbaikan.**
File `crud/analyzer.py`, fungsi `analyze_statement`: Mengubah argumen operasi yang dikirim ke `_collect` untuk `assignment.value` dan `stmt.where` dari `"U"` menjadi `"R"`.

**Test regresi.**
`test_regresi_update_subquery_operasi_read` di `tests/test_tambahan.py`.

**Peran AI.**
AI menganalisis kegagalan `tests/test_analyzer.py::test_matrix_laporan_penjualan` dan mencocokkan matriks aturan Bagian 5 spesifikasi.
