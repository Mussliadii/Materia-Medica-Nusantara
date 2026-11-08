# Struktur & Layout Dashboard

Dokumen ini menjelaskan struktur tab dan layout tiap fitur pada
`src/app/streamlit_app.py` — **Materia Medica Nusantara**.

Dashboard terdiri dari 5 tab: **Overview**, **Galeri Tanaman**, **Graph Explorer**,
**Cari by Khasiat**, dan **🧬 Similarity (RDKit)**.

---

## 1. 📊 Overview

Ringkasan statistik keseluruhan dataset.

**Isi:**
- 4 metrik utama: total tanaman (300), jumlah yang punya data senyawa (Duke's),
  jumlah yang punya data tradisional (Duke's), jumlah dengan bukti klinis modern (PubMed)
- Bar chart distribusi tingkat evidensi farmakologi modern
  (🟢 klinis / 🟡 preklinis-review / ⚪ belum ditemukan / ⚫ belum dicek)
- Catatan metodologi singkat (agar tidak overclaim dari hasil pencarian otomatis)

**Layout:**
```
[ Metrik 1 ][ Metrik 2 ][ Metrik 3 ][ Metrik 4 ]   <- st.columns(4)
Subheader: "Distribusi tingkat evidensi..."
[ Bar chart full-width ]
Caption penjelasan metodologi
```

---

## 2. 🌿 Galeri Tanaman

Tab utama untuk eksplorasi data, dengan dua mode yang saling bertukar lewat
`st.session_state["selected_plant"]`.

### Mode Galeri (default)

**Isi:**
- Search bar + 2 filter (famili tumbuhan, tingkat evidensi)
- Grid foto tanaman: 5 kolom × 4 baris (20 tanaman/halaman), setiap kartu
  berisi foto (dari Wikipedia, atau placeholder 🌿 jika tidak ada), nama Latin
  (⭐ jika salah satu dari 13 tanaman flagship), nama lokal/famili singkat,
  dan tombol **"Lihat detail"**
- Tanaman yang punya foto otomatis ditaruh di halaman-halaman awal supaya
  enak dilihat saat demo
- Navigasi halaman (Sebelumnya / indikator halaman / Selanjutnya)
- Expander "Lihat sebagai tabel data" — tabel lengkap dengan progress bar
  visual untuk kolom jumlah senyawa & jumlah kegunaan tradisional

**Layout:**
```
[ Filter famili ][ Filter tingkat evidensi ]   <- st.columns(2)
[ Search bar full-width ]
Caption jumlah hasil

[Kartu][Kartu][Kartu][Kartu][Kartu]            <- 5 kolom, diulang 4 baris
[Kartu][Kartu][Kartu][Kartu][Kartu]
[Kartu][Kartu][Kartu][Kartu][Kartu]
[Kartu][Kartu][Kartu][Kartu][Kartu]

[ ⬅ Sebelumnya ][ Halaman X dari Y ][ Selanjutnya ➡ ]   <- st.columns([1,2,1])

▸ Expander: tabel data lengkap
```

Setiap **kartu** (`st.container(border=True)`):
```
[ Foto 140px atau placeholder ]
**Nama Latin** (⭐ jika flagship)
caption: nama lokal / famili
[ tombol "Lihat detail" full-width ]
```

### Mode Detail (setelah klik "Lihat detail")

**Isi:**
- Tombol "⬅ Kembali ke galeri"
- Foto besar + kredit Wikipedia (kiri) dan info utama: nama, famili, nama
  lokal, link sumber PROSEA, kotak info status evidensi + hit PubMed (kanan)
- Teks deskripsi & kegunaan dari PROSEA (paragraf penuh)
- Dua kolom: **Kegunaan tradisional** (badge/pill coklat, maks 40 + sisanya
  disebut jumlahnya, plus daftar negara literatur) dan **Senyawa & aktivitas
  farmakologi** (dikelompokkan per senyawa — nama senyawa biru tebal, lalu
  badge merah aktivitasnya; top 8 senyawa tampil, sisanya di expander)
- **Khusus 13 tanaman flagship**: section "🔬 Senyawa unggulan" — grid 4 kolom
  kartu senyawa (gambar struktur PubChem, nama, CID/formula/berat molekul,
  link PubChem, badge kemiripan obat dari model RDKit jika ada)
- "Local subgraph" — graph interaktif (pyvis) tanaman→kegunaan/senyawa→aktivitas

**Layout:**
```
[ ⬅ Kembali ke galeri ]

[ Foto + kredit ][ Nama/famili, nama lokal, sumber, info evidensi ]  <- columns([1,2])

#### Deskripsi & kegunaan (PROSEA)
paragraf teks

[ Kegunaan tradisional (badge) ][ Senyawa & aktivitas (grouped badge) ]  <- columns(2)

(jika flagship)
#### 🔬 Senyawa unggulan
caption alasan flagship
[Kartu][Kartu][Kartu][Kartu]   <- 4 kolom, senyawa dgn struktur+similarity

#### Local subgraph
[ Graph interaktif pyvis, full-width, 550px ]
```

---

## 3. 🕸️ Graph Explorer

Versi lebih besar dari "local subgraph" di atas, untuk eksplorasi bebas satu
tanaman pada satu waktu (graph penuh 300 tanaman tidak ditampilkan sekaligus
karena akan jadi "hairball" yang tidak terbaca).

**Layout:**
```
Penjelasan singkat (kenapa subgraph, bukan graph penuh)
[ Selectbox pilih tanaman, full-width ]
Caption jumlah node & edge
[ Graph interaktif pyvis, full-width, 650px ]
```

---

## 4. 🔍 Cari by Khasiat

Pencarian terbalik: dari aktivitas farmakologi → ke tanaman kandidat.

**Isi:**
- Selectbox aktivitas farmakologi (~1.400 pilihan dari Dr. Duke's AGGREGAC)
- Kalimat ringkas jumlah tanaman yang cocok
- Bar chart top 15 tanaman berdasarkan jumlah senyawa terkait
- Daftar detail: per tanaman (top 30), nama + jumlah senyawa, lalu badge
  senyawa-senyawanya
- Jika lebih dari 30 tanaman cocok: expander dengan tabel lengkap

**Layout:**
```
Penjelasan singkat
[ Selectbox pilih aktivitas, full-width ]
Kalimat jumlah tanaman cocok

##### Jumlah senyawa terkait per tanaman (top 15)
[ Bar chart full-width ]

##### Detail senyawa per tanaman
**Tanaman 1** (N senyawa)
[ badge-badge senyawa ]
**Tanaman 2** (N senyawa)
[ badge-badge senyawa ]
...
▸ Expander tabel lengkap (jika >30 tanaman)
```

---

## 5. 🧬 Similarity (RDKit)

Hasil model cheminformatics (Morgan fingerprint + Tanimoto similarity) yang
membandingkan senyawa dari 13 tanaman flagship terhadap 30 obat modern/klasik
yang sudah dikenal.

**Isi:**
- Penjelasan metode (markdown) + catatan peringatan (caption) bahwa kemiripan
  struktural adalah sinyal screening, bukan bukti efikasi
- **Senyawa identik dengan obat yang sudah disetujui**: grid 4 kolom kartu
  (nama senyawa, "= nama obat", nama tanaman asal) — 7 kasus nyata (bukan
  prediksi), misalnya atropine/scopolamine di Datura metel, levodopa di
  Mucuna pruriens
- **Analog struktural**: tabel dengan kolom Tanimoto berupa progress bar
  visual, diurutkan dari skor tertinggi

**Layout:**
```
Penjelasan metode (markdown, beberapa baris)
Caption peringatan interpretasi

### 🟢 Senyawa identik dengan obat yang sudah disetujui/dikenal
Kalimat ringkas jumlah
[Kartu][Kartu][Kartu][Kartu]   <- 4 kolom

### 🟡 Analog struktural (kandidat untuk diteliti lebih lanjut)
[ Tabel dengan kolom Tanimoto = progress bar, full-width ]
```

---

## Komponen & pola layout yang dipakai berulang

- **Badge/pill** (`render_badges`): daftar kata-kata pendek (kegunaan,
  senyawa, aktivitas) dirender sebagai pil berwarna rounded, bukan tabel —
  warna beda per jenis data (use = coklat, chem = biru, activity = merah)
- **Kartu bordered** (`st.container(border=True)`): dipakai untuk kartu
  tanaman di galeri, kartu senyawa flagship, dan kartu "identik dengan obat"
- **Progress bar di dalam tabel** (`st.column_config.ProgressColumn`):
  dipakai untuk kolom numerik (#senyawa, #kegunaan, Tanimoto) supaya tabel
  data mentah tetap ada untuk ditinjau tapi lebih mudah dipindai
- **Expander untuk overflow**: dipakai setiap kali daftar bisa sangat panjang
  (senyawa, tanaman hasil pencarian khasiat) — tampilkan ringkas dulu,
  sisanya di balik expander agar halaman tidak terlalu panjang
- **Session state untuk navigasi**: `selected_plant` (gallery ↔ detail) dan
  `gallery_page` (pagination) dipakai supaya satu tab bisa punya dua "layar"
  tanpa perlu banyak tab terpisah
