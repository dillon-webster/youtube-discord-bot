#!/usr/bin/env python3
"""
YouTube Random Video Discord Bot

Commands (work in server channels or DMs):
  !auth          - Connect your YouTube account
  !subs          - List your subscribed channels (sent via DM)
  !random        - Pick a random video from a random channel (sent via DM)
  !random <num>  - Pick a random video from a specific channel (use number from !subs)
"""

import json
import os
import random
import sys

import discord
import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from random_subscribed_video import (
    get_subscriptions,
    get_uploads_playlist_id,
    get_videos_from_playlist,
)
from token_store import get_token, save_token
from web_auth import run_in_background

TOKEN = os.environ.get("DISCORD_TOKEN", "")
if not TOKEN:
    print("ERROR: Set the DISCORD_TOKEN environment variable.")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def get_web_url() -> str:
    base = os.environ.get("WEB_URL") or f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:8080')}"
    return base.rstrip("/")


def build_youtube_for_user(discord_id: str):
    token_data = get_token(str(discord_id))
    if not token_data:
        return None

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(str(discord_id), json.loads(creds.to_json()))
        else:
            return None

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def auth_url_for(discord_id) -> str:
    return f"{get_web_url()}/auth?discord_id={discord_id}"


async def prompt_auth(user: discord.User, channel):
    url = auth_url_for(user.id)
    try:
        await user.send(
            f"Connect your YouTube account to use this bot:\n{url}\n\nAfter connecting, come back and try again!"
        )
        if not isinstance(channel, discord.DMChannel):
            await channel.send(f"{user.mention} Check your DMs to connect your YouTube account!", delete_after=10)
    except discord.Forbidden:
        await channel.send(f"{user.mention} Connect your YouTube account: {url}", delete_after=30)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    print(f"Web auth URL: {get_web_url()}/auth")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    content = message.content.strip()
    in_dm = isinstance(message.channel, discord.DMChannel)

    if content != "!subs" and content != "!auth" and not content.startswith("!random"):
        return

    if not in_dm:
        try:
            await message.delete()
        except discord.Forbidden:
            pass

    if content == "!auth":
        url = auth_url_for(message.author.id)
        try:
            await message.author.send(f"Connect your YouTube account:\n{url}")
        except discord.Forbidden:
            await message.channel.send(f"{message.author.mention} {url}", delete_after=30)
        return

    youtube = build_youtube_for_user(message.author.id)
    if not youtube:
        await prompt_auth(message.author, message.channel)
        return

    if content == "!subs":
        await message.author.send("Fetching your subscriptions...")
        channels = get_subscriptions(youtube)
        if not channels:
            await message.author.send("No subscriptions found. Make sure you signed in with the right Google account.")
            return
        channels.sort(key=lambda c: c["title"].lower())

        lines = [f"`{i + 1:3}.` {ch['title']}" for i, ch in enumerate(channels)]
        chunk, chunks = [], []
        for line in lines:
            if sum(len(l) + 1 for l in chunk) + len(line) > 1900:
                chunks.append("\n".join(chunk))
                chunk = []
            chunk.append(line)
        if chunk:
            chunks.append("\n".join(chunk))

        await message.author.send(f"**Your subscriptions ({len(channels)} total):**")
        for chunk in chunks:
            await message.author.send(chunk)
        await message.author.send("Use `!random <number>` to pick a channel, or `!random` for a random one.")

    elif content.startswith("!random"):
        parts = content.split()

        channels = get_subscriptions(youtube)
        channels.sort(key=lambda c: c["title"].lower())

        if not channels:
            await message.author.send("No subscriptions found. Make sure you signed in with the right Google account.")
            return

        if len(parts) == 1:
            channel = random.choice(channels)
        elif len(parts) == 2 and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if not (0 <= idx < len(channels)):
                await message.author.send(f"Please enter a number between 1 and {len(channels)}.")
                return
            channel = channels[idx]
        else:
            await message.author.send("Usage: `!random` or `!random <number>`")
            return

        await message.author.send(f"Fetching videos from **{channel['title']}**...")

        playlist_id = get_uploads_playlist_id(youtube, channel["channel_id"])
        if not playlist_id:
            await message.author.send("Could not find videos for that channel.")
            return

        videos = get_videos_from_playlist(youtube, playlist_id, max_videos=50)
        if not videos:
            await message.author.send("No videos found for that channel.")
            return

        video = random.choice(videos)
        await message.author.send(f"**{channel['title']}** — {video['title']}\n{video['url']}")


if __name__ == "__main__":
    run_in_background()
    print("Starting Discord bot...")
    client.run(TOKEN)
