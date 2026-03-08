import html
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot.db import get_all_items, get_item, search_items, delete_item
from bot.formatting import format_analysis

_PROFILE_PATH = Path(__file__).parent.parent / "PROFILE.md"

logger = logging.getLogger(__name__)

_TYPE_ICONS = {
    "url": "🔗", "note": "📝", "voice_memo": "🎙", "audio": "🎵",
    "video": "🎬", "photo": "📷", "document": "📄", "unknown": "❓",
}

_LIST_LIMIT = 20


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/list — show the most recent knowledge base entries."""
    rows = get_all_items()
    if not rows:
        await update.message.reply_text("Knowledge base is empty.")
        return

    lines = [f"<b>Knowledge base</b> ({len(rows)} item(s), showing last {min(len(rows), _LIST_LIMIT)}):\n"]
    for r in rows[:_LIST_LIMIT]:
        icon = _TYPE_ICONS.get(r["source_type"], "❓")
        date = (r["created_at"] or "")[:10]
        source = html.escape((r["source"] or "—")[:60])
        lines.append(f"{icon} <code>#{r['id']}</code> <i>{date}</i>  {source}")

    lines.append("\nUse /show &lt;id&gt; to read an entry.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/show <id> — show full analysis and source for an entry."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /show &lt;id&gt;", parse_mode="HTML")
        return

    row = get_item(int(args[0]))
    if not row:
        await update.message.reply_text(f"No entry with id {args[0]}.")
        return

    icon = _TYPE_ICONS.get(row["source_type"], "❓")
    source = html.escape(row["source"] or "—")
    date = row["created_at"] or ""
    note = html.escape(row["user_note"]) if row["user_note"] else None

    header = f"{icon} <b>#{row['id']}</b>  <i>{date}</i>\n<code>{source}</code>"
    if note:
        header += f"\n<i>Note: {note}</i>"

    analysis = format_analysis(row["analysis"]) if row["analysis"] else "(no analysis)"

    msg = f"{header}\n\n{analysis}"

    # Telegram max message length is 4096 chars
    if len(msg) > 4000:
        await update.message.reply_text(msg[:4000] + "\n…(truncated)", parse_mode="HTML")
    else:
        await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/search <query> — search source, content, and analysis."""
    if not context.args:
        await update.message.reply_text("Usage: /search &lt;query&gt;", parse_mode="HTML")
        return

    query = " ".join(context.args)
    rows = search_items(query)

    if not rows:
        await update.message.reply_text(f"No results for <i>{html.escape(query)}</i>.", parse_mode="HTML")
        return

    lines = [f"<b>{len(rows)} result(s)</b> for <i>{html.escape(query)}</i>:\n"]
    for r in rows[:_LIST_LIMIT]:
        icon = _TYPE_ICONS.get(r["source_type"], "❓")
        date = (r["created_at"] or "")[:10]
        source = html.escape((r["source"] or "—")[:50])

        # Find the first field with a match and show a snippet
        snippet = ""
        for field in ("source", "content", "analysis", "user_note"):
            text = r[field] or ""
            idx = text.lower().find(query.lower())
            if idx >= 0:
                start = max(0, idx - 40)
                raw = text[start: idx + 80].replace("\n", " ")
                snippet = f"\n    <i>…{html.escape(raw)}…</i>"
                break

        lines.append(f"{icon} <code>#{r['id']}</code> <i>{date}</i>  {source}{snippet}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/profile [text] — show or update your personal profile."""
    message = update.effective_message
    if not message:
        return

    if context.args:
        text = " ".join(context.args)
        _PROFILE_PATH.write_text(text, encoding="utf-8")
        await message.reply_text("Profile updated.")
        return

    if not _PROFILE_PATH.exists():
        await message.reply_text(
            "No profile set yet. Use /profile <text> to set one, "
            "or edit PROFILE.md directly for multi-line content."
        )
        return

    content = _PROFILE_PATH.read_text(encoding="utf-8").strip()
    if not content:
        await message.reply_text("Profile file exists but is empty.")
        return

    await message.reply_text(f"<b>Your profile:</b>\n\n{html.escape(content)}", parse_mode="HTML")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/delete <id> — remove an entry from the knowledge base."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /delete &lt;id&gt;", parse_mode="HTML")
        return

    item_id = int(args[0])
    row = get_item(item_id)
    if not row:
        await update.message.reply_text(f"No entry with id {item_id}.")
        return

    delete_item(item_id)
    icon = _TYPE_ICONS.get(row["source_type"], "❓")
    source = html.escape(row["source"] or "—")
    await update.message.reply_text(
        f"Deleted {icon} <code>#{item_id}</code>  <i>{source}</i>", parse_mode="HTML"
    )
