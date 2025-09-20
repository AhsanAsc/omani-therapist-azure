from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json, base64, time
from app.services.speech_service import stt_from_wav_autolang
from app.services.conversation import handle_turn
from app.utils.language import detect_lang

router = APIRouter()

@router.websocket("/ws/{session_id}")
async def ws_handler(ws: WebSocket, session_id: str):
    await ws.accept()
    history: list[dict] = []

    async def send_disclaimer(lang: str):
        txt = ("أنا دعم نفسي عام ولست بديلاً عن رعاية طبية طارئة. إذا كان هناك خطر مباشر اتصل بـ 999."
               if lang == "ar" else
               "I provide supportive counseling and am not a substitute for emergency care. If in danger, call 999.")
        await ws.send_text(json.dumps({
            "type": "notice",
            "kind": "disclaimer",
            "text": txt,
            "lang": lang
        }))

    showed_disclaimer = False

    async def respond(user_text: str, lang_guess: str, want_voice: bool):
        """
        - lang_guess is the detected language from input (STT or typing).
        - want_voice controls whether we send back audio.
        """
        nonlocal showed_disclaimer
        if not showed_disclaimer:
            # show disclaimer in the user's detected language for this turn
            await send_disclaimer(lang_guess)
            showed_disclaimer = True

        start = time.perf_counter()

        out = await handle_turn(user_text, history)

        # Persist to history using the authoritative assistant text
        history.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": out.get("text", "")}
        ])

        # Always send text
        await ws.send_text(json.dumps({
            "type": "text_response",
            "response": out.get("text", ""),
            "lang": out.get("lang", lang_guess),
            "safety": out.get("safety", "ok"),
            "culture": out.get("culture"),
            "emotion": out.get("emotion")
        }))

        # Only send audio if the client requested voice for this turn
        audio_bytes = out.get("audio", None)
        if want_voice and audio_bytes:
            await ws.send_text(json.dumps({
                "type": "audio_response",
                "transcript": user_text,
                "response_text": out.get("text", ""),
                "audio_data": base64.b64encode(audio_bytes).decode("ascii"),
                "processing_time": time.perf_counter() - start,
                "lang": out.get("lang", lang_guess),
                "safety": out.get("safety", "ok")
            }))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                await ws.send_text(json.dumps({"type": "error", "message": "bad_json"}))
                continue

            msg_type = data.get("type")

            if msg_type == "audio_chunk":
                want_voice = True if data.get("prefer_voice") is None else bool(data.get("prefer_voice"))
                try:
                    wav = base64.b64decode(data["audio_data"])
                    stt = await stt_from_wav_autolang(wav)
                    user_text = stt.get("text", "") or ""
                    lang = stt.get("lang", "ar")
                    await respond(user_text, lang, want_voice=True if want_voice else False)
                except Exception as e:
                    await ws.send_text(json.dumps({"type": "error", "message": f"audio_error: {e}"}))

            elif msg_type == "text_message":
                msg = (data.get("message") or "").strip()
                if not msg:
                    await ws.send_text(json.dumps({"type": "error", "message": "empty_message"}))
                    continue
                lang = detect_lang(msg)
                want_voice = bool(data.get("prefer_voice"))
                await respond(msg, lang, want_voice=want_voice)

            else:
                await ws.send_text(json.dumps({"type": "error", "message": "unknown_type"}))

    except WebSocketDisconnect:
        pass
