import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from bot.analyzer import analyze, analyze_image
from bot.db import save_item
from bot.fetcher import fetch_url
from bot.transcriber import transcribe

logger = logging.getLogger(__name__)


async def _analyze_and_reply(update: Update, text: str, source: str = "") -> None:
    analysis = analyze(text)
    save_item(source or text[:200], analysis)
    await update.message.reply_text(analysis)


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
        for url in urls:
            await message.reply_text(f"Fetching {url} ...")
            fetched = await fetch_url(url)
            if not fetched["text"].strip():
                await message.reply_text(f"Could not extract content from {url}.")
                continue
            await message.reply_text("Analyzing...")
            await _analyze_and_reply(update, fetched["text"], source=url)
    else:
        await message.reply_text("Analyzing...")
        await _analyze_and_reply(update, text, source="note")


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
        await _analyze_and_reply(update, text, source="voice_memo")
    finally:
        os.unlink(path)


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
        await _analyze_and_reply(update, text, source=audio.file_name or "audio")
    finally:
        os.unlink(path)


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
        await _analyze_and_reply(update, text, source="video")
    finally:
        os.unlink(path)


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
        await _analyze_and_reply(update, text, source="photo")
    finally:
        os.unlink(path)


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
        await _analyze_and_reply(update, text, source=name)
    finally:
        os.unlink(path)
