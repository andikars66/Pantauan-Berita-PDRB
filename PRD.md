# PRD — Sistem Pantauan Berita PDRB Lombok Tengah

**Status:** Final requirements for MVP  
**Versi:** 1.1
**Tanggal:** 11 September 2026
**Target implementasi:** Python + Streamlit Community Cloud  
**Bahasa UI:** Indonesia  
**Target pengguna:** Tim kecil internal (<5 pengguna)  
**Prioritas produk:** (1) akurasi klasifikasi, (2) robustness scraping, (3) kemudahan penggunaan

---

## 0. Instruksi Utama untuk AI Coding Agent

Bangun aplikasi ini sebagai **project baru dari nol**. Repository `jadiinaja/webscrap_berita` hanya boleh digunakan sebagai referensi ide/perilaku; **jangan menjadikannya basis arsitektur atau menyalin desain lama secara mentah**.

Implementasikan MVP secara end-to-end berdasarkan PRD ini dengan prinsip berikut:

1. Jangan menambah fitur yang tidak diminta.
2. Jangan menggunakan database.
3. Jangan menggunakan LLM/AI untuk klasifikasi atau analisis.
4. Jangan membuat autentikasi/login.
5. Jangan membuat halaman admin.
6. Jangan membuat fitur koreksi manual hasil oleh user.
7. Jangan membuat sistem deduplikasi artikel pada MVP.
8. Jangan membuat arsitektur enterprise atau abstraksi berlebihan.
9. Utamakan kode yang modular, mudah dibaca, dan mudah diperbaiki apabila struktur HTML portal berubah.
10. Jika ada detail implementasi kecil yang tidak didefinisikan di PRD, pilih default yang paling sederhana, robust, dan sesuai tujuan produk tanpa meminta keputusan user, selama tidak mengubah perilaku bisnis utama.
11. Seluruh konfigurasi taxonomy, keyword, portal, dan geographic terms harus dapat diubah dari file konfigurasi di repository tanpa mengubah logika inti aplikasi.
12. Semua secret harus berasal dari Streamlit Secrets/environment dan tidak boleh di-hardcode atau tampil pada log/UI.
13. Project dianggap selesai hanya jika seluruh acceptance criteria dan Definition of Done pada PRD ini terpenuhi.

---

# 1. Latar Belakang

Analisis dan penyusunan Produk Domestik Regional Bruto (PDRB) membutuhkan informasi fenomena ekonomi yang terjadi pada periode tertentu. Salah satu sumber fenomena tersebut adalah berita.

Contoh sederhana:

> “Kemarau panjang melanda Lombok Tengah, banyak sawah gagal panen.”

Berita tersebut relevan terhadap lapangan usaha **A.1.a. Tanaman Pangan** dan memberikan indikasi **pengaruh negatif** terhadap aktivitas ekonomi subsektor tersebut.

Berita ekonomi juga dapat berkaitan dengan PDRB dari sisi pengeluaran, misalnya berita pembangunan hotel, belanja pemerintah, konsumsi rumah tangga, investasi, ekspor, atau impor.

Saat ini proses pencarian dan pengelompokan berita dapat memerlukan pencarian manual pada mesin pencari maupun portal lokal. Produk ini bertujuan mempercepat proses tersebut dengan menggabungkan:

1. pencarian Google melalui Serper.dev; dan
2. scraping portal berita lokal Lombok Tengah,

kemudian melakukan klasifikasi berdasarkan **rule/keyword** ke struktur PDB/PDRB menurut Lapangan Usaha dan Pengeluaran.

---

# 2. Product Goal

Menyediakan aplikasi Streamlit satu halaman yang memungkinkan pengguna:

1. memilih tahun dan triwulan;
2. memilih sektor/subsektor PDB/PDRB menurut Lapangan Usaha dan/atau Pengeluaran;
3. menjalankan pengumpulan berita;
4. mengklasifikasikan berita menggunakan aturan keyword;
5. menentukan arah pengaruh Positif/Negatif/Netral menggunakan aturan keyword;
6. melihat ringkasan dan daftar berita yang relevan;
7. mencari, menyaring, dan mengurutkan hasil;
8. mengunduh tabel utama dan raw result dalam format Excel.

---

# 3. Sasaran Keberhasilan

Urutan prioritas:

### P1 — Akurasi klasifikasi
Sistem harus lebih mengutamakan **precision** daripada recall. Lebih baik melewatkan beberapa berita ambigu daripada memasukkan banyak berita yang salah sektor.

### P2 — Robustness scraping
Kegagalan satu sumber tidak boleh membatalkan seluruh proses. Partial result tetap harus dapat digunakan dan diunduh.

### P3 — Mudah digunakan
User non-teknis harus dapat menjalankan proses hanya dengan:
**pilih periode → pilih sektor → klik Mulai → lihat/download hasil**.

---

# 4. Non-Goals / Out of Scope MVP

Berikut secara eksplisit **tidak termasuk MVP**:

- login dan user account;
- database atau persistence server-side;
- scheduler/background scraping;
- scraping otomatis berkala;
- LLM, embeddings, NLP model, sentiment model, atau machine learning;
- manual review/edit hasil;
- deduplikasi exact/fuzzy artikel;
- crawling seluruh internet;
- portal berita selain dua portal yang ditentukan;
- dashboard multi-page;
- role/permission management;
- histori run permanen;
- REST API publik;
- crawling isi artikel hasil Serper;
- CMS/admin UI untuk mengubah keyword;
- analytics kompleks;
- deployment selain Streamlit sebagai requirement utama.

---

# 5. Target User

Pengguna utama adalah staf analis/penyusun PDRB Kabupaten Lombok Tengah.

Karakteristik:

- jumlah pengguna kecil, <5 orang;
- tidak harus memahami Python;
- membutuhkan hasil yang dapat segera digunakan dalam analisis;
- lebih mementingkan hasil relevan dan workflow sederhana daripada fitur teknis yang banyak.

---

# 6. Platform dan Constraints

- Python 3.x yang kompatibel dengan Streamlit Community Cloud.
- Framework UI: Streamlit.
- Satu halaman.
- Tidak ada database.
- State sementara menggunakan `st.session_state`.
- Data dapat hilang ketika session/app restart.
- Output permanen hanya setelah user melakukan download.
- Deployment utama: Streamlit Community Cloud.
- Konfigurasi berada di repository.
- API key Serper berada pada Streamlit Secrets.
- Timezone aplikasi: `Asia/Makassar` (WITA).

---

# 7. Sumber Data

## 7.1 Serper.dev

Digunakan untuk pencarian berita melalui Google Search API.

Klasifikasi hasil Serper dilakukan hanya menggunakan:

- judul;
- snippet/deskripsi hasil pencarian;
- tanggal hasil bila tersedia;
- URL;
- sumber/domain.

**Jangan membuka halaman artikel Serper hanya untuk klasifikasi.**

## 7.2 Portal lokal

MVP hanya melakukan direct scraping terhadap:

1. **Inside Lombok — kategori Lombok Tengah**
   - `https://insidelombok.id/category/lombok-tengah/`

2. **Lombok Post — tag Lombok Tengah**
   - `https://lombokpost.jawapos.com/tag/lombok-tengah`

Portal scraper harus mengambil semua artikel yang dapat ditemukan pada archive/tag page untuk rentang triwulan yang dipilih, lalu artikel diklasifikasikan terhadap keseluruhan taxonomy.

### Aturan portal lokal

- Telusuri pagination sampai mencapai artikel yang lebih tua daripada `start_date` triwulan.
- Jangan terus crawling tanpa batas.
- Jika halaman sudah secara konsisten berada sebelum periode yang dipilih, hentikan pagination.
- Gunakan timeout per request.
- Gunakan retry terbatas.
- Gunakan User-Agent HTTP yang wajar.
- Beri jeda ringan bila diperlukan.
- Parser masing-masing portal harus terpisah sehingga perubahan satu portal tidak merusak portal lain.
- Kegagalan portal harus menghasilkan warning, bukan crash seluruh run.
- Jika archive/tag menyediakan excerpt/snippet, simpan.
- Jika implementasi memungkinkan dengan HTTP biasa, isi artikel portal lokal boleh diekstrak untuk meningkatkan akurasi klasifikasi.
- Jika isi artikel gagal diekstrak, fallback ke `title + excerpt/snippet`.
- Jangan mewajibkan Playwright/Selenium untuk MVP kecuali benar-benar diperlukan agar salah satu dari dua portal berfungsi pada Streamlit Community Cloud.

---

# 8. Periode

## 8.1 Tahun

Pilihan tahun hanya:

- tahun berjalan; dan
- satu tahun kalender sebelumnya.

Contoh pada 6 September 2026:

- 2025
- 2026

Bukan rolling 12 bulan.

## 8.2 Triwulan

- T1: 1 Januari – 31 Maret
- T2: 1 April – 30 Juni
- T3: 1 Juli – 30 September
- T4: 1 Oktober – 31 Desember

Future quarter tidak boleh dapat dipilih.

Jika memilih triwulan yang sedang berjalan:

`effective_end_date = min(quarter_end, current_date)`

Contoh pada 6 September 2026:

- 2026 T1, T2, T3 tersedia.
- 2026 T4 disabled/tidak tersedia.
- rentang 2026 T3 adalah 1 Juli 2026 s.d. 6 September 2026 pada saat run tersebut.

## 8.3 Validasi tanggal

Hasil yang dimasukkan ke dataset final harus memiliki tanggal yang dapat dipetakan ke periode yang dipilih.

- Parse format tanggal Indonesia dan Inggris yang umum.
- Support relative date Serper bila dapat dikonversi secara deterministik terhadap waktu run.
- Record dengan tanggal yang tidak dapat diverifikasi tidak boleh masuk main result.
- Jumlah record yang gagal parse tanggal harus dicatat dalam diagnostics/source status.
- Filter periode dilakukan kembali di sisi aplikasi walaupun Serper sudah diberi date constraint.

---

# 9. Taxonomy

Aplikasi memiliki dua dimensi taxonomy independen:

1. **Lapangan Usaha**
2. **Pengeluaran**

Taxonomy harus berada di `config/taxonomy.csv`.

## 9.1 Skema `taxonomy.csv`

Minimal:

| Kolom | Keterangan |
|---|---|
| `dimension` | `LU` atau `EXP` |
| `taxonomy_code` | kode unik internal/display |
| `parent_code` | parent taxonomy; kosong untuk root |
| `level` | integer level |
| `sort_order` | urutan resmi BPS |
| `label` | nama resmi |
| `is_leaf` | boolean |
| `selectable` | boolean |

Internal code harus unik lintas dimensi. Prefix internal `LU.` dan `EXP.` diperbolehkan.

UI dapat menampilkan kode ringkas, misalnya:

`A.1.a. Tanaman Pangan`

## 9.2 Struktur Lapangan Usaha

Taxonomy mengikuti struktur seri 2010 BPS dan urutan resmi.

### A. Pertanian, Kehutanan dan Perikanan
- A.1. Pertanian, Peternakan, Perburuan dan Jasa Pertanian
  - A.1.a. Tanaman Pangan
  - A.1.b. Tanaman Hortikultura
  - A.1.c. Tanaman Perkebunan
  - A.1.d. Peternakan
  - A.1.e. Jasa Pertanian dan Perburuan
- A.2. Kehutanan dan Penebangan Kayu
- A.3. Perikanan

### B. Pertambangan dan Penggalian
- B.1. Pertambangan Minyak, Gas dan Panas Bumi
- B.2. Pertambangan Batubara dan Lignit
- B.3. Pertambangan Bijih Logam
- B.4. Pertambangan dan Penggalian Lainnya

### C. Industri Pengolahan
- C.1. Industri Batubara dan Pengilangan Migas
- C.2. Industri Makanan dan Minuman
- C.3. Industri Pengolahan Tembakau
- C.4. Industri Tekstil dan Pakaian Jadi
- C.5. Industri Kulit, Barang dari Kulit dan Alas Kaki
- C.6. Industri Kayu, Barang dari Kayu dan Gabus dan Barang Anyaman dari Bambu, Rotan dan Sejenisnya
- C.7. Industri Kertas dan Barang dari Kertas; Percetakan dan Reproduksi Media Rekaman
- C.8. Industri Kimia, Farmasi dan Obat Tradisional
- C.9. Industri Karet, Barang dari Karet dan Plastik
- C.10. Industri Barang Galian Bukan Logam
- C.11. Industri Logam Dasar
- C.12. Industri Barang Logam; Komputer, Barang Elektronik, Optik; dan Peralatan Listrik
- C.13. Industri Mesin dan Perlengkapan
- C.14. Industri Alat Angkutan
- C.15. Industri Furnitur
- C.16. Industri Pengolahan Lainnya; Jasa Reparasi dan Pemasangan Mesin dan Peralatan

### D. Pengadaan Listrik dan Gas
- D.1. Ketenagalistrikan
- D.2. Pengadaan Gas dan Produksi Es

### E. Pengadaan Air, Pengelolaan Sampah, Limbah dan Daur Ulang

### F. Konstruksi

### G. Perdagangan Besar dan Eceran; Reparasi Mobil dan Sepeda Motor
- G.1. Perdagangan Mobil, Sepeda Motor dan Reparasinya
- G.2. Perdagangan Besar dan Eceran, Bukan Mobil dan Sepeda Motor

### H. Transportasi dan Pergudangan
- H.1. Angkutan Rel
- H.2. Angkutan Darat
- H.3. Angkutan Laut
- H.4. Angkutan Sungai, Danau dan Penyeberangan
- H.5. Angkutan Udara
- H.6. Pergudangan dan Jasa Penunjang Angkutan; Pos dan Kurir

### I. Penyediaan Akomodasi dan Makan Minum
- I.1. Penyediaan Akomodasi
- I.2. Penyediaan Makan Minum

### J. Informasi dan Komunikasi

### K. Jasa Keuangan dan Asuransi
- K.1. Jasa Perantara Keuangan
- K.2. Asuransi dan Dana Pensiun
- K.3. Jasa Keuangan Lainnya
- K.4. Jasa Penunjang Keuangan

### L. Real Estat

### M,N. Jasa Perusahaan

### O. Administrasi Pemerintahan, Pertahanan dan Jaminan Sosial Wajib

### P. Jasa Pendidikan

### Q. Jasa Kesehatan dan Kegiatan Sosial

### R,S,T,U. Jasa Lainnya

## 9.3 Struktur Pengeluaran

Gunakan struktur seri 2010 BPS nasional yang menjadi referensi requirement.

### 1. Pengeluaran Konsumsi Rumah Tangga
- 1.a. Makanan dan Minuman, Selain Restoran
- 1.b. Pakaian, Alas Kaki dan Jasa Perawatannya
- 1.c. Perumahan dan Perlengkapan Rumah Tangga
- 1.d. Kesehatan dan Pendidikan
- 1.e. Transportasi dan Komunikasi
- 1.f. Restoran dan Hotel
- 1.g. Lainnya

### 2. Pengeluaran Konsumsi LNPRT

### 3. Pengeluaran Konsumsi Pemerintah
- 3.a. Konsumsi Kolektif
- 3.b. Konsumsi Individu

### 4. Pembentukan Modal Tetap Bruto
- 4.a. Bangunan
- 4.b. Mesin dan Perlengkapan
- 4.c. Kendaraan
- 4.d. Peralatan Lainnya
- 4.e. Cultivated Biological Resources (CBR)
- 4.f. Produk Kekayaan Intelektual

### 5. Perubahan Inventori

### 6. Ekspor Barang dan Jasa
- 6.a. Barang
  - 6.a.1. Barang Nonmigas
  - 6.a.2. Barang Migas
- 6.b. Jasa

### 7. Dikurangi Impor Barang dan Jasa
- 7.a. Barang
  - 7.a.1. Barang Nonmigas
  - 7.a.2. Barang Migas
- 7.b. Jasa

Total PDB dan diskrepansi statistik bukan target klasifikasi berita dan tidak perlu selectable.

## 9.4 Aturan parent-child

- User dapat memilih parent atau child.
- Memilih parent berarti seluruh descendant-nya dianggap selected.
- User dapat memilih hanya satu child.
- UI menyediakan `Pilih Semua` dan `Hapus Semua` untuk masing-masing dimensi.
- Selected taxonomy harus dideduplicasi secara struktural saat diekspansi agar child yang sama tidak diproses dua kali.
- Minimal satu taxonomy harus dipilih sebelum tombol Mulai aktif.

---

# 10. Geographic Relevance

Target geografis utama adalah **Kabupaten Lombok Tengah**, namun berita tingkat **Provinsi Nusa Tenggara Barat** diperbolehkan apabila fenomenanya bersifat provinsi dan secara wajar relevan terhadap Lombok Tengah.

Gunakan `config/geography.csv`.

## 10.1 Skema minimal

| Kolom | Contoh |
|---|---|
| `term` | Lombok Tengah |
| `group` | `local`, `province`, `other_ntb` |
| `active` | true |

Populate awal dengan:

- `Lombok Tengah`
- `Loteng`
- `Praya`
- `Mandalika`
- nama seluruh kecamatan Lombok Tengah
- alias/lokasi penting Lombok Tengah yang relevan
- `Nusa Tenggara Barat`
- `NTB`
- nama kabupaten/kota NTB lainnya sebagai `other_ntb`

## 10.2 Rule geografis

### Local match
Relevan jika text mengandung setidaknya satu `local` term.

### Province-wide match
Jika tidak ada local term, relevan jika:

1. terdapat `province` term; dan
2. tidak didominasi konteks kabupaten/kota NTB lain yang eksplisit.

Untuk precision tinggi, jika berita hanya jelas membahas Bima, Dompu, Sumbawa, Lombok Timur, Lombok Barat, Lombok Utara, atau Kota Mataram tanpa konteks Lombok Tengah/provinsi secara umum, berita ditolak.

Contoh:

- “Produksi padi NTB turun 10 persen” → relevan.
- “Inflasi NTB dipicu kenaikan harga beras” → relevan.
- “Hotel baru dibangun di Kota Bima” → tidak relevan.
- “Produksi jagung Dompu meningkat” → tidak relevan.
- “Produksi padi NTB turun; Lombok Tengah ikut terdampak” → relevan.

## 10.3 Source-context local

Artikel yang berasal langsung dari:

- Inside Lombok kategori Lombok Tengah; atau
- Lombok Post tag Lombok Tengah

boleh dianggap memiliki `source_context_local = true`.

Tetap lakukan classification ekonomi; source context hanya membantu relevansi wilayah, bukan otomatis membuat berita relevan terhadap PDRB.

---

# 11. Keyword Configuration

Keyword pencarian Serper dan keyword klasifikasi harus berada dalam file terpisah. Perubahan pada keyword pencarian tidak boleh mengubah evidence klasifikasi, dan keyword klasifikasi tidak boleh otomatis menjadi query Serper.

## 11.1 `serper_keywords.csv`

Gunakan format panjang satu keyword per row:

| Kolom | Keterangan |
|---|---|
| `taxonomy_code` | kode taxonomy target query |
| `keyword` | term/frasa pencarian yang kuat |
| `priority` | integer positif; angka lebih kecil dipakai lebih dahulu |
| `active` | boolean |

Setiap taxonomy selectable minimal memiliki tiga keyword aktif. Taxonomy leaf maksimal memiliki sepuluh keyword aktif. Keyword parent boleh lebih dari sepuluh, dengan syarat setiap direct child diwakili oleh minimal satu keyword parent yang sama dengan keyword child tersebut.

## 11.2 `classification_keywords.csv`

Gunakan satu row per taxonomy:

| Kolom | Keterangan |
|---|---|
| `taxonomy_code` | kode taxonomy |
| `include_keywords` | daftar term/frasa include dipisahkan `|` |
| `exclude_keywords` | daftar veto khusus taxonomy dipisahkan `|` |
| `positive_keywords` | daftar indikator positif khusus taxonomy dipisahkan `|` |
| `negative_keywords` | daftar indikator negatif khusus taxonomy dipisahkan `|` |

Minimal satu include term harus tersedia untuk setiap taxonomy selectable. Satu include term yang match cukup menjadikan node kandidat, selama tidak diveto oleh exclude taxonomy.

## 11.3 `global_exclude_keywords.csv`

Gunakan format:

| Kolom | Keterangan |
|---|---|
| `keyword` | term/frasa yang mengecualikan artikel dari seluruh klasifikasi |
| `active` | boolean |

Jika global exclude match, artikel tetap boleh berada di Raw Result tetapi tidak boleh memperoleh classification apa pun.

## 11.4 Filosofi rule

- Precision > recall.
- Hindari keyword terlalu umum tanpa konteks.
- Gunakan frasa spesifik bila memungkinkan.
- Exclude taxonomy hanya memveto taxonomy terkait.
- Global exclude memveto seluruh taxonomy.
- Directional keyword harus taxonomy-specific.
- Semua rule harus dapat diedit tanpa mengubah Python.

Contoh konseptual:

```csv
taxonomy_code,include_keywords,exclude_keywords,positive_keywords,negative_keywords
LU.A.1.a,padi|jagung|gabah|panen|sawah,ikan|lele,panen raya|produksi padi meningkat,gagal panen|kekeringan
```

---

# 12. Text Normalization dan Matching

Sebelum matching:

1. lowercase;
2. Unicode normalization;
3. normalisasi whitespace;
4. punctuation normalization seperlunya;
5. jangan melakukan stemming agresif yang dapat menambah false positive.

Term satu kata maupun frasa harus menghormati batas kata agar keyword `bank` tidak salah match ke bagian substring kata lain. Frasa seperti `gagal panen` dicocokkan setelah normalisasi.

Matching harus case-insensitive.

---

# 13. Classification Algorithm

## 13.1 Classification text

### Serper
`classification_text = title + " " + snippet`

Tidak fetch isi artikel.

### Portal lokal
Prioritas:

`title + excerpt/snippet + extracted_article_text`

Jika isi gagal:
`title + excerpt/snippet`

## 13.2 Kandidat taxonomy

Setiap raw record dari **kedua metode** diklasifikasikan terhadap **seluruh taxonomy aktif**, bukan hanya taxonomy yang dipilih user.

Tujuan:

- Raw Result dapat menunjukkan klasifikasi di luar selection.
- Satu artikel dapat sekaligus diklasifikasikan sebagai Lapangan Usaha dan Pengeluaran.
- Main Result kemudian hanya mengambil classification yang berada pada selection user.

## 13.3 Include dan exclusion

Sebelum mengevaluasi taxonomy, periksa global exclude. Jika minimal satu global exclude match, hasil klasifikasi artikel adalah kosong.

Untuk setiap taxonomy node, node lolos jika:

- minimal satu `include_keywords` match; dan
- tidak ada `exclude_keywords` taxonomy tersebut yang match.

`include_score` untuk audit adalah jumlah distinct include term yang match. Exclude taxonomy adalah veto hanya terhadap node terkait.

## 13.4 Multi-label

Satu artikel boleh memiliki banyak classification.

Contoh:

Berita pembangunan hotel dapat masuk:

- F. Konstruksi
- I.1. Penyediaan Akomodasi
- 4.a. PMTB — Bangunan

## 13.5 Ancestor suppression

Jangan menghasilkan redundant parent+child dalam cabang yang sama jika child sudah memiliki evidence yang lebih spesifik.

Contoh:

Jika artikel cocok kuat dengan:

`A.1.a. Tanaman Pangan`

maka jangan otomatis menghasilkan tambahan:

- A.1.
- A.

hanya karena keyword parent juga match.

Sebaliknya, jika text hanya cocok dengan include term parent dan tidak ada child yang cocok, parent boleh menjadi classification.

Prinsip: **gunakan level terdalam yang didukung evidence**.

## 13.6 Node tanpa child

Kategori seperti F. Konstruksi merupakan classification target normal.

---

# 14. Impact Classification

Nilai `Pengaruh` per **article × taxonomy classification**:

- Positif
- Negatif
- Netral

## 14.1 Definisi Netral

Berita relevan terhadap taxonomy, tetapi tidak terdapat indikasi arah perubahan ekonomi yang cukup berdasarkan rule.

Netral bukan error dan bukan “tidak relevan”.

## 14.2 Impact score

Untuk taxonomy classification yang telah lolos:

`positive_score = jumlah distinct positive_keywords yang match`

`negative_score = jumlah distinct negative_keywords yang match`

Decision:

- `positive_score > negative_score` → Positif
- `negative_score > positive_score` → Negatif
- sama-sama 0 → Netral
- skor sama → Netral

Directional keyword tidak diwariskan dari taxonomy lain dan tidak menggunakan kamus sentiment global.

## 14.3 Contoh

“Gagal panen padi di Lombok Tengah”:

- LU.A.1.a → Negatif

“Produksi padi meningkat 20 persen”:

- LU.A.1.a → Positif

“Bupati meninjau sentra produksi padi”:

- LU.A.1.a → Netral, jika rule relevansi match tetapi tidak ada directional rule.

---

# 15. Serper Query Strategy

Tujuan: hemat query tetapi tetap presisi.

## 15.1 Query targets

Serper hanya membuat query berdasarkan **taxonomy yang dipilih user**.

Jika user memilih parent:

- gunakan hanya keyword yang dikonfigurasi pada parent tersebut;
- jangan membuat query terpisah untuk descendant yang ikut terpilih akibat ekspansi UI.

Jika user hanya memilih child, gunakan keyword child tersebut. Jika beberapa sibling dipilih tanpa parent, masing-masing sibling menjadi query target.

## 15.2 Keyword query pack

Jangan mengirim satu request untuk setiap keyword.

Untuk setiap query target:

1. pilih keyword aktif dari `serper_keywords.csv`;
2. urutkan berdasarkan `priority`;
3. gabungkan keyword dengan operator `OR`;
4. bagi keyword menjadi pack maksimal sepuluh term agar query tidak terlalu panjang;
5. parent dengan lebih dari sepuluh keyword menghasilkan beberapa query pack, seluruhnya tetap memakai keyword parent.

Contoh konseptual:

`("Lombok Tengah" OR "Loteng") ("gagal panen" OR "produksi padi" OR "panen raya")`

Tidak ada fallback ke label taxonomy. Kekurangan keyword merupakan configuration error.

## 15.3 Dua geographic query scope

Per query target, maksimal default **dua query scope**:

### Scope A — Local
Fokus Lombok Tengah:
- Lombok Tengah
- Loteng
- alias lokal utama yang masuk akal

### Scope B — Province
Fokus fenomena tingkat NTB:
- Nusa Tenggara Barat
- NTB

Scope province tetap melewati geographic relevance filter setelah hasil diterima.

Konfigurasi harus mencegah jumlah query menjadi tidak terkendali.

## 15.4 Date constraint

Kirim date range triwulan/effective period ke Serper menggunakan mekanisme date filtering yang didukung API.

Setelah menerima hasil, tetap lakukan local date validation.

## 15.5 Result count

Gunakan jumlah hasil per request yang wajar dan supported oleh Serper. Jangan melakukan pagination agresif secara default.

Tujuan bukan “sebanyak mungkin”, tetapi relevansi.

## 15.6 Query diagnostics

Catat:

- jumlah request Serper;
- key index yang dipakai secara internal (jangan tampil key);
- jumlah result diterima;
- quota/auth failure;
- retry;
- failover ke key berikutnya;
- jumlah result lolos periode/geography.

UI cukup menampilkan agregat aman, bukan detail secret.

---

# 16. Serper API Key Pooling

Streamlit Secrets harus mendukung beberapa key.

Contoh konseptual:

```toml
SERPER_API_KEYS = [
  "key-1",
  "key-2",
  "key-3"
]
```

## 16.1 Failover

Mulai dari key pertama yang tersedia.

Rotasi ke key berikutnya hanya untuk error yang menunjukkan key tidak dapat dipakai, misalnya:

- quota exhausted;
- rate limit yang memang terkait key;
- invalid/unauthorized key;
- response API yang secara eksplisit menunjukkan limit key.

Gangguan koneksi/timeout biasa:

- retry key yang sama secara terbatas terlebih dahulu;
- jangan langsung membuang seluruh pool.

Jika semua key tidak dapat dipakai:

- Serper source = failed;
- lanjutkan portal scraping;
- final run = `Selesai dengan peringatan` bila ada sumber lain berhasil.

## 16.2 Security

- Tidak ada key di repository.
- Tidak ada key di UI.
- Tidak ada key di exception yang ditampilkan user.
- Jangan mencatat raw API key di log.
- Sediakan `.streamlit/secrets.toml.example` tanpa key asli.

---

# 17. Portal Scraping Flow

Untuk masing-masing portal:

1. buka halaman archive/tag;
2. parse list artikel;
3. parse tanggal;
4. jika artikel berada di periode: simpan;
5. jika artikel lebih baru: lanjut;
6. jika halaman sudah melewati `start_date`: stop;
7. lanjut pagination bila masih diperlukan;
8. fetch detail artikel bila digunakan oleh implementation untuk classification text;
9. normalisasi record;
10. classification dilakukan pada pipeline berikutnya.

## 17.1 Required raw fields

Internal record minimal:

```text
record_id
source_type        # serper / portal
source
title
date
url
snippet
article_text
source_context_local
period_valid
geo_relevant
```

`record_id` boleh berupa UUID run-time.

## 17.2 Scraper termination guard

Wajib ada guard:

- maximum pages per portal yang reasonable/configurable;
- stop ketika artikel lebih tua dari period;
- timeout;
- retry limit;
- jangan infinite loop jika pagination URL berulang.

---

# 18. No Deduplication

MVP **tidak melakukan deduplication**.

Tidak ada:

- fuzzy title comparison;
- canonical URL merging;
- similarity threshold;
- cross-source duplicate removal.

Jika artikel sama muncul dari dua source/query, keduanya boleh tetap ada.

Akibatnya semua metric harus diberi nama yang tidak mengesankan “unique article” kecuali memang dihitung unique secara eksplisit.

---

# 19. End-to-End Processing Pipeline

Urutan wajib:

1. Validasi input.
2. Resolve `start_date` dan `effective_end_date`.
3. Expand taxonomy selection.
4. Load configuration.
5. Generate Serper query plan.
6. Jalankan Serper dengan API-key pooling.
7. Scrape Inside Lombok.
8. Scrape Lombok Post.
9. Normalisasi raw records.
10. Validasi tanggal.
11. Geographic relevance.
12. Klasifikasikan seluruh raw record terhadap seluruh taxonomy.
13. Tentukan impact per classification.
14. Bentuk raw view.
15. Bentuk main long-format view berdasarkan selected taxonomy.
16. Hitung summary.
17. Render hasil.
18. Buat Excel in-memory saat download.

Tidak perlu menyimpan intermediate file ke disk permanen.

---

# 20. Run Status

Gunakan tiga status:

### `Selesai`
Semua source utama yang dijalankan berhasil tanpa error signifikan.

### `Selesai dengan peringatan`
Minimal satu source menghasilkan usable result/proses selesai, tetapi ada source atau sebagian request yang gagal.

### `Gagal`
Tidak ada pipeline source yang dapat menghasilkan proses usable karena error fatal.

Tidak menemukan berita bukan error.

`0 artikel ditemukan` dapat tetap berstatus `Selesai`.

---

# 21. UI / UX

Aplikasi hanya satu halaman.

## 21.1 Header

Tampilkan:

**Pantauan Berita PDRB Lombok Tengah**

Subjudul singkat:

> Mengumpulkan dan mengklasifikasikan berita ekonomi berdasarkan Lapangan Usaha dan Pengeluaran.

Hindari teks teknis berlebihan.

## 21.2 Panel Input

Urutan:

1. Tahun
2. Triwulan
3. Lapangan Usaha
4. Pengeluaran
5. Tombol Mulai

### Taxonomy selector

Gunakan tampilan hierarchy yang intuitif.

Requirement perilaku:

- parent checkbox/select dapat memilih descendant;
- child tetap selectable individual;
- `Pilih Semua`
- `Hapus Semua`
- parent/child visually distinguishable dengan indentasi;
- tampilkan kode + label.

Tidak wajib memakai custom JS tree library jika dapat dibuat secara sederhana dengan komponen Streamlit.

## 21.3 Tombol Mulai

Disabled bila:

- belum memilih periode valid; atau
- tidak memilih taxonomy apa pun.

Saat processing:

- cegah double submit sebisa mungkin;
- tampilkan progress.

---

# 22. Progress UI

Tahap yang ditampilkan:

1. Persiapan
2. Serper
3. Inside Lombok
4. Lombok Post
5. Normalisasi
6. Klasifikasi
7. Penyusunan Hasil
8. Selesai

Gunakan:

- satu progress bar utama;
- status text ringkas;
- optional live counters.

Contoh:

`Inside Lombok — halaman 4 — 73 artikel periode ditemukan`

Jangan menampilkan debug trace kepada user normal.

---

# 23. Source Status / Diagnostics

Setelah run, tampilkan section kecil:

| Sumber | Status | Ditemukan | Lolos Periode | Warning/Error |
|---|---|---:|---:|---|
| Serper | Berhasil | ... | ... | ... |
| Inside Lombok | Berhasil | ... | ... | ... |
| Lombok Post | Warning | ... | ... | Timeout halaman ... |

Informasi yang berguna:

- request Serper yang digunakan;
- result count;
- artikel portal;
- gagal parse tanggal;
- kegagalan request;
- source failed.

Jangan tampilkan API key atau stack trace.

Detailed Python exception dapat ditulis ke application log secara aman.

---

# 24. Summary

Setelah run tampilkan metric cards:

1. **Raw Records**
2. **Raw Records Terklasifikasi**
3. **Raw Records Tidak Terklasifikasi**
4. **Classification Rows Terpilih**
5. **Positif**
6. **Negatif**
7. **Netral**

Definisi harus eksplisit karena multi-label diperbolehkan.

- `Raw Records` = jumlah record hasil pengumpulan yang lolos periode dan masuk dataset raw.
- `Raw Records Terklasifikasi` = raw record dengan ≥1 classification.
- `Classification Rows Terpilih` = jumlah article × classification yang sesuai taxonomy pilihan user.
- Positif/Negatif/Netral dihitung pada classification rows utama, bukan unique article.

## 24.1 Ringkasan taxonomy

Tampilkan tabel:

| Dimensi | Kode | Sektor/Subsektor | Jumlah Berita |
|---|---|---|---:|

Semua taxonomy yang dipilih user harus tetap muncul walaupun jumlah = 0.

Urutan mengikuti `sort_order` BPS.

## 24.2 Grafik

Hanya grafik yang berguna:

1. bar chart jumlah classification rows per sektor/subsektor terpilih;
2. chart distribusi Positif/Negatif/Netral.

Jangan membuat dashboard penuh grafik.

---

# 25. Main Result Table

Tampilkan setelah summary.

## 25.1 Granularity

**Satu row = satu article × satu classification.**

Jika satu artikel cocok dengan 3 subsektor, muncul 3 baris.

Contoh:

| Sektor/Subsektor | Judul | ... |
|---|---|---|
| F. Konstruksi | Hotel baru ... | ... |
| I.1. Penyediaan Akomodasi | Hotel baru ... | ... |
| 4.a. Bangunan | Hotel baru ... | ... |

## 25.2 Kolom visible

Urutan:

1. `Sektor/Subsektor`
2. `Judul Berita`
3. `Tanggal`
4. `Pengaruh`
5. `Tautan`
6. `Sumber`

Optional internal columns tidak perlu terlihat.

Jika dua dimensi berpotensi membingungkan, `Sektor/Subsektor` dapat diawali badge/prefix singkat seperti `LU —` / `Pengeluaran —`, tetapi label utama tetap ringkas.

## 25.3 Filtering

Sediakan:

- search text;
- filter dimensi;
- filter sektor/subsektor;
- filter pengaruh;
- filter sumber;
- filter tanggal/range bila mudah dilakukan.

Search minimal mencakup:

- judul;
- sektor/subsektor;
- sumber.

Sorting dapat memanfaatkan sortable dataframe headers atau implementasi sederhana yang equivalent.

## 25.4 Urutan default

Default sort:

1. official taxonomy order;
2. tanggal terbaru ke lama;
3. judul.

---

# 26. Raw Result Table

Raw table secara default **disembunyikan** dalam expander/toggle seperti:

`Lihat seluruh hasil scraping (raw)`

## 26.1 Granularity

**Satu row = satu raw scraped/search record.**

Jangan expand raw menjadi satu row per classification.

## 26.2 Kolom

Urutan visible:

1. `Sektor/Subsektor`
2. `Judul Berita`
3. `Tanggal`
4. `Pengaruh`
5. `Tautan`
6. `Sumber`

Untuk multi-label:

- `Sektor/Subsektor` berisi classification dipisahkan `; `
- `Pengaruh` berisi nilai aligned dalam urutan yang sama, sebaiknya format pasangan yang tidak ambigu bila diperlukan.

Contoh yang lebih aman:

`LU.A.1.a=Negatif; EXP.1.a=Netral`

Jika tidak terklasifikasi:

- Sektor/Subsektor kosong
- Pengaruh kosong

Raw table tetap boleh memiliki search/filter sederhana tetapi tidak wajib selengkap main table.

---

# 27. Excel Export

Ada **dua tombol/file Excel terpisah**.

## 27.1 Main Excel

Nama contoh:

`berita_pdrb_2026_T3.xlsx`

Sheets:

### `Ringkasan`
Berisi:

- periode;
- waktu run;
- metric utama;
- taxonomy terpilih lengkap dengan count termasuk 0;
- source status ringkas.

### `Berita`
Long format satu row per article × classification.

Kolom minimal:

- Dimensi
- Kode
- Sektor/Subsektor
- Judul Berita
- Tanggal
- Pengaruh
- Tautan
- Sumber

Urutan taxonomy harus sesuai BPS, bukan alphabetical.

## 27.2 Raw Excel

Nama contoh:

`raw_berita_pdrb_2026_T3.xlsx`

Sheet:

### `Raw`

Satu row per raw record.

Kolom minimal:

- Sektor/Subsektor
- Judul Berita
- Tanggal
- Pengaruh
- Tautan
- Sumber

Boleh tambahkan kolom audit yang berguna seperti:

- Source Type
- Snippet
- Classification Count

selama enam kolom wajib tetap ada dan format tidak membingungkan.

## 27.3 Implementation

- Gunakan `BytesIO`.
- Tidak perlu menulis hasil permanen ke filesystem.
- Gunakan `openpyxl` atau `xlsxwriter`.
- Format header sederhana.
- Freeze header.
- Auto/filter table bila mudah.
- Tanggal sebagai tanggal Excel, bukan string acak.

---

# 28. Session State

Setelah run selesai, simpan pada `st.session_state`:

- run metadata;
- raw dataframe;
- classification dataframe;
- selected result dataframe;
- summary;
- source statuses;
- query diagnostics.

Perubahan filter UI tidak boleh otomatis mengulang scraping.

Run baru hanya dilakukan setelah user klik Mulai kembali.

---

# 29. Error Handling

## 29.1 Network

Setiap source request:

- connect/read timeout;
- retry terbatas;
- error message yang user-friendly.

## 29.2 Portal berubah struktur

Jika selector gagal:

- source status = warning/failed;
- jangan menghasilkan `0 artikel sukses` secara diam-diam jika parser sebenarnya rusak;
- validasi bahwa response mengandung struktur artikel yang reasonable;
- jika tidak, raise source-specific scraping error.

## 29.3 Serper

Bedakan:

- quota/auth error → key failover;
- transient network/server error → retry;
- malformed response → warning;
- semua keys gagal → Serper failed, portal tetap jalan.

## 29.4 Classification/config

Saat load aplikasi:

- validasi duplicate taxonomy code;
- invalid parent;
- missing required CSV columns;
- keyword ke taxonomy code yang tidak ada;
- priority Serper invalid;
- taxonomy dengan keyword Serper kurang dari minimum;
- taxonomy leaf dengan lebih dari sepuluh keyword Serper;
- keyword parent yang belum mewakili direct child;
- taxonomy selectable tanpa include classification;
- duplicate atau konflik include/exclude;
- global exclude invalid.

Configuration error yang membuat klasifikasi tidak aman boleh menjadi fatal dengan pesan jelas.

---

# 30. Performance dan Resource Policy

Tidak ada target jumlah artikel tertentu.

Prinsip:

- relevansi lebih penting daripada volume;
- jangan infinite crawling;
- jangan agresif melakukan request paralel ke portal;
- concurrency terbatas diperbolehkan bila sederhana dan tidak merusak source;
- caching configuration boleh menggunakan `st.cache_data`;
- jangan cache result scraping lintas periode secara membingungkan;
- main UI harus tetap responsif sejauh Streamlit memungkinkan.

Partial result lebih baik daripada seluruh run gagal.

---

# 31. Project Structure

Gunakan struktur tipis seperti:

```text
project/
├── app.py
├── config/
│   ├── taxonomy.csv
│   ├── serper_keywords.csv
│   ├── classification_keywords.csv
│   ├── global_exclude_keywords.csv
│   ├── portals.csv
│   └── geography.csv
├── src/
│   ├── config_loader.py
│   ├── date_utils.py
│   ├── serper_client.py
│   ├── portal_scrapers.py
│   ├── classifier.py
│   ├── pipeline.py
│   └── exporter.py
├── tests/
│   ├── test_classifier.py
│   ├── test_date_utils.py
│   ├── test_taxonomy.py
│   └── test_serper_pool.py
├── .streamlit/
│   └── secrets.toml.example
├── requirements.txt
├── README.md
└── PRD.md
```

Tidak perlu:

- domain layer;
- repository layer;
- database models;
- dependency-injection framework;
- event bus;
- microservices;
- class hierarchy kompleks untuk dua scraper.

---

# 32. `portals.csv`

Minimal:

| id | name | url | active |
|---|---|---|---|
| inside_lombok | Inside Lombok | archive URL | true |
| lombok_post | Lombok Post | tag URL | true |

Jika selector/page pattern harus hard-coded source-specific, simpan di code parser, bukan memaksakan seluruh HTML selector menjadi CSV jika membuat desain rapuh.

---

# 33. Testing Strategy

Testing dibuat minimal tetapi high-value.

Tidak perlu mengejar coverage tinggi.

## 33.1 Wajib

### Taxonomy
- parent selection expand descendants;
- official order dipertahankan;
- invalid parent terdeteksi.

### Classifier
- include match;
- exclusion veto;
- multi-label;
- ancestor suppression;
- parent fallback;
- positive;
- negative;
- neutral no directional rule;
- tie → neutral.

### Date
- T1/T2/T3/T4 boundaries;
- current quarter capped today;
- future quarter unavailable;
- previous/current year options.

### Serper pool
Mock test:

- key1 quota exhausted → key2 dipakai;
- network timeout key1 → retry key1 sebelum rotate;
- semua key gagal → controlled failure.

## 33.2 Tidak diwajibkan

- full integration test portal yang bergantung live HTML;
- browser automation E2E;
- snapshot UI testing.

Scraper parser harus didesain agar fungsi parsing HTML dapat diuji dengan fixture kecil bila Coding Agent dapat melakukannya tanpa banyak overhead.

---

# 34. Logging

Gunakan Python `logging`.

Log teknis boleh mencakup:

- source;
- URL request;
- status code;
- attempt;
- parser error;
- classification count;
- elapsed processing stage.

Jangan log:

- API key;
- full secrets;
- sensitive environment.

UI hanya menampilkan diagnostic ringkas.

---

# 35. Initial Keyword Seed

Coding Agent wajib membuat `serper_keywords.csv`, `classification_keywords.csv`, dan `global_exclude_keywords.csv` awal yang **usable**, bukan file kosong.

Namun tidak perlu berusaha membuat kamus sempurna.

Seed harus:

- keyword Serper mencakup seluruh taxonomy selectable;
- setiap leaf memiliki 3–10 keyword Serper yang kuat;
- keyword parent boleh lebih banyak dan mewakili setiap direct child;
- classification minimal memiliki include keyword yang masuk akal;
- memiliki directional positive/negative rules pada kategori yang jelas;
- menggunakan exclude taxonomy dan global exclude untuk false-positive yang jelas;
- conservative/precision-oriented.

Jika taxonomy sangat luas, node yang sulit diberi directional rule tetap boleh menghasilkan `Netral`.

Keyword harus mudah diedit setelah MVP berjalan.

---

# 36. Main Business Rules Summary

1. Periode = tahun + triwulan.
2. Tahun = current + previous calendar year.
3. Future quarter disabled.
4. Dua taxonomy: LU + Pengeluaran.
5. Hierarchy lengkap.
6. Multi-select.
7. Parent memilih descendants.
8. Multi-label classification.
9. Rule-based only.
10. Impact rule-based only.
11. Netral = relevan tanpa arah.
12. Serper = title + snippet only.
13. Portal = full quarter archive/tag.
14. Portal raw diklasifikasikan terhadap seluruh taxonomy.
15. Serper result juga diklasifikasikan terhadap seluruh taxonomy.
16. Main table hanya classification yang sesuai selection.
17. Raw table seluruh record.
18. Lombok Tengah + province-wide NTB yang relevan.
19. Precision > recall.
20. No dedup.
21. No manual correction.
22. No database.
23. No login.
24. 2 portal direct scraping saja.
25. Multiple Serper API keys dengan failover.
26. Excel main + raw sebagai dua file.
27. Official BPS taxonomy ordering.
28. Zero-count selected taxonomy tetap terlihat pada summary/export.
29. Source failure → partial result + warning.
30. UI satu halaman.
31. Keyword Serper terpisah dari keyword klasifikasi.
32. Parent terpilih memakai keyword parent, bukan query seluruh descendant.
33. Global exclude mencegah seluruh klasifikasi tetapi record tetap dapat muncul di raw.

---

# 37. Acceptance Criteria

## AC-01 — Period selector
Ketika app dibuka, user hanya dapat memilih current year dan previous calendar year.

## AC-02 — Future quarter
Future quarter tidak selectable.

## AC-03 — Current quarter
Current quarter menggunakan tanggal hari ini sebagai effective end.

## AC-04 — Taxonomy dimensions
UI menampilkan Lapangan Usaha dan Pengeluaran sebagai dua kelompok berbeda.

## AC-05 — Hierarchy
Taxonomy mengikuti hierarchy dan official order yang didefinisikan di PRD/config.

## AC-06 — Parent select
Memilih parent mencakup seluruh descendant.

## AC-07 — Select all/clear
Masing-masing dimension memiliki aksi pilih semua/hapus semua.

## AC-08 — Start validation
Run tidak dapat dimulai tanpa minimal satu taxonomy.

## AC-09 — Serper selected query
Serper query plan hanya memakai `serper_keywords.csv`. Parent terpilih memakai keyword parent dan menekan query descendant; child yang dipilih sendiri memakai keyword child.

## AC-10 — Serper classification text
Tidak ada fetching full article untuk hasil Serper; classifier menggunakan title+snippet.

## AC-11 — API key pool
Quota/auth failure key pertama dapat berpindah ke key berikutnya tanpa membatalkan pipeline.

## AC-12 — Portal scope
Direct scraper hanya menggunakan Inside Lombok Lombok Tengah dan Lombok Post tag Lombok Tengah.

## AC-13 — Portal period
Portal crawler berhenti setelah archive melewati batas awal triwulan atau termination guard.

## AC-14 — Full taxonomy classification
Raw record diklasifikasikan terhadap seluruh taxonomy aktif hanya dengan `classification_keywords.csv`. Global exclude menghasilkan classification kosong.

## AC-15 — Geography
Bima-only/non-Lombok-Tengah local news tidak masuk sebagai NTB-wide relevant, sedangkan fenomena province-wide NTB dapat masuk.

## AC-16 — Multi-label
Satu article dapat memiliki ≥2 classification.

## AC-17 — Long main rows
Satu article dengan tiga classification menghasilkan tiga main rows bila ketiganya selected.

## AC-18 — Ancestor suppression
Specific child tidak menghasilkan redundant ancestor row tanpa alasan.

## AC-19 — Impact
Jumlah positive/negative keyword yang match menentukan impact; tie/no direction = Netral.

## AC-20 — Source isolation
Jika satu portal gagal, portal lain/Serper tetap berjalan.

## AC-21 — Warning status
Partial source failure menghasilkan `Selesai dengan peringatan`.

## AC-22 — No news
Run dengan 0 artikel merupakan valid completed run, bukan application crash.

## AC-23 — Progress
User dapat melihat progress stage selama run.

## AC-24 — Source status
Setelah run tersedia ringkasan status Serper, Inside Lombok, Lombok Post.

## AC-25 — Metrics
Metric membedakan Raw Records dan Classification Rows.

## AC-26 — Zero taxonomy
Selected taxonomy tanpa berita tetap muncul dengan count 0.

## AC-27 — Main table
Main table memiliki enam kolom wajib dan filter/search.

## AC-28 — Sort
Default order mengikuti taxonomy BPS lalu tanggal.

## AC-29 — Raw hidden
Raw table tidak langsung memenuhi halaman; default hidden.

## AC-30 — Raw unclassified
Unclassified raw record memiliki classification/impact kosong.

## AC-31 — Main Excel
Tombol download menghasilkan Excel dengan `Ringkasan` dan `Berita`.

## AC-32 — Raw Excel
Tombol terpisah menghasilkan raw Excel.

## AC-33 — No persistence
App dapat berjalan tanpa DB dan tidak membutuhkan penyimpanan hasil server-side.

## AC-34 — No manual editing
Tidak ada UI untuk mengubah classification/impact hasil.

## AC-35 — No dedup
Tidak ada fuzzy/exact deduplication step pada pipeline MVP.

## AC-36 — Config validation
CSV configuration invalid menghasilkan pesan jelas dan tidak diam-diam membuat classification salah.

## AC-37 — Secret safety
API key tidak ada di git/UI/log.

## AC-38 — Tests
High-value unit tests pada section Testing lulus.

## AC-39 — Streamlit deployment
Aplikasi dapat dijalankan lokal dan dikonfigurasi untuk Streamlit Community Cloud.

## AC-40 — README
README menjelaskan setup, secrets, run lokal, konfigurasi CSV, dan deploy.

---

# 38. Definition of Done

Project dianggap selesai apabila:

- [ ] app dapat dijalankan dengan `streamlit run app.py`;
- [ ] tidak memerlukan database;
- [ ] tahun dan triwulan bekerja sesuai aturan;
- [ ] future quarter tidak selectable;
- [ ] taxonomy LU lengkap;
- [ ] taxonomy Pengeluaran lengkap;
- [ ] hierarchy selection bekerja;
- [ ] configuration CSV tersedia dan tervalidasi;
- [ ] Serper keyword seed usable tersedia dan terpisah;
- [ ] classification keyword seed usable tersedia;
- [ ] global exclude tersedia;
- [ ] geography config tersedia;
- [ ] Serper query generation bekerja;
- [ ] multiple API-key failover bekerja;
- [ ] Inside Lombok scraper bekerja atau menghasilkan controlled source error;
- [ ] Lombok Post scraper bekerja atau menghasilkan controlled source error;
- [ ] satu source gagal tidak menyebabkan total crash;
- [ ] date filtering strict;
- [ ] geographic filter bekerja;
- [ ] rule classification bekerja;
- [ ] exclusion bekerja;
- [ ] multi-label bekerja;
- [ ] ancestor suppression bekerja;
- [ ] Positif/Negatif/Netral bekerja;
- [ ] main table long-format;
- [ ] search/filter bekerja;
- [ ] raw table hidden by default;
- [ ] summary metrics benar;
- [ ] selected taxonomy count 0 tetap terlihat;
- [ ] source diagnostics tersedia;
- [ ] progress UI tersedia;
- [ ] main Excel download bekerja;
- [ ] raw Excel download bekerja;
- [ ] hasil berada di session state dan filter tidak memicu re-scrape;
- [ ] secret tidak bocor;
- [ ] required unit tests lulus;
- [ ] README selesai;
- [ ] `.streamlit/secrets.toml.example` tersedia;
- [ ] siap deploy ke Streamlit Community Cloud.

---

# 39. Suggested Implementation Order for Coding Agent

Coding Agent boleh mengerjakan dalam satu task/iteration besar dengan urutan internal berikut:

1. Scaffold minimal project.
2. Buat taxonomy/config CSV.
3. Config validation.
4. Date utilities.
5. Rule classifier + tests.
6. Geography relevance.
7. Serper client + key pool + tests.
8. Inside Lombok scraper.
9. Lombok Post scraper.
10. Pipeline orchestration.
11. Excel exporter.
12. Streamlit UI.
13. Source diagnostics/progress.
14. End-to-end local verification.
15. README + secrets example.
16. Run tests.
17. Final cleanup.

User tidak perlu diminta mengambil keputusan pada setiap tahap kecuali requirement benar-benar mustahil atau bertentangan dengan PRD.

---

# 40. Reference Sources

Requirement taxonomy dan konteks mengacu pada referensi resmi BPS Seri 2010, terutama:

- BPS — `[Seri 2010] PDB Menurut Lapangan Usaha Seri 2010`
- BPS — `[Seri 2010] PDB Triwulanan ADHK menurut Pengeluaran`
- BPS — `Produk Domestik Bruto Indonesia Triwulanan`
- BPS — metadata Pembentukan Modal Tetap Bruto (PMTB)
- BPS — metadata komponen ekspor/impor

Sumber portal MVP:

- Inside Lombok — kategori Lombok Tengah
- Lombok Post — tag Lombok Tengah

Repository referensi produk lama:

- `jadiinaja/webscrap_berita`

Apabila terdapat perbedaan minor label/ejaan taxonomy antara data konfigurasi awal dengan tabel BPS resmi terbaru **Seri 2010**, Coding Agent harus mempertahankan struktur bisnis PRD ini tetapi menggunakan label resmi BPS untuk `taxonomy.csv`.

---

# 41. Final Product Behavior Example

User memilih:

- Tahun: 2026
- Triwulan: III
- `A.1.a. Tanaman Pangan`
- `F. Konstruksi`
- `4.a. Bangunan`

User klik **Mulai**.

Sistem:

1. menentukan rentang 1 Juli 2026 sampai effective end date;
2. membuat query Serper untuk tiga target tersebut dengan local/province scope;
3. menggunakan API key pool jika key terkena quota;
4. scraping seluruh artikel periode dari Inside Lombok kategori Lombok Tengah;
5. scraping seluruh artikel periode dari Lombok Post tag Lombok Tengah;
6. melakukan period/geographic validation;
7. mengklasifikasikan seluruh raw records terhadap semua LU dan Pengeluaran;
8. menentukan impact;
9. membuat main dataset hanya untuk tiga taxonomy selected;
10. menampilkan summary, chart, table, dan source status;
11. user dapat mencari/filter/sort;
12. raw table tersedia tetapi collapsed;
13. user dapat mengunduh:
    - `berita_pdrb_2026_T3.xlsx`
    - `raw_berita_pdrb_2026_T3.xlsx`

Contoh hasil:

| Sektor/Subsektor | Judul Berita | Tanggal | Pengaruh | Tautan | Sumber |
|---|---|---|---|---|---|
| A.1.a. Tanaman Pangan | Kemarau panjang, sejumlah sawah gagal panen | 2026-08-10 | Negatif | ... | Inside Lombok |
| F. Konstruksi | Pembangunan hotel baru dimulai di kawasan Mandalika | 2026-08-18 | Positif | ... | Lombok Post |
| 4.a. Bangunan | Pembangunan hotel baru dimulai di kawasan Mandalika | 2026-08-18 | Positif | ... | Lombok Post |

Berita kedua muncul dua classification rows karena secara ekonomi relevan terhadap Konstruksi dan PMTB Bangunan.

---

**END OF PRD**
