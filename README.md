# Pantauan Berita PDRB Lombok Tengah

Aplikasi Streamlit satu halaman untuk mengumpulkan berita dari Serper, Inside Lombok, dan Lombok Post, lalu mengklasifikasikannya secara rule-based ke taxonomy PDRB Lapangan Usaha dan Pengeluaran. Hasil hanya disimpan dalam session aktif dan dapat diunduh sebagai dua file Excel.

## Menjalankan secara lokal

Gunakan Python 3.11 atau 3.12. Dari root repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Isi `.streamlit/secrets.toml` dengan satu atau beberapa key Serper:

```toml
SERPER_API_KEYS = ["key-pertama", "key-kedua"]
```

File tersebut sudah diabaikan Git. Jangan menaruh key pada kode, CSV, README, atau commit.

Jalankan aplikasi:

```powershell
streamlit run app.py
```

Tanpa key Serper, aplikasi tetap menjalankan kedua portal dan menandai Serper gagal secara terkontrol.

## Konfigurasi

Semua konfigurasi bisnis berada di `config/`:

- `taxonomy.csv`: hierarchy, kode, label, urutan resmi, dan threshold klasifikasi.
- `keywords.csv`: rule `include`, `exclude`, `positive`, dan `negative`; ubah secara konservatif karena precision diprioritaskan.
- `geography.csv`: istilah Lombok Tengah, NTB, dan wilayah NTB lain.
- `portals.csv`: dua archive portal yang didukung MVP dan guard `max_pages` per sumber.

Konfigurasi divalidasi saat aplikasi dibuka. Kode taxonomy duplikat, parent invalid, rule invalid, atau taxonomy tanpa include rule akan menghasilkan pesan yang jelas.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests menggunakan mock/fixture dan tidak mengonsumsi kuota Serper atau melakukan crawl portal live.

## Deploy ke Streamlit Community Cloud

1. Push repository ke GitHub tanpa `.streamlit/secrets.toml`.
2. Buat app baru di Streamlit Community Cloud dengan entrypoint `app.py`.
3. Tambahkan `SERPER_API_KEYS` melalui **App settings → Secrets** memakai format TOML di atas.
4. Deploy. Dependency Python murni pada `requirements.txt`; tidak diperlukan database, browser automation, atau service terpisah.

Perubahan HTML portal eksternal dapat membuat satu scraper berstatus warning/gagal, tetapi sumber lain dan ekspor hasil parsial tetap berjalan.
