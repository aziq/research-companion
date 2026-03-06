from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.commands import cmd_delete, cmd_list, cmd_search, cmd_show
from bot.handlers import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_text,
    handle_video,
    handle_voice,
)


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    # KB commands
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("show", cmd_show))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("delete", cmd_delete))

    # Content ingestion
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    return app
