# Laporan Akhir

## 1. Hasil evaluasi

Berikut adalah keluaran terminal `python evaluate.py` setelah seluruh ground truth (`data/ground_truth.csv`) dilengkapi untuk keempat file sampel:

```text
Dievaluasi: audit.sql, campuran_error.sql, laporan_penjualan.sql, pemeliharaan.sql (27 triple)

Metode   Precision  Recall     F1
parser        1.00    1.00   1.00
regex         0.65    0.81   0.72

[regex]
  salah ditemukan (FP): ('audit.sql', 16, 'sesi', 'R')
  salah ditemukan (FP): ('campuran_error.sql', 4, 'pesanan', 'R')
  salah ditemukan (FP): ('campuran_error.sql', 8, 'keranjang', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'D')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pesanan', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'rahasia', 'R')
  salah ditemukan (FP): ('laporan_penjualan.sql', 15, 'pesanan', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.alamat', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.pelanggan', 'R')
  salah ditemukan (FP): ('pemeliharaan.sql', 2, 'pelanggan_lama', 'U')
  salah ditemukan (FP): ('pemeliharaan.sql', 15, 'crm.alamat', 'R')
  terlewat (FN):       ('audit.sql', 2, 'pesanan', 'R')
  terlewat (FN):       ('laporan_penjualan.sql', 3, 'pelanggan', 'R')
  terlewat (FN):       ('laporan_penjualan.sql', 3, 'pesanan', 'R')
  terlewat (FN):       ('pemeliharaan.sql', 3, 'crm.alamat', 'R')
  terlewat (FN):       ('pemeliharaan.sql', 3, 'crm.pelanggan', 'R')
```

---

## 2. Tiga kasus di mana regex salah

### Kasus 1: Teks di Dalam Komentar Mengandung Kata Kunci SQL
- **SQL:**
  ```sql
  -- DELETE FROM pelanggan   (baris ini komentar, bukan perintah)
  /* Skrip pemeliharaan data pelanggan.
     Catatan lama: UPDATE pelanggan_lama sudah tidak dipakai. */
  ```
- **Kesalahan regex:**
  Pola ekspresi reguler `\bDELETE\s+FROM\s+([A-Za-z_]\w*)` dan `\bUPDATE\s+([A-Za-z_]\w*)` tidak memiliki pemahaman konteks komentar. Akibatnya, regex mendeteksi operasi `D` pada tabel `pelanggan` dan operasi `U` pada tabel `pelanggan_lama` (False Positive).
- **Mengapa parser benar:**
  Pada tahap *Lexical Analysis* (Crafting Interpreters Bab 4), lexer secara eksplisit mengenali format komentar baris (`--`) dan komentar blok (`/* ... */`). Lexer mengonsumsi seluruh isi komentar tanpa memancarkan token apa pun ke parser. Akibatnya, AST parser hanya memuat statement SQL aktif dan terbebas dari teks komentar.

### Kasus 2: String Literal yang Memuat Kata Mirip Klausa SQL
- **SQL:**
  ```sql
  WHERE o.status = 'LUNAS' AND o.catatan <> 'FROM rahasia'
  ```
- **Kesalahan regex:**
  Pola regex `\bFROM\s+([A-Za-z_]\w*)` mencocokkan substring `FROM rahasia` yang terdapat di dalam literal string `'FROM rahasia'`, sehingga mengklaim bahwa terdapat pembacaan tabel bernama `rahasia` (False Positive).
- **Mengapa parser benar:**
  Lexer membedakan teks di dalam tanda kutip tunggal sebagai `TokenType.STRING`. Parser kemudian memetakannya menjadi node data literal (`ast.Literal(value="FROM rahasia", kind="string")`) di dalam cabang ekspresi biner, bukan sebagai klausa sumber tabel `FROM` pada statement query.

### Kasus 3: Tabel Jamak Dipisahkan Tanda Koma pada Klausa FROM
- **SQL:**
  ```sql
  SELECT p.id, p.nama
  FROM pelanggan p, pesanan o
  WHERE o.pelanggan_id = p.id;
  ```
- **Kesalahan regex:**
  Pola regex naif `\bFROM\s+([A-Za-z_]\w*)` hanya mengambil tabel pertama tepat setelah kata kunci `FROM` (yaitu `pelanggan`). Regex gagal mengenali pemisah koma `, pesanan o` sehingga tabel `pesanan` terlewat sepenuhnya (False Negative).
- **Mengapa parser benar:**
  Grammar parser recursive descent (Bab 6) mendefinisikan aturan `sources = [self._table_ref()]` diikuti `while self._match(T.COMMA): sources.append(self._table_ref())`. Parser membaca setiap item referensi tabel secara rekursif, sehingga kedua tabel (`pelanggan` dan `pesanan`) masuk ke dalam daftar sumber AST dan keduanya berhasil ditandai dengan operasi `R`.

---

## 3. Batas pendekatan kami

Meskipun seluruh bug implementasi telah diperbaiki dan mencapai akurasi 100% pada dataset uji, parser ini memiliki keterbatasan intrinsik karena pendekatan *schemaless* (tanpa koneksi ke basis data riil):

### 1. Ambiguitas Kolom Tanpa Qualifier pada Multi-Tabel (*Schemaless Column Resolution*)
- **Contoh SQL:**
  ```sql
  SELECT nama, total FROM pelanggan p JOIN pesanan o ON o.pelanggan_id = p.id;
  ```
- **Akibat pada CRUD matrix & kolom:**
  Ekstraktor mampu mengenali tabel `pelanggan` dan `pesanan` berstatus `R` pada tingkat tabel. Namun, pada pelaporan detail kolom (`--kolom`), resolver tidak dapat menentukan apakah `nama` milik tabel `pelanggan` atau `pesanan` karena tidak memiliki qualifier (`p.` atau `o.`). Sesuai aturan, kolom dibiarkan `resolved = None` dan menghasilkan peringatan diagnostik ambigu.
- **Informasi yang dibutuhkan:**
  Katalog skema tabel (*database schema metadata / data dictionary*) yang memuat daftar nama kolom fisik dari masing-masing tabel yang terlibat.

### 2. Penanganan Proyeksi Bintang (`*` dan `t.*`) Tanpa Ekspansi Kolom Riil
- **Contoh SQL:**
  ```sql
  SELECT * FROM pesanan WHERE status = 'LUNAS';
  ```
- **Akibat pada CRUD matrix & kolom:**
  Pada tingkat tabel, operasi `R` pada tabel `pesanan` tercatat dengan benar. Namun, pada level pelacakan penggunaan kolom (`--kolom`), ekstraktor tidak dapat mendaftarkan kolom apa saja yang diakses karena AST hanya memuat node simbolik `ast.Star()`.
- **Informasi yang dibutuhkan:**
  Informasi skema tabel untuk memperluas (*star expansion*) simbol `*` menjadi daftar atribut kolom fisik yang sesungguhnya dimiliki tabel basis data saat query dijalankan.

### 3. Ketidakmampuan Menangani Konstruksi Kueri Lanjutan (*Out-of-Scope SQL Features*)
- **Contoh SQL:**
  ```sql
  WITH ringkasan AS (
      SELECT pelanggan_id, SUM(total) AS belanja FROM pesanan GROUP BY pelanggan_id
  )
  SELECT c.nama, r.belanja FROM pelanggan c JOIN ringkasan r ON r.pelanggan_id = c.id;
  ```
- **Akibat pada CRUD matrix & kolom:**
  Parser dirancang untuk subset gramatikal spesifik tanpa dukungan CTE (*Common Table Expressions* / `WITH`), operator himpunan (`UNION`), view, dan dynamic SQL (`EXECUTE`). Pernyataan seperti di atas akan memicu `ParseError` dan membuang statement tersebut sehingga tabel `pesanan` dan `pelanggan` tidak terhitung dalam matriks.
- **Informasi yang dibutuhkan:**
  Ekspansi gramatikal BNF pada parser dan resolver untuk mendukung struktur query modular (tabel semu CTE, temporary tables, view catalog, dan UNION pipelines).

---

## 4. Pembagian kerja

Pengerjaan tugas diselesaikan secara kolaboratif melalui metode *pair programming* dan pembagian tanggung jawab teknis berbasis fitur/komponen spesifik (mengingat sebagian besar berkas inti dikembangkan bersama oleh kedua anggota):

1. **Nadhief Musyaffa:**
   - **Lexer (`crud/lexer.py`):**
     - Mengimplementasikan scanner manual komentar blok `/* ... */` (TODO T3) lengkap dengan pelacakan nomor baris/kolom dan error saat komentar tidak ditutup (`LexError`).
     - Memperbaiki bug *maximal munch* pada pemindaian operator `<>` dengan lookahead `self._match(">")`.
     - Mengimplementasikan normalisasi kata kunci SQL (*case-insensitivity*) ke format huruf besar pada `_word`.
   - **Parser (`crud/parser.py`):**
     - Mengimplementasikan dukungan sintaks `INSERT INTO ... SELECT` (TODO T1) pada fungsi `_insert`.
   - **Resolver (`crud/resolver.py`):**
     - Memperbaiki arah pencarian *lexical scope* pada fungsi `_lookup` dari scope terdalam ke scope terluar (*innermost-to-outermost*) untuk memastikan resolusi alias dan aturan *shadowing* berjalan benar.
     - Menambahkan pembersihan scope (`self._pop()`) pada fungsi `_delete` untuk mencegah kebocoran alias tabel `DELETE` ke statement berikutnya.
   - **Pengujian Kasus Tepi (`tests/test_tambahan.py`):**
     - Menyusun dan mengimplementasikan 5 pengujian kasus tepi (*edge cases*) beserta analisis risikonya: komentar blok tidak ditutup, subquery FROM tanpa alias, ambiguitas kolom tanpa qualifier pada multi-tabel, titik koma berturut-turut/kosong, dan statement INSERT-SELECT kompleks dengan JOIN serta WHERE subquery.

2. **Dzikra Al Ghufroon:**
   - **Lexer (`crud/lexer.py`):**
     - Mengimplementasikan penanganan karakter escape kutip tunggal ganda (`''`) di dalam fungsi `_string`.
   - **Parser (`crud/parser.py`):**
     - Memisahkan hierarki tata bahasa logika menjadi fungsi terpisah `_or` (level 1) dan `_and` (level 2) untuk memastikan presedensi operator `AND` lebih tinggi daripada `OR`.
     - Memperbaiki mekanisme *panic mode error recovery* pada `_synchronize` agar berhenti tepat setelah mengonsumsi delimiter titik koma (`;`).
     - Menambahkan dukungan keyword opsional `OUTER` pada klausa `LEFT OUTER JOIN` di fungsi `_join`.
   - **Resolver (`crud/resolver.py`):**
     - Mengimplementasikan resolusi kolom tanpa qualifier (TODO T2) yang dibatasi pada scope terdalam beserta pemancaran warning diagnostik jika ambigu.
     - Menerapkan penguatan isolasi scope antar-statement pada fungsi `resolve_statement` (`self.scope = None` sebelum dan sesudah eksekusi).
   - **Analyzer & CLI (`crud/analyzer.py` & `crud/cli.py`):**
     - Memperbaiki klasifikasi analisis operasi tabel subquery pada klausa UPDATE (`SET` dan `WHERE`) dari status modifikasi `'U'` menjadi `'R'` (*read-only*).
     - Menambahkan ekspansi wildcard glob path pada antarmuka baris perintah CLI agar kompatibel dengan lingkungan Windows PowerShell.
   - **Pengujian Regresi & Evaluasi (`tests/test_tambahan.py` & `data/ground_truth.csv`):**
     - Mengimplementasikan 9 unit test regresi di `tests/test_tambahan.py` yang memvalidasi kegagalan sebelum perbaikan dan kelulusan setelah perbaikan untuk Bug 1 sampai Bug 9.
     - Melakukan analisis kueri manual dan menyusun dataset pelabelan `data/ground_truth.csv` untuk evaluasi metrik precision, recall, dan F1.

3. **Mekanisme Pemahaman Bersama:**
   - **Sesi Walkthrough & Code Review:** Setiap kali salah satu anggota menyelesaikan implementasi fitur/bug, dilakukan sesi *walkthrough* kode bersama baris demi baris untuk memastikan kode yang ditulis mudah dipahami oleh anggota lain.
   - **Diskusi Teori Formal:** Mengaitkan setiap keputusan perbaikan kode dengan konsep bahasa formal dari buku *Crafting Interpreters* (Bab 4 Pemindaian Leksikal, Bab 6 Parser Recursive Descent & Panic Mode, serta Bab 11 Resolusi Simbol & Lingkungan Scope).
   - **Simulasi Pengujian Lisan:** Melakukan latihan tanya-jawab mandiri dengan menguji contoh-contoh SQL sampel dan memprediksi pohon sintaksis AST menggunakan flag `--ast` serta matriks operasinya sebelum evaluasi akhir dijalankan.
