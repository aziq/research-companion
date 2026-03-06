import html
import logging
import re
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot.analyzer import analyze, analyze_image
from bot.db import save_item
from bot.fetcher import fetch_url
from bot.transcriber import transcribe

logger = logging.getLogger(__name__)

_SECTION_EMOJIS = {
    "main idea": "💡",
    "why it matters": "🎯",
    "category": "🏷",
    "suggested experiment": "🧪",
    "time required to explore": "⏱",
}


def _format_for_telegram(analysis: str) -> str:
    """Convert markdown analysis text to Telegram HTML."""
    lines = analysis.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue

        # Markdown headers: # / ## / ###
        header_match = re.match(r"^#{1,3}\s+(.*)", stripped)
        if header_match:
            raw = header_match.group(1).strip()
            lookup = re.sub(r"\*\*", "", raw).rstrip(":").strip().lower()
            emoji = _SECTION_EMOJIS.get(lookup, "")
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
            content = html.escape(clean)
            prefix = f"{emoji} " if emoji else ""
            out.append(f"\n{prefix}<b>{content}</b>")
            continue

        # Section headers ending with ":" (fallback)
        if stripped.endswith(":") and len(stripped) < 60:
            lookup = stripped.rstrip(":").strip().lower()
            emoji = _SECTION_EMOJIS.get(lookup, "")
            label = html.escape(stripped)
            prefix = f"{emoji} " if emoji else ""
            out.append(f"\n{prefix}<b>{label}</b>")
            continue

        # Regular line: escape HTML, then convert markdown bold
        escaped = html.escape(stripped)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        # Markdown bullets to •
        escaped = re.sub(r"^[\-\*]\s", "• ", escaped)
        out.append(escaped)
    return "\n".join(out).strip()


async def _analyze_and_reply(
    update: Update,
    text: str,
    source_type: str = "note",
    source: str = "",
    user_note: str = "",
) -> None:
    analysis = analyze(text)
    save_item(
        source_type=source_type,
        source=source,
        content=text,
        analysis=analysis,
        user_note=user_note,
    )
    formatted = _format_for_telegram(analysis)
    await update.message.reply_text(formatted, parse_mode="HTML")


# --- Text & URLs ---

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    text = message.text or ""
    if not text:
        return

    entities = message.entities or []
    urls = [
        text[e.offset: e.offset + e.length] if e.type == "url" else e.url
        for e in entities
        if e.type in ("url", "text_link")
    ]

    if urls:
        # Extract user context (message text minus the URLs themselves)
        user_note = text
        for url_str in urls:
            user_note = user_note.replace(url_str, "")
        user_note = " ".join(user_note.split()).strip()

        for url in urls:
            await message.reply_text(f"Fetching {url} ...")
            fetched = await fetch_url(url)
            if not fetched["text"].strip():
                await message.reply_text(f"Could not extract content from {url}.")
                continue
            await message.reply_text("Analyzing...")
            await _analyze_and_reply(
                update, fetched["text"],
                source_type="url", source=url, user_note=user_note,
            )
    else:
        await message.reply_text("Analyzing...")
        await _analyze_and_reply(update, text, source_type="note")


# --- Voice messages ---

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Transcribing voice message...")
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        path = f.name
    try:
        voice_file = await update.message.voice.get_file()
        await voice_file.download_to_drive(path)
        text = await transcribe(path)
        if not text:
            await update.message.reply_text("Could not transcribe audio.")
            return
        await update.message.reply_text(f"Transcript:\n{text[:300]}{'...' if len(text) > 300 else ''}")
        await update.message.reply_text("Analyzing...")
        await _analyze_and_reply(update, text, source_type="voice_memo")
    finally:
        Path(path).unlink(missing_ok=True)


# --- Audio files ---

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    audio = update.message.audio
    suffix = f".{audio.mime_type.split('/')[-1]}" if audio.mime_type else ".mp3"
    await update.message.reply_text(f"Transcribing audio: {audio.file_name or 'file'}...")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        path = f.name
    try:
        audio_file = await audio.get_file()
        await audio_file.download_to_drive(path)
        text = await transcribe(path)
        if not text:
            await update.message.reply_text("Could not transcribe audio.")
            return
        await update.message.reply_text("Analyzing...")
        await _analyze_and_reply(
            update, text,
            source_type="audio", source=audio.file_name or "",
        )
    finally:
        Path(path).unlink(missing_ok=True)


# --- Video & video notes ---

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    video = update.message.video or update.message.video_note
    await update.message.reply_text("Extracting and transcribing video audio...")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    try:
        video_file = await video.get_file()
        await video_file.download_to_drive(path)
        text = await transcribe(path)
        if not text:
            await update.message.reply_text("No speech detected in video.")
            return
        await update.message.reply_text("Analyzing...")
        await _analyze_and_reply(update, text, source_type="video")
    finally:
        Path(path).unlink(missing_ok=True)


# --- Photos (GPT-4o-mini vision) ---

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import base64
    await update.message.reply_text("Analyzing image...")
    photo = update.message.photo[-1]  # largest available size
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        photo_file = await photo.get_file()
        await photo_file.download_to_drive(path)
        with open(path, "rb") as img:
            b64 = base64.b64encode(img.read()).decode()
        caption = update.message.caption or ""
        text = analyze_image(b64, caption)
        await update.message.reply_text("Analyzing...")
        await _analyze_and_reply(
            update, text,
            source_type="photo", user_note=caption,
        )
    finally:
        Path(path).unlink(missing_ok=True)


# --- Documents (PDF, text files, audio attachments) ---

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    mime = doc.mime_type or ""
    name = doc.file_name or "document"
    suffix = f".{name.rsplit('.', 1)[-1]}" if "." in name else ".bin"

    await update.message.reply_text(f"Processing {name}...")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        path = f.name
    try:
        doc_file = await doc.get_file()
        await doc_file.download_to_drive(path)

        if "pdf" in mime:
            import pdfplumber
            text = ""
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            text = text[:8000]
        elif mime.startswith("text/"):
            with open(path, "r", errors="ignore") as fh:
                text = fh.read(8000)
        elif mime.startswith("audio/") or suffix in (".ogg", ".mp3", ".m4a", ".wav", ".flac"):
            text = await transcribe(path)
        else:
            await update.message.reply_text(f"Unsupported document type: {mime}")
            return

        if not text.strip():
            await update.message.reply_text("Could not extract text from document.")
            return

        await update.message.reply_text("Analyzing...")
        await _analyze_and_reply(
            update, text,
            source_type="document", source=name,
            user_note=update.message.caption or "",
        )
    finally:
        Path(path).unlink(missing_ok=True)
