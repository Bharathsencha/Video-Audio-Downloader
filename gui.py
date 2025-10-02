# gui.py
import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QLabel, QPushButton, QLineEdit, QHBoxLayout,
    QVBoxLayout, QApplication, QRadioButton, QComboBox, QFileDialog,
    QListWidget, QMessageBox, QGroupBox, QGridLayout, QCheckBox, QInputDialog,
    QButtonGroup
)

import backend
import playlist

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")

class FetchThread(QThread):
    fetched = Signal(object, object)  # (info dict or None, error str or None)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            info = backend.fetch_info(self.url)
            self.fetched.emit(info, None)
        except Exception as e:
            self.fetched.emit(None, str(e))


class DownloadThread(QThread):
    progress = Signal(str)  # human readable progress
    finished = Signal(bool, object)  # success, error-or-result

    def __init__(self, url, out_dir, video_format_id=None, audio_only=False, is_playlist=False):
        super().__init__()
        self.url = url
        self.out_dir = out_dir
        self.video_format_id = video_format_id
        self.audio_only = audio_only
        self.is_playlist = is_playlist
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.terminate()

    def progress_hook(self, d):
        if self._cancelled:
            return
        # called by yt-dlp; d is dict; create a short message
        status = d.get("status")
        if status == "downloading":
            percent = d.get("_percent_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            filename = d.get("filename", "")
            if filename:
                # Extract just the filename for display
                filename = os.path.basename(filename)
                if len(filename) > 40:
                    filename = filename[:37] + "..."
            
            if percent and eta and filename:
                self.progress.emit(f"Downloading: {filename}\n{percent} ETA: {eta}")
            elif percent and filename:
                self.progress.emit(f"Downloading: {filename}\n{percent}")
            elif percent:
                self.progress.emit(f"Downloading: {percent}")
            else:
                self.progress.emit("Downloading...")
        elif status == "finished":
            self.progress.emit("Download finished, post-processing...")
        else:
            self.progress.emit("Downloading...")

    def run(self):
        try:
            if self._cancelled:
                return
            
            if self.is_playlist:
                # Use playlist module
                if self.audio_only:
                    playlist.download_playlist_audio(
                        self.url,
                        self.out_dir,
                        progress_hook=self.progress_hook
                    )
                else:
                    playlist.download_playlist_video(
                        self.url,
                        self.out_dir,
                        video_format_id=self.video_format_id,
                        progress_hook=self.progress_hook
                    )
            else:
                # Use backend for single video
                backend.download_video(
                    self.url,
                    self.out_dir,
                    video_format_id=self.video_format_id,
                    audio_only=self.audio_only,
                    progress_hook=self.progress_hook
                )
            
            if not self._cancelled:
                self.finished.emit(True, None)
        except Exception as e:
            if not self._cancelled:
                self.finished.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Py YTDLP GUI - Video & Playlist Downloader")
        self.setMinimumSize(750, 520)
        self._apply_light_theme()

        self._build_ui()
        self.load_history()

    def _build_ui(self):
        w = QWidget()
        layout = QVBoxLayout()
        top_row = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube / URL here and press Search")
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.on_search)

        top_row.addWidget(self.url_input)
        top_row.addWidget(self.btn_search)

        layout.addLayout(top_row)

        # Thumbnail and info area
        info_row = QHBoxLayout()

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setStyleSheet("border: 1px solid #cfcfcf; background: #f7fbff;")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        info_row.addWidget(self.thumbnail_label)

        right_info = QVBoxLayout()

        # Download Mode: Single or Playlist
        mode_box = QGroupBox("Download Mode")
        mode_layout = QHBoxLayout()
        self.rb_single = QRadioButton("Single Video")
        self.rb_playlist = QRadioButton("Playlist")
        self.rb_single.setChecked(True)
        self.rb_single.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.rb_single)
        mode_layout.addWidget(self.rb_playlist)
        mode_box.setLayout(mode_layout)
        right_info.addWidget(mode_box)

        # Video / Audio radio
        type_box = QGroupBox("Output")
        type_layout = QHBoxLayout()
        self.rb_video = QRadioButton("Video")
        self.rb_audio = QRadioButton("Audio")
        self.rb_video.setChecked(True)
        self.rb_video.toggled.connect(self.on_type_changed)
        type_layout.addWidget(self.rb_video)
        type_layout.addWidget(self.rb_audio)
        type_box.setLayout(type_layout)
        right_info.addWidget(type_box)

        # quality combobox
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Select quality after search")
        right_info.addWidget(self.quality_combo)

        # download location
        dl_layout = QHBoxLayout()
        self.folder_display = QLineEdit(DEFAULT_DOWNLOAD_DIR)
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.clicked.connect(self.browse_folder)
        dl_layout.addWidget(self.folder_display)
        dl_layout.addWidget(self.btn_browse)
        right_info.addLayout(dl_layout)

        # download button and progress label
        self.btn_download = QPushButton("Download")
        self.btn_download.clicked.connect(self.on_download)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.on_cancel_download)
        self.btn_cancel.setEnabled(False)
        
        download_buttons = QHBoxLayout()
        download_buttons.addWidget(self.btn_download)
        download_buttons.addWidget(self.btn_cancel)
        
        self.progress_label = QLabel("")
        self.progress_label.setWordWrap(True)
        right_info.addLayout(download_buttons)
        right_info.addWidget(self.progress_label)

        info_row.addLayout(right_info)
        layout.addLayout(info_row)

        # History + controls
        hist_row = QHBoxLayout()
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.on_history_open)

        hist_controls = QVBoxLayout()
        self.btn_clear_history = QPushButton("Clear History")
        self.btn_clear_history.clicked.connect(self.clear_history)
        self.btn_show_history = QPushButton("Refresh History")
        self.btn_show_history.clicked.connect(self.load_history)
        hist_controls.addWidget(self.btn_show_history)
        hist_controls.addWidget(self.btn_clear_history)
        hist_controls.addStretch()

        hist_row.addWidget(self.history_list, 1)
        hist_row.addLayout(hist_controls)

        layout.addLayout(hist_row)
        w.setLayout(layout)
        self.setCentralWidget(w)

        # internal state
        self.current_info = None
        self.current_thumbnail_url = None
        self.playlist_detected = False
        self.is_playlist_url = False
        self._dl_thread = None

    # ---------- UI actions ----------
    def on_cancel_download(self):
        if self._dl_thread and self._dl_thread.isRunning():
            self._dl_thread.cancel()
            self.progress_label.setText("Cancelling download...")
            self.btn_cancel.setEnabled(False)

    def _apply_light_theme(self):
        # blue & white theme (light)
        style = """
        QWidget { background: #f4fbff; color: #0b2545; font-family: Inter, Arial; }
        QLineEdit, QComboBox, QListWidget { background: white; border: 1px solid #c7e0ff; padding: 6px; }
        QPushButton { background: #1e88ff; color: white; border-radius: 6px; padding: 6px 10px; }
        QPushButton#small { background: transparent; color: #1e88ff; border: 1px solid #c7e0ff; padding: 4px; }
        QLabel { }
        """
        self.setStyleSheet(style)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select download folder", self.folder_display.text())
        if folder:
            self.folder_display.setText(folder)

    def on_mode_changed(self):
        """Called when user switches between Single and Playlist mode"""
        pass  # Nothing special needed here

    def on_type_changed(self):
        # When switching between video and audio, update the quality combo automatically
        if self.current_info:
            self.update_quality_combo()

    def update_quality_combo(self):
        """Update quality combo based on current selection and available info"""
        if self.rb_audio.isChecked():
            # Audio selected
            self.quality_combo.clear()
            self.quality_combo.addItem("Best Audio Quality (MP3)")
            self.quality_combo.setEnabled(False)
        else:
            # Video selected
            self.quality_combo.setEnabled(True)
            if self.current_info:
                formats = backend.parse_video_formats(self.current_info)
                self.quality_combo.clear()
                for fmt_id, label in formats:
                    self.quality_combo.addItem(label, fmt_id)

    def on_search(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please paste a YouTube (or other) URL.")
            return
        self.btn_search.setEnabled(False)
        self.progress_label.setText("Fetching info...")
        self.quality_combo.clear()
        self.quality_combo.addItem("Loading formats...")
        t = FetchThread(url)
        t.fetched.connect(self.on_fetched)
        t.start()
        # keep reference
        self._fetch_thread = t

    def on_fetched(self, info, error):
        self.btn_search.setEnabled(True)
        if error or not info:
            QMessageBox.critical(self, "Fetch failed", f"Could not fetch info: {error}")
            self.progress_label.setText("")
            self.quality_combo.clear()
            return

        self.current_info = info
        
        # Check if it's a playlist
        if info.get("_type") == "playlist" or (info.get("entries") and len(info.get("entries", [])) > 1):
            self.playlist_detected = True
            entries = info.get("entries", [])
            self.progress_label.setText(f"Playlist detected with {len(entries)} videos")
            
            # Auto-select playlist mode
            self.rb_playlist.setChecked(True)
            
            # Show playlist thumbnail (from first video)
            if entries and len(entries) > 0:
                thumb = entries[0].get("thumbnail")
                if thumb:
                    self.current_thumbnail_url = thumb
                    b = backend.download_thumbnail_to_bytes(thumb)
                    if b:
                        pix = QPixmap()
                        pix.loadFromData(b)
                        pix = pix.scaled(self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.thumbnail_label.setPixmap(pix)
                    else:
                        self.thumbnail_label.setText("Thumbnail\nnot available")
                else:
                    self.thumbnail_label.setText("No thumbnail")
        else:
            self.playlist_detected = False
            self.rb_single.setChecked(True)
            
            # show thumbnail for single video
            thumb = self.current_info.get("thumbnail")
            self.current_thumbnail_url = thumb
            if thumb:
                b = backend.download_thumbnail_to_bytes(thumb)
                if b:
                    pix = QPixmap()
                    pix.loadFromData(b)
                    pix = pix.scaled(self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.thumbnail_label.setPixmap(pix)
                else:
                    self.thumbnail_label.setText("Thumbnail\nnot available")
            else:
                self.thumbnail_label.setText("No thumbnail")

        # Update quality combo based on current selection
        self.update_quality_combo()

        # add to history
        hist_entry = {
            "title": self.current_info.get("title", "Unknown"),
            "url": self.current_info.get("webpage_url") or self.current_info.get("original_url") or self.url_input.text().strip()
        }
        backend.add_to_history(hist_entry)
        self.load_history()
        self.progress_label.setText("Ready")

    def on_download(self):
        if not self.current_info:
            QMessageBox.warning(self, "No target", "Search a URL and fetch info first.")
            return
        
        out_dir = self.folder_display.text().strip() or DEFAULT_DOWNLOAD_DIR
        audio_only = self.rb_audio.isChecked()
        is_playlist = self.rb_playlist.isChecked()

        # Handle playlist downloads - create subfolder
        if is_playlist:
            playlist_title = self.current_info.get("title", "Playlist")
            # Clean up title for folder name
            playlist_title = "".join(c for c in playlist_title if c.isalnum() or c in (' ', '-', '_')).strip()
            if not playlist_title:
                playlist_title = "Playlist"
            out_dir = os.path.join(out_dir, playlist_title)
            
            # Confirm with user
            entries = self.current_info.get("entries", [])
            msg = f"Download {len(entries)} videos from playlist to:\n{out_dir}"
            reply = QMessageBox.question(
                self, 
                "Confirm Playlist Download", 
                msg,
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        # Get video format
        fmt_id = None
        if not audio_only:
            data_index = self.quality_combo.currentIndex()
            if data_index >= 0:
                fmt_id = self.quality_combo.currentData()
            if not fmt_id:
                fmt_id = "best"

        # Disable download button and enable cancel
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_label.setText("Starting download...")
        
        self._dl_thread = DownloadThread(
            self.url_input.text().strip(),
            out_dir,
            video_format_id=fmt_id,
            audio_only=audio_only,
            is_playlist=is_playlist
        )
        self._dl_thread.progress.connect(self.on_dl_progress)
        self._dl_thread.finished.connect(self.on_dl_finished)
        self._dl_thread.start()

    def on_dl_progress(self, msg):
        self.progress_label.setText(msg)

    def on_dl_finished(self, success, error):
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._dl_thread = None
        
        if success:
            QMessageBox.information(self, "Done", "Download complete!")
            self.progress_label.setText("Download complete")
        else:
            if error:
                QMessageBox.critical(self, "Download error", f"Error: {error}")
                self.progress_label.setText("Error during download")
            else:
                self.progress_label.setText("Download cancelled")

    def load_history(self):
        self.history_list.clear()
        hist = backend.load_history()
        for e in hist:
            title = e.get("title", "No title")
            # Only show title, not URL
            self.history_list.addItem(title)

    def clear_history(self):
        backend.clear_history()
        self.load_history()

    def on_history_open(self, item):
        # when user double-clicks a history entry, get its URL and search
        hist = backend.load_history()
        selected_index = self.history_list.row(item)
        if 0 <= selected_index < len(hist):
            url = hist[selected_index].get("url", "")
            if url:
                self.url_input.setText(url)
                self.on_search()