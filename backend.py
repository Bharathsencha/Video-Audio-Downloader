# backend.py
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yt_dlp
import requests

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "py_ytdlp_gui"
HISTORY_FILE = CONFIG_DIR / "history.json"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def _save_history_list(history: List[Dict]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def load_history() -> List[Dict]:
    if HISTORY_FILE.exists():
        try:
            return json.load(open(HISTORY_FILE, "r", encoding="utf-8"))
        except Exception:
            return []
    return []

def add_to_history(entry: Dict):
    hist = load_history()
    hist.insert(0, entry)  # newest first
    # keep only last 100
    hist = hist[:100]
    _save_history_list(hist)

def clear_history():
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()

def fetch_info(url: str) -> Dict:
    """
    Uses yt_dlp to extract info (no download).
    returns the info dict.
    """
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,  # get full metadata
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info

def get_best_audio_format(info: Dict) -> str:
    # Not strictly needed if we use postprocessor 'bestaudio'
    return "bestaudio"

def estimate_file_size(height: int, duration: int, ext: str) -> str:
    """
    Estimate file size based on resolution, duration and format.
    Returns human readable size like "Est. 1.2GB"
    """
    if not duration or duration <= 0:
        return ""
    
    # Rough bitrate estimates (kbps) for different qualities
    bitrate_map = {
        2160: 25000,  # 4K
        1440: 16000,  # 1440p
        1080: 8000,   # 1080p
        720: 5000,    # 720p
        480: 2500,    # 480p
        360: 1000,    # 360p
        240: 500,     # 240p
        144: 300,     # 144p
    }
    
    # Get closest bitrate
    bitrate = bitrate_map.get(height, 2000)  # default 2mbps
    
    # WebM is usually more efficient than MP4
    if ext.lower() == "webm":
        bitrate = int(bitrate * 0.8)
    
    # Calculate size in MB
    size_mb = (bitrate * duration) / (8 * 1000)  # Convert kbps*seconds to MB
    
    if size_mb < 1024:
        return f"Est. {size_mb:.0f}MB"
    else:
        size_gb = size_mb / 1024
        return f"Est. {size_gb:.1f}GB"

def parse_video_formats(info: Dict) -> List[Tuple[str, str]]:
    """
    Returns list of (format_id, label) with highest quality first, 144p last.
    Label example: "1080p MP4 Est. 1.2GB"
    """
    formats = info.get("formats") or []
    parsed = []
    seen = set()
    duration = info.get("duration", 0)
    
    # Filter and organize formats
    video_formats = []
    for f in formats:
        # Skip audio-only formats
        if f.get("acodec") == "none" and f.get("vcodec", "") == "none":
            continue
        if f.get("vcodec") == "none":  # audio only
            continue
            
        fmt_id = f.get("format_id")
        if not fmt_id or fmt_id in seen:
            continue
        seen.add(fmt_id)
        
        height = f.get("height") or 0
        ext = (f.get("ext") or "").upper()
        
        # Skip formats without height info
        if height == 0:
            continue
            
        video_formats.append((fmt_id, height, ext))
    
    # Sort by height (highest first), but put 144p at the end
    def sort_key(item):
        _, height, ext = item
        if height <= 144:
            return (0, height)  # Low priority for 144p and below
        return (1, height)
    
    video_formats.sort(key=sort_key, reverse=True)
    
    # Create clean labels with size estimates
    for fmt_id, height, ext in video_formats:
        size_est = estimate_file_size(height, duration, ext)
        if size_est:
            label = f"{height}p {ext} {size_est}"
        else:
            label = f"{height}p {ext}"
        parsed.append((fmt_id, label))
    
    # Add fallback if no formats found
    if not parsed:
        parsed = [("best", "Best Quality")]
    
    return parsed

def download_video(
    url: str,
    out_dir: str,
    video_format_id: Optional[str] = None,
    audio_only: bool = False,
    playlist_items: Optional[str] = None,
    progress_hook=None,
):
    """
    Download logic using yt_dlp.
    - out_dir: folder path
    - video_format_id: format id (for video); if None use 'best'
    - audio_only: if True, extract audio to MP3 (requires ffmpeg)
    - playlist_items: a string like "1-3" or "5" to pick playlist items (yt-dlp option)
    progress_hook: optional callable(d) for progress updates
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    outtmpl = os.path.join(out_dir, "%(title)s - %(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": False if playlist_items else True,
        "quiet": True,
        "no_warnings": True,
    }
    if playlist_items:
        ydl_opts["playlist_items"] = playlist_items  # e.g. "1-5" or "3"
    if audio_only:
        # download best audio and convert to mp3 via ffmpeg
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        })
    else:
        if video_format_id:
            ydl_opts["format"] = f"{video_format_id}+bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.download([url])
    return result

def download_thumbnail_to_bytes(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.content
    except Exception:
        return None