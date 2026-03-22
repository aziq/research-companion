import base64
import io
import logging
import tempfile
from pathlib import Path

import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse as FastAPIFileResponse

from bot.analyzer import analyze, analyze_image
from bot.auth import require_token
from bot.config import MAX_CONTENT_CHARS
from bot.db import (
    delete_item,
    get_all_items,
    get_item,
    get_profile,
    save_item,
    search_items,
    set_profile,
)
from bot.fetcher import fetch_url
from bot.storage import full_path, save_file
from bot.transcriber import transcribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

@router.get("/items")
async def list_items(q: str | None = None, user_id: str = Depends(require_token)):
    rows = search_items(q, user_id) if q else get_all_items(user_id)
    return [dict(r) for r in rows]


@router.get("/items/{item_id}")
async def show_item(item_id: int, user_id: str = Depends(require_token)):
    row = get_item(item_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)


@router.delete("/items/{item_id}", status_code=204)
async def remove_item(item_id: int, user_id: str = Depends(require_token)):
    if not get_item(item_id, user_id):
        raise HTTPException(status_code=404, detail="Not found")
    delete_item(item_id, user_id)


@router.get("/items/{item_id}/file")
async def download_file(item_id: int, user_id: str = Depends(require_token)):
    row = get_item(item_id, user_id)
    if not row or not row["file_path"]:
        raise HTTPException(status_code=404, detail="No file stored for this item")
    p = full_path(row["file_path"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FastAPIFileResponse(str(p))


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

@router.post("/submit/text", status_code=201)
async def submit_text(
    text: str = Form(...),
    user_note: str = Form(""),
    user_id: str = Depends(require_token),
):
    analysis = analyze(text, user_id)
    save_item(user_id, "note", "", text, analysis, user_note)
    return {"analysis": analysis}


@router.post("/submit/url", status_code=201)
async def submit_url(
    url: str = Form(...),
    user_note: str = Form(""),
    user_id: str = Depends(require_token),
):
    fetched = await fetch_url(url)
    if not fetched["text"].strip():
        raise HTTPException(status_code=422, detail="Could not extract content from URL")
    analysis = analyze(fetched["text"], user_id)
    save_item(user_id, "url", url, fetched["text"], analysis, user_note)
    return {"analysis": analysis}


@router.post("/submit/file", status_code=201)
async def submit_file(
    file: UploadFile = File(...),
    user_note: str = Form(""),
    user_id: str = Depends(require_token),
):
    mime = file.content_type or ""
    name = file.filename or "file"
    suffix = f".{name.rsplit('.', 1)[-1]}" if "." in name else ".bin"
    data = await file.read()

    stored_file_path = ""
    if "pdf" in mime:
        stored_file_path = save_file(data, suffix)
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages)[:MAX_CONTENT_CHARS]
        source_type = "document"
    elif mime.startswith("text/"):
        stored_file_path = save_file(data, suffix)
        text = data.decode("utf-8", errors="ignore")[:MAX_CONTENT_CHARS]
        source_type = "document"
    elif mime.startswith("image/"):
        stored_file_path = save_file(data, suffix)
        b64 = base64.b64encode(data).decode()
        text = analyze_image(b64, user_note)
        source_type = "photo"
    elif mime.startswith("audio/") or suffix in (".ogg", ".mp3", ".m4a", ".wav", ".flac"):
        stored_file_path = save_file(data, suffix)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            tmp_path = f.name
        try:
            text = await transcribe(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        source_type = "audio"
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {mime}")

    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from file")

    analysis = analyze(text, user_id)
    save_item(user_id, source_type, name, text, analysis, user_note, file_path=stored_file_path)
    return {"analysis": analysis}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_profile_endpoint(user_id: str = Depends(require_token)):
    return {"content": get_profile(user_id)}


@router.put("/profile", status_code=200)
async def set_profile_endpoint(
    content: str = Form(...),
    user_id: str = Depends(require_token),
):
    set_profile(user_id, content)
    return {"ok": True}
