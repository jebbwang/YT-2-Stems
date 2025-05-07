# yt2stems is a GUI for downloading and splitting audio from YouTube and SoundCloud using yt-dlp, ffmpeg, and demucs.
# yt-dlp  ➜  MP3  ➜  Demucs Split  – with model selector, stem options & progress bar
# ---------------------------------------------------------------
#  Requires:  Python ≥3.9, ffmpeg on PATH, PySide6, yt-dlp, demucs, torch
# ---------------------------------------------------------------

import re
import sys
import tempfile
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QTextEdit, QFileDialog, QProgressBar, QHBoxLayout
)
from PySide6.QtCore import Qt, QThread, Signal


import essentia.standard as es

def analyze_bpm_key(path: str) -> tuple[int, str]:
    """
    Analyze the audio file at `path` and return (tempo, key) using Essentia.
    """
    # Load audio at 44.1 kHz
    audio = es.MonoLoader(filename=path, sampleRate=44100)()
    # Extract tempo in BPM
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    # Extract key and scale
    key, scale, strength = es.KeyExtractor()(audio)
    key_name = f"{key} {scale}"
    return int(round(bpm)), key_name


# ────────────────────────── Worker thread ──────────────────────────
class StemWorker(QThread):
    log = Signal(str)      # textual logging
    done = Signal(str)     # finished / error message
    prog = Signal(int)     # 0-100 int

    def __init__(self, url: str, bitrate: str, model: str, two_stem: bool, outdir: Path, is_file: bool = False):
        super().__init__()
        self.url = url
        self.bitrate = bitrate
        self.model = model
        self.two_stem = two_stem
        self.outdir = outdir
        self.is_file = is_file

    def _run_subprocess(self, cmd: list[str], progress_offset: int = 0, progress_span: int = 0):
        """Run *cmd* and stream stderr → progress callback."""
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
        pattern = re.compile(r"(\d{1,3})%")
        for line in proc.stderr:
            if progress_span:
                m = pattern.search(line)
                if m:
                    pct = int(m.group(1))
                    self.prog.emit(progress_offset + pct * progress_span // 100)
        proc.wait()
        if proc.returncode:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def run(self):
        try:
            # 1️⃣  Prepare input (download or local file)
            if self.is_file:
                tmp_path = Path(self.url)
                title = tmp_path.stem
                self.log.emit(f"📁  Using local file: {tmp_path.name}")
                self.prog.emit(10)
            else:
                import yt_dlp
                self.log.emit("⏬  Fetching & downloading audio …")
                self.prog.emit(0)
                ydl_opts = {
                    "quiet": True,
                    "format": "bestaudio/best",
                    "outtmpl": f"{tempfile.gettempdir()}/%(title)s.%(ext)s",
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url, download=False)
                    title = yt_dlp.utils.sanitize_filename(info["title"])
                    tmp_path = Path(tempfile.gettempdir()) / f"{title}.{info['ext']}"
                    ydl.download([self.url])
                self.prog.emit(10)

            # 🔍 Analyze BPM and key
            bpm, key = analyze_bpm_key(str(tmp_path))
            self.log.emit(f"🎚️  Detected tempo: {bpm} BPM")
            self.log.emit(f"🔑  Estimated key: {key}")

            # 2️⃣  Transcode to MP3
            self.log.emit("🔄  Transcoding to MP3 …")
            mp3_path = self.outdir / f"{title}_{self.bitrate}k.mp3"
            ff_cmd = [
                "ffmpeg", "-y", "-i", str(tmp_path),
                "-vn", "-c:a", "libmp3lame", "-b:a", f"{self.bitrate}k", str(mp3_path)
            ]
            self._run_subprocess(ff_cmd)
            self.prog.emit(40)

            # 3️⃣  Split with Demucs
            self.log.emit(f"🎛️  Splitting with Demucs ({self.model}) …")
            demucs_cmd = [
                sys.executable, "-m", "demucs",
                str(mp3_path), "-o", str(self.outdir), "-n", self.model,
            ]
            if self.two_stem:
                demucs_cmd += ["--two-stems", "vocals"]
            self._run_subprocess(demucs_cmd, progress_offset=50, progress_span=50)
            self.prog.emit(100)

            tmp_path.unlink(missing_ok=True)
            self.done.emit("✅  Finished – stems ready!")
        except Exception as e:
            self.done.emit(f"❌  Error: {e}")


# ──────────────────────────── GUI ─────────────────────────────────
class MainWindow(QWidget):
    # Model key, description for dropdown
    MODEL_OPTIONS = [
        ("htdemucs",    "htdemucs (4 stems, fast)"),
        ("htdemucs_ft", "htdemucs_ft (4 stems, fine-tuned)"),
        ("mdx",         "mdx (4 stems, fastest)"),
        ("mdx_extra_q", "mdx_extra_q (4 stems, highest quality)"),
        ("hdemucs_mmi", "hdemucs_mmi (6 stems, adds guitar & piano)")
    ]

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("YT2Stems")
        self.resize(680, 520)

        # URL input
        self.url_edit = QLineEdit(placeholderText="Paste YouTube / SoundCloud link OR drag & drop file (mp3, wav, flac, m4a) here")

        # File chooser button
        self.file_btn = QPushButton("Choose file…")
        self.file_btn.setToolTip("Select a local audio file instead of a URL")

        # Bitrate selector
        self.bitrate_combo = QComboBox()
        for br in ("96", "128", "192", "320"):
            self.bitrate_combo.addItem(f"{br} kbps", br)
        self.bitrate_combo.setCurrentIndex(3)

        # Model selector
        self.model_combo = QComboBox()
        for key, desc in self.MODEL_OPTIONS:
            self.model_combo.addItem(desc, key)

        # Two-stem mode
        self.twoStemChk = QCheckBox("2 stems (vocals + accompaniment)")

        # Output folder choice
        self.out_btn = QPushButton("Choose output folder …")
        self.out_lbl = QLabel("(current directory)")
        self.out_dir = Path.cwd()

        # Run button, progress bar, log
        self.run_btn = QPushButton("Download & Split")
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.log_view = QTextEdit(readOnly=True)

        # Layout
        lay = QVBoxLayout(self)
        # youtube and soundcloud links are supported
        lay.addWidget(QLabel("URL / File:"));
        lay.addWidget(self.url_edit)
        lay.addWidget(self.file_btn)
        hb = QHBoxLayout();
        hb.addWidget(QLabel("Bitrate:")); hb.addWidget(self.bitrate_combo)
        hb.addWidget(QLabel("Model:")); hb.addWidget(self.model_combo)
        lay.addLayout(hb)
        lay.addWidget(self.twoStemChk)
        lay.addWidget(self.out_btn); lay.addWidget(self.out_lbl)
        lay.addWidget(self.run_btn); lay.addWidget(self.progress); lay.addWidget(self.log_view)

        # Signals
        self.out_btn.clicked.connect(self.pick_outdir)
        self.run_btn.clicked.connect(self.start_job)
        self.file_btn.clicked.connect(self.choose_file)

    def pick_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.out_dir = Path(d); self.out_lbl.setText(str(self.out_dir))

    def start_job(self):
        url = self.url_edit.text().strip()
        from pathlib import Path
        is_file = Path(url).is_file()
        if not url:
            self.log("Paste a link first."); return
        br = self.bitrate_combo.currentData()
        model = self.model_combo.currentData()
        two = self.twoStemChk.isChecked()
        self.log(f"\n---  New job  ( {br} kbps  |  {model}  |  {'2-stem' if two else 'full'}) ---")
        self.progress.setValue(0); self.run_btn.setEnabled(False)

        self.worker = StemWorker(url, br, model, two, self.out_dir, is_file)
        self.worker.log.connect(self.log)
        self.worker.done.connect(self.job_done)
        self.worker.prog.connect(self.progress.setValue)
        self.worker.start()

    def log(self, msg: str):
        self.log_view.append(msg)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def job_done(self, msg: str):
        self.log(msg); self.run_btn.setEnabled(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        from pathlib import Path
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).suffix.lower() in ('.mp3', '.wav', '.flac', '.m4a'):
                self.url_edit.setText(path)
        event.accept()

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a)"
        )
        if path:
            self.url_edit.setText(path)


# ───────────────────────────  main  ───────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    wnd = MainWindow(); wnd.show()
    sys.exit(app.exec())