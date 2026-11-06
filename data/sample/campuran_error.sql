-- Statement kedua mengandung kesalahan sintaks
SELECT id, nama FROM pelanggan WHERE aktif = 1;

SELECT id nama, FROM pesanan;

UPDATE produk SET stok = stok - 1 WHERE id = :id;

DELETE FROM keranjang WHERE dibuat < :batas;
