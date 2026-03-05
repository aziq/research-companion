"""
Telegram bot server — dual-mode: polling (local dev) or webhook (production).

Local dev (no tunnel needed):
    pip install -r requirements.txt
    python main.py

Production (Cloud Run / any HTTPS host):
    Set WEBHOOK_URL=https://your-domain.com in .env and run via uvicorn:
    uvicorn main:app --host 0.0.0.0 --port 8080
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update

from bot.application import build_application

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_URL = os.getenv("WEBHOOK_URL")


def run_polling() -> None:
    """Run in long-polling mode — no public URL required."""
    logger.info("Starting in polling mode")
    telegram_app = build_application(TOKEN)
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)


def build_webhook_app():
    """Build the FastAPI app for webhook mode (production)."""
    from fastapi import FastAPI, Request, Response

    app = FastAPI()
    telegram_app = build_application(TOKEN)

    @app.on_event("startup")
    async def startup() -> None:
        await telegram_app.initialize()
        webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
        await telegram_app.bot.set_webhook(webhook_endpoint)
        logger.info(f"Webhook set to {webhook_endpoint}")
        await telegram_app.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await telegram_app.stop()
        await telegram_app.shutdown()

    @app.post("/webhook")
    async def webhook(request: Request) -> Response:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return Response(status_code=200)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


if WEBHOOK_URL:
    # Production: expose ASGI app for uvicorn
    app = build_webhook_app()
else:
    # Local dev: run polling when executed directly
    if __name__ == "__main__":
        run_polling()
