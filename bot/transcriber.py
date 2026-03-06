import asyncio
import logging

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper base model (first run downloads ~150 MB)...")
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def _transcribe_sync(file_path: str) -> str:
    model = _get_model()
    segments, info = model.transcribe(file_path, beam_size=5)
    text = " ".join(s.text for s in segments).strip()
    logger.info(f"Transcribed {file_path} ({info.language}, {info.duration:.1f}s)")
    return text


async def transcribe(file_path: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, file_path)
