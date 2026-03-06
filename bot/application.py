from telegram.ext import Application, MessageHandler, filters

from bot.handlers import (
    handle_text,
    handle_voice,
    handle_audio,
    handle_video,
    handle_photo,
    handle_document,
)


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    return app
