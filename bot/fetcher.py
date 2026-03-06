import asyncio
import logging
import re
from urllib.parse import urlparse

import httpx
import requests
import trafilatura

logger = logging.getLogger(__name__)

_YT_PATTERNS = re.compile(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})")


def _youtube_transcript(url: str) -> dict:
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

    match = _YT_PATTERNS.search(url)
    if not match:
        return _yt_dlp_extract(url)

    video_id = match.group(1)
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(t["text"] for t in transcript)
        return {"text": text[:8000], "title": f"YouTube video ({video_id})", "source_type": "youtube"}
    except (NoTranscriptFound, TranscriptsDisabled):
        logger.info(f"No transcript for {video_id}, falling back to yt-dlp description")
        return _yt_dlp_extract(url)


def _tweet_id_from_url(url: str) -> str | None:
    match = re.search(r"(?:twitter\.com|x\.com)/\S+/status(?:es)?/(\d+)", url)
    return match.group(1) if match else None


def _fxtwitter_fetch(tweet_id: str) -> dict | None:
    """Fetch tweet data from the fxtwitter community API (free, no auth)."""

    try:
        resp = requests.get(
            f"https://api.fxtwitter.com/status/{tweet_id}",
            timeout=30,
            headers={"User-Agent": "research-companion-bot/1.0"},
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("tweet")
    except Exception as e:
        logger.warning(f"fxtwitter fetch failed for {tweet_id}: {e}")
        return None


def _syndication_fetch(tweet_id: str) -> dict | None:
    """Fetch via X's own syndication API (used for embedded tweets, free, no auth)."""

    try:
        resp = requests.get(
            f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=0",
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data if data.get("text") else None
    except Exception as e:
        logger.warning(f"syndication fetch failed for {tweet_id}: {e}")
        return None


def _format_fxtwitter(tweet: dict, url: str) -> dict:
    handle = tweet.get("author", {}).get("screen_name", "")
    author = tweet.get("author", {}).get("name", "")

    # X Article (long-form "Notes")
    article = tweet.get("article")
    if article:
        title = article.get("title", "")
        body = article.get("text") or tweet.get("text", "")
        text = f"X Article by @{handle}: {title}\n\n{body}"
        return {"text": text[:8000], "title": title or f"Article by @{handle}", "source_type": "social"}

    text = f"@{handle} ({author}):\n\n{tweet.get('text', '')}"
    return {"text": text[:8000], "title": f"Post by @{handle}", "source_type": "social"}


def _format_syndication(data: dict, url: str) -> dict:
    user = data.get("user", {})
    handle = user.get("screen_name", "")
    author = user.get("name", "")
    text = f"@{handle} ({author}):\n\n{data.get('text', '')}"
    return {"text": text[:8000], "title": f"Post by @{handle}", "source_type": "social"}


def _fetch_tweet(url: str) -> dict:
    tweet_id = _tweet_id_from_url(url)

    if tweet_id:
        # 1. fxtwitter (handles X Articles too)
        tweet = _fxtwitter_fetch(tweet_id)
        if tweet:
            return _format_fxtwitter(tweet, url)

        # 2. X syndication API (X's own embed endpoint)
        data = _syndication_fetch(tweet_id)
        if data:
            return _format_syndication(data, url)

    # 3. yt-dlp as last resort
    return _yt_dlp_extract(url)


def _yt_dlp_extract(url: str) -> dict:
    import yt_dlp

    # ignore_no_formats_error: return info dict even when the tweet has no video
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("yt-dlp returned no info")
        uploader = info.get("uploader") or info.get("channel") or ""
        description = info.get("description") or ""
        text = f"Author: {uploader}\n\n{description}".strip()
        return {"text": text[:8000], "title": info.get("title") or url, "source_type": "social"}
    except Exception as e:
        logger.warning(f"yt-dlp failed for {url}: {e}")
        return {"text": "", "title": url, "source_type": "unknown"}


async def _generic_fetch(url: str) -> dict:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            html = resp.text
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        if not text:
            text = ""
        return {"text": text[:8000], "title": url, "source_type": "article"}
    except Exception as e:
        logger.warning(f"Generic fetch failed for {url}: {e}")
        return {"text": "", "title": url, "source_type": "unknown"}


async def fetch_url(url: str) -> dict:
    domain = urlparse(url).netloc.lower()

    if any(d in domain for d in ("youtube.com", "youtu.be")):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _youtube_transcript, url)

    if any(d in domain for d in ("twitter.com", "x.com", "t.co")):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _fetch_tweet, url)

    return await _generic_fetch(url)
