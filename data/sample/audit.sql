-- Audit akses data
SELECT p.id, p.nama
FROM pelanggan p, pesanan o
WHERE o.pelanggan_id = p.id
  AND o.tanggal BETWEEN :mulai AND :akhir
  OR p.level = 'gold' AND p.aktif = 1;

SELECT p.nama
FROM pelanggan p
WHERE EXISTS (SELECT 1 FROM pembayaran b WHERE b.pelanggan_id = p.id AND b.status = 'GAGAL');

SELECT x.id
FROM pelanggan x
WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x WHERE x.total > 500000);

DELETE FROM sesi s WHERE s.kedaluwarsa < :sekarang;

SELECT s.id FROM pengguna u WHERE u.aktif = 1;

UPDATE pesanan SET status = 'BATAL'
WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);
