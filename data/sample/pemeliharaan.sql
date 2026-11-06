/* Skrip pemeliharaan data pelanggan.
   Catatan lama: UPDATE pelanggan_lama sudah tidak dipakai. */
select c.id, c.nama, a.kota
from crm.pelanggan c
left outer join crm.alamat a on a.pelanggan_id = c.id
where c.nama = 'O''Brien' or c.kota = 'Bandung' and c.aktif = 1;

update crm.pelanggan
set nama = 'O''Neil', diubah_oleh = :pengguna
where id = :id;

insert into crm.log_perubahan (pelanggan_id, keterangan)
select id, 'nama diperbarui' from crm.pelanggan where id = :id;

delete from crm.alamat
where pelanggan_id not in (select id from crm.pelanggan);
