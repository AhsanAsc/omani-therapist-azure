from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import io

from app.services.speech_service import tts_to_mp3, stt_from_wav_autolang
from app.services.conversation import handle_turn
from app.utils.language import detect_lang

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

class TTSIn(BaseModel):
    text: str
    lang: str | None = "ar"

@router.post("/tts")
async def tts(body: TTSIn):
    mp3 = await tts_to_mp3(body.text, body.lang or "ar")
    return StreamingResponse(io.BytesIO(mp3), media_type="audio/mpeg")

@router.post("/stt")
async def stt(file: UploadFile = File(...)):
    data = await file.read()
    return await stt_from_wav_autolang(data)

class ChatIn(BaseModel):
    user_text: str

@router.post("/chat")
async def chat(body: ChatIn):
    u = body.user_text or ""
    lang = detect_lang(u)
    out = await handle_turn(u, history=[])
    return JSONResponse({
        "assistant_text": out["text"],
        "lang": out["lang"],
        "safety": out["safety"],
        "culture": out.get("culture"),
        "emotion": out.get("emotion")
    })
