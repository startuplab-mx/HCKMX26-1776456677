"""
Voice transcription endpoint — Groq Whisper.
Accepts audio upload, returns transcript.
Moderation happens client-side via the normal WebSocket flow.
"""
import io
from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Request
from openai import OpenAI

from config import get_settings

router = APIRouter()
settings = get_settings()


def _call_whisper(audio_bytes: bytes, filename: str) -> str:
    client = OpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    result = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=buf,
        language="es",
        response_format="text",
        prompt="Transcribe el audio exactamente una vez, sin repetir.",
    )
    text = result if isinstance(result, str) else result.text
    return _dedup_transcript(text)


def _dedup_transcript(text: str) -> str:
    """Remove exact repetition: 'X X' → 'X' when second half equals first half."""
    t = text.strip()
    mid = len(t) // 2
    # Check exact halves (with possible space separator)
    for sep in (" ", ""):
        half = mid if sep == "" else mid - (len(sep) // 2)
        first = t[:half].strip()
        second = t[half:].strip().lstrip(sep)
        if first and first == second:
            return first
    # Check sentence-level repetition
    sentences = [s.strip() for s in t.replace("?", "?.").replace("!", "!.").split(".") if s.strip()]
    if len(sentences) >= 2:
        half = len(sentences) // 2
        if sentences[:half] == sentences[half:half * 2]:
            return ". ".join(sentences[:half])
    return t


@router.post("/voice/transcribe", summary="Transcribe voice audio via Groq Whisper (multipart)")
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (webm/ogg/wav/mp3)"),
    x_api_key: str = Header(...),
):
    if x_api_key != settings.api_key_secret:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="Groq API key not configured")

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=422, detail="Audio too short or empty")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Audio too large (max 25 MB)")

    try:
        transcript = _call_whisper(audio_bytes, audio.filename or "voice.webm")
        return {"transcript": transcript.strip()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"STT error: {str(e)[:120]}")


@router.post("/voice/transcribe/raw", summary="Transcribe raw WAV bytes (Unity SDK)")
async def transcribe_raw(
    request: Request,
    x_api_key: str = Header(...),
):
    """Accepts raw audio bytes in body — for Unity UnityWebRequest.uploadHandler = UploadHandlerRaw."""
    if x_api_key != settings.api_key_secret:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="Groq API key not configured")

    audio_bytes = await request.body()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=422, detail="Audio too short or empty")

    content_type = request.headers.get("content-type", "audio/wav")
    ext_map = {"audio/wav": "voice.wav", "audio/ogg": "voice.ogg", "audio/webm": "voice.webm",
               "audio/mpeg": "voice.mp3", "audio/mp3": "voice.mp3"}
    filename = ext_map.get(content_type, "voice.wav")

    try:
        transcript = _call_whisper(audio_bytes, filename)
        return {"transcript": transcript.strip()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"STT error: {str(e)[:120]}")
