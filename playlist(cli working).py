#!/usr/bin/env python3
"""
Simple CLI playlist downloader using yt-dlp with anti-bot measures
"""
import os
import yt_dlp
from pathlib import Path


def download_playlist_video(url, output_folder="downloads"):
    """
    Download entire playlist as video files
    """
    # Create output folder
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Output template with playlist index
    outtmpl = os.path.join(output_folder, "%(playlist_index)s - %(title)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'outtmpl': outtmpl,
        'noplaylist': False,  # Allow playlist
        'ignoreerrors': True,  # Skip unavailable videos
        'merge_output_format': 'mp4',  # Merge to mp4
        'continuedl': True,
        'retries': 10,
        'fragment_retries': 10,
        # Anti-bot measures - use Android client
        'extractor_args': {
            'youtube': {
                'player_client': ['android_creator'],
                'player_skip': ['webpage'],
            }
        },
    }
    
    print(f"Downloading playlist to: {output_folder}")
    print("=" * 50)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.download([url])
    
    print("\n" + "=" * 50)
    print("Download complete!")
    return result


def download_playlist_audio(url, output_folder="downloads"):
    """
    Download entire playlist as MP3 audio files
    """
    # Create output folder
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Output template with playlist index
    outtmpl = os.path.join(output_folder, "%(playlist_index)s - %(title)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'noplaylist': False,  # Allow playlist
        'ignoreerrors': True,  # Skip unavailable videos
        'continuedl': True,
        'retries': 10,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # Anti-bot measures - use Android client
        'extractor_args': {
            'youtube': {
                'player_client': ['android_creator'],
                'player_skip': ['webpage'],
            }
        },
    }
    
    print(f"Downloading playlist (audio only) to: {output_folder}")
    print("=" * 50)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.download([url])
    
    print("\n" + "=" * 50)
    print("Download complete!")
    return result


def get_playlist_info(url):
    """
    Get playlist information without downloading
    """
    ydl_opts = {
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'quiet': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android_creator'],
            }
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


if __name__ == "__main__":
    print("YouTube Playlist Downloader")
    print("=" * 50)
    print("\nNOTE: Using Android client to bypass bot detection")
    print("If downloads fail, try: pip install -U yt-dlp\n")
    
    # Get URL from user
    url = input("Enter playlist URL: ").strip()
    
    if not url:
        print("Error: No URL provided")
        exit(1)
    
    # Check if it's a playlist
    try:
        print("\nFetching playlist info...")
        info = get_playlist_info(url)
        
        if info.get('_type') == 'playlist':
            entries = info.get('entries', [])
            title = info.get('title', 'Unknown Playlist')
            print(f"\nPlaylist: {title}")
            print(f"Total videos: {len(entries)}")
        else:
            print("\nThis appears to be a single video, not a playlist.")
            print("Downloading anyway...")
    except Exception as e:
        print(f"Warning: Could not fetch info - {e}")
        print("Continuing with download anyway...")
    
    # Ask for download type
    print("\nDownload as:")
    print("1. Video (MP4 - max 1080p)")
    print("2. Audio (MP3)")
    choice = input("Enter choice (1 or 2): ").strip()
    
    # Get output folder
    output = input("\nEnter output folder (press Enter for 'downloads'): ").strip()
    if not output:
        output = "downloads"
    
    # Download
    print()
    try:
        if choice == "2":
            download_playlist_audio(url, output)
        else:
            download_playlist_video(url, output)
            
        print("\n✓ All done! Check your output folder.")
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        exit(0)
    except Exception as e:
        print(f"\nError during download: {e}")
        print("\nTroubleshooting:")
        print("1. Update yt-dlp: pip install -U yt-dlp")
        print("2. Check your internet connection")
        print("3. Try a different playlist")
        exit(1)