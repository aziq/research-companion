"""
Webhook-based Telegram bot server.

Local dev:
    1. Install deps: pip install -r requirements.txt
    2. Expose local port: ngrok http 8000
    3. Set WEBHOOK_URL=https://<ngrok-id>.ngrok.io in .env
    4. Run: uvicorn main:app --reload

Production (Cloud Run / any HTTPS host):
    Set WEBHOOK_URL to your public HTTPS URL and deploy.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update

from bot.application import build_application

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-domain.com

app = FastAPI()
telegram_app = build_application(TOKEN)


@app.on_event("startup")
async def startup() -> None:
    await telegram_app.initialize()
    if WEBHOOK_URL:
        webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
        await telegram_app.bot.set_webhook(webhook_endpoint)
        logger.info(f"Webhook set to {webhook_endpoint}")
    else:
        logger.warning("WEBHOOK_URL not set — webhook not registered with Telegram")
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
