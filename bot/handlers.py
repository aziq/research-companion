from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any incoming text message."""
    message = update.message
    if not message or not message.text:
        return

    user = message.from_user
    text = message.text
    chat_id = message.chat_id

    logger.info(f"Message from {user.username or user.id} (chat {chat_id}): {text}")

    # Echo back for now — replace with actual logic
    await message.reply_text(f"Received: {text}")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages containing URLs (entities of type 'url' or 'text_link')."""
    message = update.message
    if not message:
        return

    entities = message.entities or []
    urls = []

    for entity in entities:
        if entity.type == "url":
            url = message.text[entity.offset : entity.offset + entity.length]
            urls.append(url)
        elif entity.type == "text_link":
            urls.append(entity.url)

    if not urls:
        return

    logger.info(f"URLs received: {urls}")
    await message.reply_text(f"Got {len(urls)} link(s) — will process them shortly.")
