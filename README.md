# Sistem Presensi Siswa — Kelas XI TKJ 1

Sistem Presensi Siswa adalah aplikasi berbasis web (Python Flask) untuk mengelola data siswa kelas **XI TKJ 1 — SMKN 8 Kota Bekasi**, mencatat kehadiran harian (baik oleh pengurus kelas maupun presensi mandiri siswa), serta menghasilkan laporan presensi secara otomatis (harian, mingguan, dan bulanan).

## 🚀 Fitur Utama

*   **Autentikasi & Akun:** Sistem login aman berbasis peran untuk **Admin Kelas** (Ketua Kelas dan Sekretaris dengan kunci akses admin) serta **Siswa** (wajib ganti kata sandi sementara saat login pertama).
*   **Manajemen Siswa:** Tambah, edit, aktif/nonaktifkan akun, reset kata sandi sementara, dan lihat detail riwayat kehadiran tiap siswa.
*   **Pencatatan Presensi Cepat & Mandiri:**
    *   **Tombol Cepat Admin:** Mencatat seluruh siswa hadir sekaligus (*Tandai Semua Hadir*) dengan satu klik, lalu mengubah status secara langsung di tabel bagi siswa yang tidak masuk (**Izin**, **Sakit**, atau **Alpa**).
    *   **Presensi Siswa:** Input kehadiran mandiri sesuai jadwal sesi dan verifikasi lokasi GPS sekolah (opsional).
*   **Laporan Komprehensif:** Pembuatan rekap kehadiran **harian**, **mingguan**, dan **bulanan** lengkap dengan tata letak cetak serta ekspor ke **CSV** dan **Excel (`.xlsx`)**.
*   **Tampilan & Pengaturan Sistem:** Dilengkapi *switch* **Tema Gelap / Terang (*Dark Mode*)**, identitas **Logo Kelas XI TKJ 1**, serta konfigurasi jadwal sesi harian, titik lokasi sekolah, dan tahun ajaran.

## 🛠️ Teknologi yang Digunakan

*   **Backend:** Python (Flask)
*   **Database:** SQLite (dikelola via `app/db.py` & folder `migrations/`)
*   **Frontend:** HTML, CSS, JavaScript (Jinja2 Templates, tanpa ketergantungan CDN eksternal)
*   **Ekspor Data:** `openpyxl` (Excel `.xlsx`) & modul `csv`

## 📦 Prasyarat

Pastikan Anda sudah menginstal:
*   [Python 3.10+](https://www.python.org/downloads/)
*   `pip`

## ⚙️ Cara Instalasi & Menjalankan Aplikasi

1. **Clone repositori**
   ```bash
   git clone https://github.com/USERNAME/absensi-xi-tkj-1.git
   cd absensi-xi-tkj-1
   ```

2. **Buat Virtual Environment**
   ```bash
   python -m venv venv

   # Aktifkan virtual environment (Windows):
   venv\Scripts\activate
   # Aktifkan virtual environment (Mac/Linux):
   source venv/bin/activate
   ```

3. **Instal dependensi**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurasi Environment**
   Salin file `.env.example` menjadi `.env`, lalu isi `APP_ENV=development` dan `ADMIN_ACCESS_KEY` sesuai keinginan Anda.
   ```bash
   cp .env.example .env
   ```

5. **Inisialisasi Database & Akun Awal**
   Jalankan perintah berikut melalui `manage.py` untuk membuat tabel database, akun pengurus kelas (Ketua Kelas / Sekretaris), dan mengimpor daftar 44 siswa:
   ```bash
   python manage.py init-db
   python manage.py create-admin --name "Ketua Kelas XI TKJ 1"
   python manage.py create-admin --name "Sekretaris XI TKJ 1"
   python manage.py import-students data/daftar_siswa_XI_TKJ_1.md
   ```

6. **Jalankan Aplikasi**
   Jalankan server web menggunakan Flask dan `wsgi.py`:
   ```bash
   flask --app wsgi run
   ```
   Aplikasi akan berjalan di `http://127.0.0.1:5000/`.

## 📁 Struktur Projek Utama

*   `app/`: Berisi kode sumber utama aplikasi (`routes/`, `services/`, `templates/`, `static/`, `security.py`, `db.py`).
*   `data/`: Penyimpanan data pendukung (`daftar_siswa_XI_TKJ_1.md` untuk impor daftar siswa kelas).
*   `migrations/`: Berisi skrip SQL (`001_init.sql`) untuk skema tabel database.
*   `tests/`: Berisi pengujian otomatis aplikasi (`python -m unittest discover -s tests -t . -v`).
*   `manage.py` & `wsgi.py`: *Entry point* untuk administrasi CLI dan menjalankan server aplikasi.
