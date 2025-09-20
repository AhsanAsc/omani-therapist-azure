from typing import Dict
from app.services.speech_service import stt_from_wav_autolang, tts_to_mp3, pick_voice

async def transcribe_autolang(wav_bytes: bytes) -> Dict[str, str]:
    """Return {'text': str, 'lang': 'ar'|'en'}."""
    return await stt_from_wav_autolang(wav_bytes)

async def synthesize(text: str, lang: str) -> bytes:
    """Return MP3 bytes in chosen language."""
    return await tts_to_mp3(text, lang)

__all__ = ["transcribe_autolang", "synthesize", "pick_voice"]
