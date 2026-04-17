#!/usr/bin/env python3
"""
YouTube Random Video Discord Bot

Commands:
  !subs          - List all your subscribed channels with numbers
  !random        - Pick a random channel and open a random video
  !random <num>  - Pick a random video from a specific channel (use number from !subs)
"""

import os
import random
import sys
from pathlib import Path

import discord

SCRIPT_DIR = Path(__file__).parent
TOKEN = os.environ.get("DISCORD_TOKEN", "")
if not TOKEN:
    print("ERROR: Set the DISCORD_TOKEN environment variable.")
    print("  export DISCORD_TOKEN=your_token_here")
    sys.exit(1)

sys.path.insert(0, str(SCRIPT_DIR))
from random_subscribed_video import (
    get_credentials,
    get_subscriptions,
    get_uploads_playlist_id,
    get_videos_from_playlist,
)

import googleapiclient.discovery

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

youtube = None
channels_cache = []


def build_youtube():
    global youtube
    creds = get_credentials()
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def load_channels():
    global channels_cache
    if not channels_cache:
        channels_cache = get_subscriptions(youtube)
        channels_cache.sort(key=lambda c: c["title"].lower())
    return channels_cache


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    print("Bot is ready. Use !subs or !random in Discord.")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    content = message.content.strip()

    if content == "!subs":
        channels = load_channels()
        lines = [f"`{i+1:3}.` {ch['title']}" for i, ch in enumerate(channels)]
        # Discord has a 2000 char limit per message, chunk if needed
        chunk, chunks = [], []
        for line in lines:
            if sum(len(l) + 1 for l in chunk) + len(line) > 1900:
                chunks.append("\n".join(chunk))
                chunk = []
            chunk.append(line)
        if chunk:
            chunks.append("\n".join(chunk))

        await message.channel.send(f"**Your subscriptions ({len(channels)} total):**")
        for chunk in chunks:
            await message.channel.send(chunk)
        await message.channel.send("Use `!random <number>` to pick a channel, or `!random` for a random one.")

    elif content.startswith("!random"):
        channels = load_channels()
        parts = content.split()

        if len(parts) == 1:
            channel = random.choice(channels)
        elif len(parts) == 2 and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if not (0 <= idx < len(channels)):
                await message.channel.send(f"Please enter a number between 1 and {len(channels)}.")
                return
            channel = channels[idx]
        else:
            await message.channel.send("Usage: `!random` or `!random <number>`")
            return

        await message.channel.send(f"Fetching videos from **{channel['title']}**...")

        playlist_id = get_uploads_playlist_id(youtube, channel["channel_id"])
        if not playlist_id:
            await message.channel.send("Could not find videos for that channel.")
            return

        videos = get_videos_from_playlist(youtube, playlist_id, max_videos=50)
        if not videos:
            await message.channel.send("No videos found for that channel.")
            return

        video = random.choice(videos)
        await message.channel.send(
            f"**{channel['title']}** — {video['title']}\n{video['url']}"
        )


if __name__ == "__main__":
    print("Authenticating with YouTube...")
    build_youtube()
    print("Starting Discord bot...")
    client.run(TOKEN)
