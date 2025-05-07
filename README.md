# YT-2-Stems

**YT‑2‑Stems** lets you drop in any song (or paste a YouTube/SoundCloud link) and instantly get clean vocal, drum, bass, and other stems—plus its BPM and musical key.  
It wraps state‑of‑the‑art **machine‑learning models** (Demucs for stem separation and Essentia for tempo/key analysis) in a one‑window Python GUI.

A cross-platform Python GUI that:

1. **Downloads** audio from **YouTube or SoundCloud** via `yt-dlp` – or lets you drag-and-drop / select a local file.  
2. **Transcodes** to MP3 at the bitrate you choose (FFmpeg).  
3. **Splits** the track into stems with **Demucs v4** (choose any model; 2-stem or full).  
4. **Analyzes** the original track’s **tempo (BPM)** and **musical key** using **Essentia**.  
5. Shows a live **progress bar** and detailed log.

Result: a folder of stems (vocals, drums, bass, other, etc.) plus BPM + key read-outs.

---

## ✨ Features

|                | Details |
|----------------|---------|
| **Drag-and-drop / File picker** | Load `mp3 / wav / flac / m4a` or paste a YouTube/SoundCloud URL |
| **Model selector** | `htdemucs`, `mdx`, fine-tuned, 6-stem, 2-stem checkbox |
| **BPM + Key**  | Essentia `RhythmExtractor2013` & `KeyExtractor` |
| **Live status**| Download → Transcode → Split with % progress |
| **Pure Python**| Single `yt2stems.py` (≈300 LOC) + PySide 6 GUI |
| **One-file build** | `pyinstaller --onefile --noconsole yt2stems.py` |

---

## 📦 Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **Python 3.9+** | runtime | [python.org](https://python.org) |
| **FFmpeg**      | MP3 transcode | `brew install ffmpeg` / `choco install ffmpeg` |

Dependencies are managed via `requirements.txt`

---

## 🚀 Quick Start

```bash
# clone
git clone https://github.com/yourname/yt2stems.git
cd yt2stems

# venv (recommended to isolate dependencies)
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# run
python3 yt2stems.py