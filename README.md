# 🎬 SDT Subtitle Toolset for Metal Gear Solid 2 & 3

This toolset allows you to **extract subtitles from `.SDT` files** and **import edited subtitles back into `.SDT` files**, supporting both **Metal Gear Solid 2 & 3** (PC and PS3 versions).

<span style="color:red">❌ Note: This is not for Codec, for Codec use Giza GCX Tool</span>
---

## ✅ Requirements

Install the following dependency before running either script:

```bash
pip install colorama
```

---

## 📦 Tools Included

### 1. 📤 `0000.SDT_extractor.py` – Extract Subtitles to CSV

Extracts subtitles from an `.SDT` file into a CSV format for editing.

#### 🔧 Usage:
```bash
python 0000.SDT_extractor.py input.sdt output.csv
```

#### 📌 Example:
```bash
python 0000.SDT_extractor.py t00a2d.sdt t00a2d.csv
```

#### 📋 Output CSV Format:

| Start Time | End Time | Lang ID | Text                         |
|------------|----------|---------|------------------------------|
| 54738      | 55671    | [ENG]   | Our boy is right on schedule.|

---

### 2. 📥 `0000.SDT_importer.py` – Import CSV Back to `.SDT`

Rebuilds an `.SDT` file using a CSV of subtitles, preserving original code and audio data.

#### 🔧 Usage:
```bash
python 0000.SDT_importer.py input.csv output.sdt
```

> ⚠️ The `output.sdt` must already exist and be the same file that was originally extracted.

#### 📌 Example:
```bash
python 0000.SDT_importer.py t00a2d_edited.csv t00a2d.sdt
```

#### 📝 Notes:
- Uses the original `.sdt` as a template.
- Preserves internal structure, padding, and offsets.
- Keeps code blocks and audio/data intact.

---

## 📄 Language Code Mapping

Supported language codes in `[Lang ID]` column:

| Label     | Language        |
|-----------|-----------------|
| `[ENG]`   | English         |
| `[FRE]`   | French          |
| `[GER]`   | German          |
| `[ITA]`   | Italian         |
| `[SPA]`   | Spanish         |
| `[JPN]`   | Japanese        |

---

## 🛠 Features

- Clean subtitle extraction and re-import workflow
- Full support for PACB block parsing
- Maintains alignment, padding, and internal offsets
- Preserves embedded code and audio sections are not tested, only preserved as raw data
- UTF-8 compatible with fallback decoding

---
