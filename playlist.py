# playlist.py
import os
from pathlib import Path
from typing import Optional
import yt_dlp


def download_playlist_video(
    url: str,
    out_dir: str,
    video_format_id: Optional[str] = None,
    progress_hook=None,
):
    """
    Download entire playlist as video files.
    Creates a subfolder with playlist name.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    outtmpl = os.path.join(out_dir, "%(playlist_index)s - %(title)s.%(ext)s")

    # Determine format based on video_format_id
    if video_format_id and video_format_id != "best":
        # User selected specific quality
        format_string = f"{video_format_id}+bestaudio/best"
    else:
        # Default to best quality up to 1080p
        format_string = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"

    ydl_opts = {
        'format': format_string,
        'outtmpl': outtmpl,
        'noplaylist': False,  # Allow playlist download
        'ignoreerrors': True,  # Skip unavailable videos
        'merge_output_format': 'mp4',
        'continuedl': True,
        'retries': 10,
        'fragment_retries': 10,
        'quiet': True,
        'no_warnings': True,
        # Use multiple client fallbacks
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web'],
                'player_skip': ['configs'],
            }
        },
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.download([url])
    return result


def download_playlist_audio(
    url: str,
    out_dir: str,
    progress_hook=None,
):
    """
    Download entire playlist as audio files (MP3).
    Creates a subfolder with playlist name.
    Requires ffmpeg.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    outtmpl = os.path.join(out_dir, "%(playlist_index)s - %(title)s.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'noplaylist': False,  # Allow playlist download
        'ignoreerrors': True,  # Skip unavailable videos
        'continuedl': True,
        'retries': 10,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # Use multiple client fallbacks
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web'],
                'player_skip': ['configs'],
            }
        },
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.download([url])
    return result


def get_playlist_info(url: str) -> dict:
    """
    Fetch playlist information without downloading.
    Returns dict with playlist metadata.
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',  # Get playlist structure
        'extractor_args': {
            'youtube': {
                'player_client': ['android_creator', 'ios', 'web'],
            }
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    
    return info