#!/usr/bin/env python3
"""
Watch a random video from your YouTube subscriptions.

First-time setup:
  1. Go to https://console.cloud.google.com/
  2. Create a new project (or use existing)
  3. Enable "YouTube Data API v3" (APIs & Services > Enable APIs)
  4. Go to APIs & Services > Credentials > Create Credentials > OAuth client ID
  5. Application type: Desktop app
  6. Download the JSON and save it as "client_secrets.json" next to this script
  7. Go to APIs & Services > OAuth consent screen, add your Google account as a Test User
  8. Run this script — it will open a browser to authorize, then save a token for future runs
"""

import json
import os
import random
import sys
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SECRETS_FILE = SCRIPT_DIR / "client_secrets.json"
TOKEN_FILE = SCRIPT_DIR / ".youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


def get_credentials():
    import json

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    # Try env var first (used on Railway), then fall back to local file
    token_json = os.environ.get("YOUTUBE_TOKEN")
    if token_json:
        creds = Credentials.from_authorized_user_info(
            json.loads(token_json), SCOPES)
    elif TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRETS_FILE.exists():
                print("ERROR: client_secrets.json not found.")
                print()
                print("Setup instructions:")
                print("  1. Go to https://console.cloud.google.com/")
                print("  2. Create a project and enable 'YouTube Data API v3'")
                print("  3. Create OAuth credentials (Desktop app type)")
                print("  4. Download the JSON and save as:", SECRETS_FILE)
                print(
                    "  5. Add your Google account as a Test User in OAuth consent screen"
                )
                print("  6. Re-run this script")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(SECRETS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        if not token_json:
            TOKEN_FILE.write_text(creds.to_json())

    return creds


def get_subscriptions(youtube) -> list[dict]:
    print("Fetching your subscriptions...")
    channels = []
    next_page = None

    while True:
        params = {
            "part": "snippet",
            "mine": True,
            "maxResults": 50,
            "order": "alphabetical",
        }
        if next_page:
            params["pageToken"] = next_page

        resp = youtube.subscriptions().list(**params).execute()
        for item in resp.get("items", []):
            snippet = item["snippet"]
            channels.append(
                {
                    "title": snippet["title"],
                    "channel_id": snippet["resourceId"]["channelId"],
                }
            )

        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    return channels


def get_uploads_playlist_id(youtube, channel_id: str) -> str | None:
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items", [])
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_videos_from_playlist(
    youtube, playlist_id: str, max_videos: int = 100
) -> list[dict]:
    videos = []
    next_page = None

    while len(videos) < max_videos:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(50, max_videos - len(videos)),
        }
        if next_page:
            params["pageToken"] = next_page

        resp = youtube.playlistItems().list(**params).execute()
        for item in resp.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            videos.append(
                {
                    "title": snippet["title"],
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                }
            )

        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    return videos


def main():
    try:
        import googleapiclient.discovery
    except ImportError:
        print("Installing dependencies...")
        import subprocess

        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "google-auth-oauthlib",
                "google-api-python-client",
                "-q",
            ]
        )
        import googleapiclient.discovery

    creds = get_credentials()

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds)

    channels = get_subscriptions(youtube)
    if not channels:
        print("No subscriptions found.")
        sys.exit(1)

    print(f"\nFound {len(channels)} subscribed channels:\n")
    for i, ch in enumerate(channels, 1):
        print(f"  {i:3}. {ch['title']}")

    print()
    while True:
        raw = input(
            "Enter channel number (or press Enter for random): ").strip()
        if raw == "":
            channel = random.choice(channels)
            print(f"Randomly selected: {channel['title']}")
            break
        if raw.isdigit() and 1 <= int(raw) <= len(channels):
            channel = channels[int(raw) - 1]
            break
        print(f"  Please enter a number between 1 and {len(channels)}")

    # Get uploads playlist
    playlist_id = get_uploads_playlist_id(youtube, channel["channel_id"])
    if not playlist_id:
        print("Could not find uploads for this channel. Try again.")
        sys.exit(1)

    # Get videos
    print("Fetching recent videos...")
    videos = get_videos_from_playlist(youtube, playlist_id, max_videos=50)
    if not videos:
        print("No videos found for this channel.")
        sys.exit(1)

    # Pick a random video
    video = random.choice(videos)

    print(f"\nOpening random video from '{
          channel['title']}' ({len(videos)} fetched):")
    print(f"  Title: {video['title']}")
    print(f"  URL:   {video['url']}\n")

    webbrowser.open(video["url"])


if __name__ == "__main__":
    main()
