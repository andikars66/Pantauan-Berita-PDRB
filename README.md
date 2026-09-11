# Pantauan Berita PDRB Lombok Tengah

Aplikasi Streamlit satu halaman untuk mengumpulkan berita dari Serper, Inside Lombok, Lombok Post, Radar Mandalika, Radar Lombok, Suara NTB, dan Pemkab Lombok Tengah, lalu mengklasifikasikannya secara rule-based ke taxonomy PDRB Lapangan Usaha dan Pengeluaran. Hasil hanya disimpan dalam session aktif dan dapat diunduh sebagai dua file Excel.

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

Tanpa key Serper, aplikasi tetap menjalankan seluruh portal aktif dan menandai Serper gagal secara terkontrol.

## Konfigurasi

Semua konfigurasi bisnis berada di `config/`:

- `taxonomy.csv`: hierarchy, kode, label, dan urutan resmi taxonomy.
- `serper_keywords.csv`: keyword pencarian Serper dalam format panjang. Setiap leaf memiliki 3–10 keyword; parent boleh lebih banyak dan harus mewakili setiap direct child.
- `classification_keywords.csv`: daftar `include_keywords`, `exclude_keywords`, `positive_keywords`, dan `negative_keywords` per taxonomy. Daftar dalam satu cell dipisahkan dengan koma `,`. Karena delimiter CSV juga koma, cell berisi beberapa keyword harus diapit tanda kutip ganda (contoh: `"padi,jagung,gabah"`). Excel akan menangani pengutipan ini saat menyimpan CSV. Pemisah lama `|` ditolak dengan pesan validasi.
- `global_exclude_keywords.csv`: term yang mencegah sebuah berita diklasifikasikan ke taxonomy mana pun.
- `geography.csv`: istilah Lombok Tengah, NTB, dan wilayah NTB lain.
- `portals.csv`: enam archive portal yang didukung dan guard `max_pages` per sumber.

Keyword pencarian dan klasifikasi sepenuhnya terpisah. Jika parent dipilih, Serper hanya memakai keyword parent; descendant yang ikut terpilih melalui hierarchy tidak membuat query tambahan. Keyword parent dibagi menjadi pack maksimal sepuluh term per request bila diperlukan.

Konfigurasi divalidasi saat aplikasi dibuka. Kode taxonomy duplikat, parent invalid, keyword Serper kurang, child yang belum terwakili pada keyword parent, rule klasifikasi invalid, atau taxonomy tanpa include rule akan menghasilkan pesan yang jelas.

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

## Pengumpulan paralel

Serper dan portal aktif dikumpulkan bersamaan dengan maksimal empat pekerjaan sumber. Serper menjalankan maksimal tiga query bersamaan dalam batch kecil; jumlah query rencana dan batas hasil per query tetap sama. Key yang ditolak diingat selama satu run, dengan failover dan penghitung yang dilindungi lock. Timeout diulang pada key yang sama dan tidak menonaktifkan key. Tidak ada tambahan dependency untuk paralelisasi.

Tiap portal memakai session tersendiri dan pagination berurutan (satu request pada satu waktu per portal). Progress Streamlit diperbarui pada thread utama. Urutan hasil tetap mengikuti konfigurasi/query, dan kegagalan satu sumber tidak membatalkan sumber lain. Halaman gagal setelah sebagian hasil terkumpul menghasilkan warning beserta hasil parsial.

Portal yang tersedia pada `portals.csv`:

- `inside_lombok`: https://insidelombok.id/category/lombok-tengah/
- `lombok_post`: https://lombokpost.jawapos.com/tag/lombok-tengah
- `radar_mandalika`: https://radarmandalika.id/category/lombok-tengah/
- `radar_lombok`: https://radarlombok.co.id/daerah/lombok-tengah
- `suara_ntb`: https://suarantb.com/category/ntb/lombok-tengah/
- `pemkab_loteng`: https://lomboktengahkab.go.id/berita/

Sumber dapat dinonaktifkan melalui `active=false`. Pemkab memakai offset 15 artikel per halaman; detail artikel dalam periode diambil untuk melengkapi judul arsip yang terpotong. Radar Lombok mengambil tanggal dari detail hanya untuk kartu utama yang tidak mencantumkan tanggal. Sumber lain memakai judul dan cuplikan arsip. Kartu unggulan Radar Lombok/Suara NTB hanya dibaca pada halaman pertama agar tidak menghambat penghentian pagination untuk periode lama. Jika tanggal Suara NTB tidak tampil pada kartu utama, tanggal diambil dari struktur URL artikel bertanggal. Halaman tanpa struktur yang dikenali menghasilkan error/warning, bukan sukses dengan nol artikel.

Penambahan portal, delimiter koma, dan pengumpulan paralel mengikuti permintaan perubahan setelah PRD; `PRD.md` tetap dipertahankan.

## Sumber berita dan sisa kredit

Blok **PARAMETER PENCARIAN** menyediakan checkbox **Sumber berita** untuk Serper dan setiap portal aktif. Semua dicentang secara default. Minimal satu sumber dan satu kategori harus dipilih. Hanya sumber terpilih yang dikumpulkan dan masuk diagnostics; jika Serper tidak dipilih, tidak ada query pencarian Serper yang dibuat atau dikirim. Pemeriksaan saldo akun untuk tag tetap dilakukan terpisah.

Tag **Credits left** menjumlahkan `balance` dari `GET https://google.serper.dev/account` untuk seluruh API key berbeda yang dikonfigurasi (key identik yang terulang dihitung sekali). Pemeriksaan memakai maksimal tiga request bersamaan, timeout terbatas, dan cache per session selama lima menit yang diperbarui pada interaksi berikutnya atau setelah pencarian Serper. Tidak ada key atau respons akun mentah yang ditampilkan/disimpan dalam cache. Jika salah satu saldo gagal diperiksa, total ditampilkan **Tidak tersedia**, disertai jumlah key yang berhasil diperiksa. Tanpa key, tag menampilkan 0 dengan keterangan konfigurasi belum tersedia. Angka merupakan saldo saat pemeriksaan terakhir, sehingga penggunaan dari aplikasi lain dapat membuatnya berubah.
