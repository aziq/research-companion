from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from bot.handlers import handle_message, handle_url


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    # URL messages get routed to the URL handler first
    app.add_handler(MessageHandler(filters.Entity("url") | filters.Entity("text_link"), handle_url))

    # Everything else
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
