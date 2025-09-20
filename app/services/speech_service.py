import os, uuid, tempfile, asyncio, requests
import azure.cognitiveservices.speech as speechsdk
from typing import Dict, List, Optional
from app.config import get_settings

# -----------------------------
# Internal helpers
# -----------------------------
def _recog_cfg() -> speechsdk.SpeechConfig:
    """
    Base recognizer config. Per-call tuning (timeouts, profanity, etc.)
    is applied where the recognizer is created.
    """
    s = get_settings()
    assert s.AZURE_SPEECH_KEY, "AZURE_SPEECH_KEY missing"
    assert s.AZURE_SPEECH_REGION, "AZURE_SPEECH_REGION missing"
    return speechsdk.SpeechConfig(subscription=s.AZURE_SPEECH_KEY, region=s.AZURE_SPEECH_REGION)

def _synth_cfg(voice: str) -> speechsdk.SpeechConfig:
    s = get_settings()
    assert s.AZURE_SPEECH_KEY, "AZURE_SPEECH_KEY missing"
    assert s.AZURE_SPEECH_REGION, "AZURE_SPEECH_REGION missing"
    cfg = speechsdk.SpeechConfig(subscription=s.AZURE_SPEECH_KEY, region=s.AZURE_SPEECH_REGION)
    cfg.speech_synthesis_voice_name = voice
    return cfg

def pick_voice(lang: str) -> str:
    s = get_settings()
    return s.VOICE_AR if lang == "ar" else s.VOICE_EN

def _locale_for(lang: str) -> str:
    return "ar-OM" if lang == "ar" else "en-US"

# -----------------------------
# Speech-to-Text (Auto ar/en)
# -----------------------------
async def stt_from_wav_autolang(wav_bytes: bytes) -> Dict[str, str]:
    """
    Auto-detect between ar-OM and en-US. Returns {"text": str, "lang": "ar"|"en"}.
    Tuned for natural pauses + therapy domain phrase hints.
    """
    cfg = _recog_cfg()
    # Tuned timeouts for longer natural pauses, and keep raw text
    cfg.set_property(speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "3000")
    cfg.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "1200")
    cfg.set_property(speechsdk.PropertyId.SpeechServiceResponse_ProfanityOption, "raw")

    stream = speechsdk.audio.PushAudioInputStream()
    audio_cfg = speechsdk.audio.AudioConfig(stream=stream)
    auto = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["ar-OM", "en-US"])

    reco = speechsdk.SpeechRecognizer(
        speech_config=cfg,
        auto_detect_source_language_config=auto,
        audio_config=audio_cfg
    )

    # Phrase hints: Arabic + English therapy vocabulary, hotline numbers, etc.
    try:
        phrases = [
            "CBT", "breathing", "grounding", "panic", "anxiety", "depression",
            "Aysha", "Omani", "helpline", "80077", "999",
            "إن شاء الله", "بإذن الله", "توكل", "قلق", "ضغط", "تنفّس", "ذكر", "عُماني",
        ]
        plist = speechsdk.PhraseListGrammar.from_recognizer(reco)
        for p in phrases:
            plist.addPhrase(p)
    except Exception:
        # If phrase list fails (SDK version mismatch), just proceed without it.
        pass

    async def _feed():
        stream.write(wav_bytes)
        stream.close()
    asyncio.create_task(_feed())

    res = await asyncio.get_event_loop().run_in_executor(None, reco.recognize_once)

    if res.reason == speechsdk.ResultReason.RecognizedSpeech:
        lang_res = res.properties.get(
            speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult
        ) or ""
        lang = "ar" if "ar" in lang_res else "en"
        return {"text": res.text or "", "lang": lang}

    if res.reason == speechsdk.ResultReason.NoMatch:
        # Default to Arabic if nothing recognized (keeps downstream flow stable)
        return {"text": "", "lang": "ar"}

    details = getattr(res.cancellation_details, "error_details", "")
    raise RuntimeError(f"STT failed: {res.reason} {details}")

# -----------------------------
# Text-to-Speech (plain + SSML)
# -----------------------------
def _tts_rest(text: str, voice: str, locale: str) -> bytes:
    """
    Plain text REST fallback TTS (MP3 16kHz mono, 32kbps).
    """
    s = get_settings()
    endpoint = s.AZURE_SPEECH_ENDPOINT or f"https://{s.AZURE_SPEECH_REGION}.api.cognitive.microsoft.com"
    tok = requests.post(
        f"{endpoint}/sts/v1.0/issueToken",
        headers={"Ocp-Apim-Subscription-Key": s.AZURE_SPEECH_KEY},
        timeout=20
    )
    tok.raise_for_status()
    token = tok.text

    ssml = f"<speak version='1.0' xml:lang='{locale}'><voice xml:lang='{locale}' name='{voice}'>{text}</voice></speak>"
    r = requests.post(
        f"https://{s.AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
            "User-Agent": "omani-therapist-voice/1.0",
        },
        timeout=30
    )
    r.raise_for_status()
    return r.content

def _tts_rest_ssml(ssml: str) -> bytes:
    """
    SSML REST fallback (for mixed language “islands”).
    """
    s = get_settings()
    endpoint = s.AZURE_SPEECH_ENDPOINT or f"https://{s.AZURE_SPEECH_REGION}.api.cognitive.microsoft.com"
    tok = requests.post(
        f"{endpoint}/sts/v1.0/issueToken",
        headers={"Ocp-Apim-Subscription-Key": s.AZURE_SPEECH_KEY},
        timeout=20
    )
    tok.raise_for_status()
    token = tok.text

    r = requests.post(
        f"https://{s.AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
            "User-Agent": "omani-therapist-voice/1.0",
        },
        timeout=30
    )
    r.raise_for_status()
    return r.content

async def tts_to_mp3(text: str, lang: str) -> bytes:
    """
    Plain single-language TTS with SDK first; REST fallback.
    """
    voice = pick_voice(lang)
    locale = _locale_for(lang)
    try:
        cfg = _synth_cfg(voice)
        tmp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
        out = speechsdk.audio.AudioOutputConfig(filename=tmp)
        syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
        res = await asyncio.get_event_loop().run_in_executor(None, lambda: syn.speak_text(text))
        if res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            with open(tmp, "rb") as f:
                return f.read()
    except Exception:
        pass
    return await asyncio.to_thread(_tts_rest, text, voice, locale)

# -----------------------------
# Code-switching TTS
# -----------------------------
def build_mixed_ssml(spans: List[Dict[str, str]], default_lang: str = "ar") -> str:
    """
    Build SSML with language islands. Each span: {"text": "...", "lang": "ar"|"en"}.
    Chooses voice per island based on lang. Keeps whitespace minimal.
    """
    s = get_settings()
    def voice_for(l):
        return (s.VOICE_AR, "ar-OM") if l == "ar" else (s.VOICE_EN, "en-US")

    parts = ["<speak version='1.0'>"]
    for sp in spans:
        t = (sp.get("text") or "").strip()
        if not t:
            continue
        l = sp.get("lang") or default_lang
        v, loc = voice_for(l)
        parts.append(f"<voice xml:lang='{loc}' name='{v}'>{t}</voice>")
        parts.append(" ")
    parts.append("</speak>")
    return "".join(parts)

async def tts_mixed_or_plain(text: str, lang: str, spans: Optional[List[Dict[str, str]]] = None) -> bytes:
    """
    If spans indicate mixed scripts, synthesize SSML islands; else plain TTS.
    This speaks exactly what the assistant produced (no forced mixing).
    """
    s = get_settings()
    code_switching = getattr(s, "CODE_SWITCHING", True)

    # Mixed path only if enabled and we actually have >1 non-empty spans
    if code_switching and spans:
        non_empty = [sp for sp in spans if (sp.get("text") or "").strip()]
        langs = {sp.get("lang") for sp in non_empty if (sp.get("lang") in {"ar", "en"})}
        if len(non_empty) > 1 and len(langs) > 1:
            ssml = build_mixed_ssml(non_empty, default_lang=lang)
            # SDK SSML first
            try:
                cfg = _synth_cfg(pick_voice(lang))
                tmp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
                out = speechsdk.audio.AudioOutputConfig(filename=tmp)
                syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
                res = await asyncio.get_event_loop().run_in_executor(None, lambda: syn.speak_ssml(ssml))
                if res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    with open(tmp, "rb") as f:
                        return f.read()
            except Exception:
                pass
            # REST SSML fallback
            return await asyncio.to_thread(_tts_rest_ssml, ssml)

    # Plain single-language path
    return await tts_to_mp3(text, lang)
