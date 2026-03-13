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
    from youtube_transcript_api import YouTubeTranscriptApi

    match = _YT_PATTERNS.search(url)
    if not match:
        return _yt_dlp_extract(url)

    video_id = match.group(1)
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        text = " ".join(snippet.text for snippet in fetched)
        return {"text": text[:8000], "title": f"YouTube video ({video_id})", "source_type": "youtube"}
    except Exception:
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

    image_urls = [
        p["url"] for p in (tweet.get("media") or {}).get("photos", []) if p.get("url")
    ]

    # X Article (long-form "Notes")
    article = tweet.get("article")
    if article:
        title = article.get("title", "")
        body = article.get("text") or tweet.get("text", "")
        text = f"X Article by @{handle}: {title}\n\n{body}"
        return {"text": text[:8000], "title": title or f"Article by @{handle}", "source_type": "social", "image_urls": image_urls}

    text = f"@{handle} ({author}):\n\n{tweet.get('text', '')}"
    return {"text": text[:8000], "title": f"Post by @{handle}", "source_type": "social", "image_urls": image_urls}


def _format_syndication(data: dict, url: str) -> dict:
    user = data.get("user", {})
    handle = user.get("screen_name", "")
    author = user.get("name", "")
    image_urls = [
        m["media_url_https"] for m in (data.get("mediaDetails") or [])
        if m.get("type") == "photo" and m.get("media_url_https")
    ]
    text = f"@{handle} ({author}):\n\n{data.get('text', '')}"
    return {"text": text[:8000], "title": f"Post by @{handle}", "source_type": "social", "image_urls": image_urls}


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
    import tempfile, os

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt",
    }
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts["paths"] = {"home": tmpdir}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            if not info:
                raise ValueError("yt-dlp returned no info")

            # Try to read a downloaded subtitle file
            subtitle_text = ""
            for fname in os.listdir(tmpdir):
                if fname.endswith(".vtt"):
                    with open(os.path.join(tmpdir, fname), encoding="utf-8", errors="ignore") as f:
                        raw = f.read()
                    # Strip VTT header/timestamps, keep only text lines
                    lines = []
                    for line in raw.splitlines():
                        line = line.strip()
                        if not line or line.startswith("WEBVTT") or "-->" in line or line.isdigit():
                            continue
                        lines.append(line)
                    subtitle_text = " ".join(lines)
                    break

        uploader = info.get("uploader") or info.get("channel") or ""
        title = info.get("title") or url
        description = info.get("description") or ""

        if subtitle_text:
            text = f"{title}\nBy: {uploader}\n\nTranscript:\n{subtitle_text}"
        else:
            text = f"{title}\nBy: {uploader}\n\n{description}".strip()

        source_type = "youtube" if "vimeo" not in url and "youtube" in url else "video"
        return {"text": text[:8000], "title": title, "source_type": source_type}
    except Exception as e:
        logger.warning(f"yt-dlp failed for {url}: {e}")
        return {"text": "", "title": url, "source_type": "unknown"}


async def _generic_fetch(url: str) -> dict:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            )
            html = resp.text
    except Exception as e:
        logger.warning(f"Generic fetch failed for {url}: {e}")
        return {"text": "", "title": url, "source_type": "unknown"}

    logger.debug(f"Fetched {url} — status={resp.status_code} len={len(html)}")

    # 1. trafilatura strict
    text = trafilatura.extract(html, include_comments=False, include_tables=False)

    # 2. trafilatura with recall mode (less strict)
    if not text:
        text = trafilatura.extract(html, include_comments=False, include_tables=True, favor_recall=True)
        if text:
            logger.debug(f"trafilatura favor_recall extracted {len(text)} chars from {url}")

    if not text:
        logger.debug(f"trafilatura failed for {url}, trying BeautifulSoup")

    # 3. BeautifulSoup fallback — extract visible text from article/main/body
    if not text:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            container = soup.find("article") or soup.find("main") or soup.find("body")
            if container:
                text = container.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.warning(f"BeautifulSoup fallback failed for {url}: {e}")

    title = url
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
    except Exception:
        pass

    return {"text": (text or "")[:8000], "title": title, "source_type": "article"}


def _domain_matches(domain: str, *targets: str) -> bool:
    """Check if domain equals or is a subdomain of any target."""
    return any(domain == t or domain.endswith(f".{t}") for t in targets)


async def fetch_url(url: str) -> dict:
    domain = urlparse(url).netloc.lower()

    if _domain_matches(domain, "youtube.com", "youtu.be"):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _youtube_transcript, url)

    if _domain_matches(domain, "vimeo.com"):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _yt_dlp_extract, url)

    if _domain_matches(domain, "twitter.com", "x.com", "t.co"):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _fetch_tweet, url)

    return await _generic_fetch(url)
