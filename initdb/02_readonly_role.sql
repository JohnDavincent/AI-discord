-- Role khusus BACA untuk bot SQL (Vanna).
-- Ini batas keamanan yang sebenarnya: apa pun SQL yang dihasilkan model,
-- Postgres sendiri yang menolak kalau itu operasi tulis.
--
-- Dijalankan otomatis saat volume pertama kali dibuat. Kalau volume sudah ada,
-- jalankan manual:
--   docker compose exec -T db psql -U aidiscord -d brain -f /docker-entrypoint-initdb.d/02_readonly_role.sql

DROP ROLE IF EXISTS brain_reader;

CREATE ROLE brain_reader LOGIN PASSWORD 'Brain_RO_2026_readonly';

GRANT CONNECT ON DATABASE brain TO brain_reader;
GRANT USAGE  ON SCHEMA public   TO brain_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO brain_reader;

-- Tabel yang dibuat setelah ini ikut ter-grant otomatis, jadi tidak perlu
-- diingat-ingat tiap kali menambah tabel baru.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO brain_reader;

-- Batas waktu query dipaksa di level role. Query berat tidak bisa
-- menggantung bot, dan ini tidak bergantung pada benarnya kode Python.
ALTER ROLE brain_reader SET statement_timeout = '5s';
