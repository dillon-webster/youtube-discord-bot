#!/usr/bin/env python3

import subprocess
import sys
import json
import random
import webbrowser


def ensure_yt_dlp():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print("Installing yt-dlp...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])


def get_channel_videos(channel_input: str) -> list[dict]:
    import yt_dlp

    # Normalize input to a channel URL
    if channel_input.startswith("http"):
        url = channel_input
    else:
        # Try as a handle (@name) or plain name
        handle = channel_input if channel_input.startswith("@") else f"@{channel_input}"
        url = f"https://www.youtube.com/{handle}/videos"

    print(f"Fetching videos from: {url}")

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlist_items": "1-200",  # cap at 200 to keep it fast
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries", [])
    if not entries:
        raise ValueError("No videos found. Check the channel name and try again.")

    return entries


def pick_random_video(entries: list[dict]) -> dict:
    return random.choice(entries)


def main():
    if len(sys.argv) > 1:
        channel = " ".join(sys.argv[1:])
    else:
        channel = input("Enter YouTube channel name or URL: ").strip()

    if not channel:
        print("No channel provided.")
        sys.exit(1)

    ensure_yt_dlp()

    try:
        videos = get_channel_videos(channel)
    except Exception as e:
        print(f"Error fetching channel: {e}")
        sys.exit(1)

    video = pick_random_video(videos)
    video_id = video.get("id") or video.get("url", "")
    title = video.get("title", "Unknown title")

    video_url = f"https://www.youtube.com/watch?v={video_id}" if not video_id.startswith("http") else video_id

    print(f"\nOpening random video ({len(videos)} total):")
    print(f"  Title: {title}")
    print(f"  URL:   {video_url}\n")

    webbrowser.open(video_url)


if __name__ == "__main__":
    main()
