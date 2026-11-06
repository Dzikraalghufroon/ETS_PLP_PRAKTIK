-- Laporan penjualan bulanan
-- DELETE FROM pelanggan   (baris ini komentar, bukan perintah)
SELECT p.nama, SUM(o.total) AS omzet
FROM pelanggan p
JOIN pesanan o ON o.pelanggan_id = p.id
WHERE o.status = 'LUNAS' AND o.catatan <> 'FROM rahasia'
GROUP BY p.nama;

INSERT INTO arsip_pesanan (id, total)
SELECT id, total FROM pesanan WHERE tanggal < :batas;

UPDATE pelanggan SET level = 'gold'
WHERE id IN (SELECT pelanggan_id FROM pesanan WHERE total > 1000000);

DELETE FROM pesanan WHERE tanggal < :batas;
