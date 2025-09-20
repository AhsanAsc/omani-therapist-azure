# main.py
import os, io, json, base64, uuid, tempfile, time, asyncio, re
from typing import List, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
import logging, datetime
from starlette.middleware.base import BaseHTTPMiddleware

# -------------------------------------------------------------------
# ENV
# -------------------------------------------------------------------
load_dotenv(".env")
AZ_REGION   = os.getenv("AZURE_SPEECH_REGION", "uaenorth")
AZ_KEY      = os.getenv("AZURE_SPEECH_KEY")
AZ_ENDPOINT = os.getenv("AZURE_SPEECH_ENDPOINT", "").rstrip("/")
VOICE_AR    = os.getenv("VOICE_AR", "ar-OM-AyshaNeural")
VOICE_EN    = os.getenv("VOICE_EN", "en-US-JennyNeural")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SECURE_MODE = os.getenv("SECURE_MODE","false").lower()=="true"
REDACT_LOGS = os.getenv("REDACT_LOGS","true").lower()=="true"
CODE_SWITCHING = os.getenv("CODE_SWITCHING","on").lower() == "on"  # <- feature flag

oai: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# -------------------------------------------------------------------
# APP
# -------------------------------------------------------------------
app = FastAPI(title="Omani Therapist Voice")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
)

SAFE_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "microphone=()",
}

PHI_PATTERNS = [
    r"\b\d{9,16}\b",                  # generic MRN/ID/phone spill
    r"\b(?:\d{3}-?\d{2}-?\d{4})\b",   # SSN-like
    r"\b[\w\.-]+@[\w\.-]+\.\w+\b",    # emails
]

def redact(text: str) -> str:
    if not (text and REDACT_LOGS): return text or ""
    t = text
    for p in PHI_PATTERNS:
        t = re.sub(p, "[REDACTED]", t)
    return t

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        if SECURE_MODE:
            for k,v in SAFE_HEADERS.items(): resp.headers.setdefault(k,v)
        return resp

app.add_middleware(SecurityHeadersMiddleware)

# -------------------------------------------------------------------
# Prompts / Safety / Culture
# -------------------------------------------------------------------
SYS_AR = (
    "أنت معالج/ـة نفسي/ة عماني/ة باللهجة العُمانية. كن موجزاً (٢–٣ جمل) واختم بسؤال متابعة واحد. "
    "استخدم تقنيات مثبتة بالدليل حسب الحاجة: الإنصات النشط، التحقق/التطبيع، صياغة معرفية مبسطة (CBT)، "
    "حلّ مُوجّه نحو الأهداف الصغيرة، وتنظيم الانفعال (تنفس/تأريض). "
    "راعِ القيم الإسلامية والأسرة والخصوصية. تجنّب التشخيص الطبي أو الأدوية."
)

SYS_EN = (
    "You are an Omani, culturally-aware therapist. Be brief (2–3 sentences) and end with one follow-up question. "
    "Prefer evidence-based methods: active listening, validation/normalization, simple CBT reframing, "
    "solution-focused steps, and basic emotion regulation (breathing/grounding). "
    "Respect Islamic values, family context, and privacy. Avoid medical diagnoses or medication advice."
)

RISK_AR = [
    "انتحار", "أؤذي نفسي", "أقتل نفسي", "أذى", "قتل",
    "مميت", "ميؤوس", "لا أريد العيش", "أموت", "سأنهي حياتي"
]
RISK_EN = [
    "suicide", "kill myself", "end my life", "self harm",
    "hurt myself", "i want to die", "no reason to live", "hopeless"
]

EMOTION_LEXICON_AR = {
    "sad": ["حزين", "مكتئب", "يائس", "محبط", "بائس"],
    "anxious": ["قلق", "متوتر", "خائف", "مهموم", "مضطرب"],
    "angry": ["غاضب", "معصب", "زعلان", "مستاء"],
    "stressed": ["مضغوط", "مرهق", "منهك", "ضغط"],
    "hopeful": ["متفائل", "أمل", "واثق", "مبسوط", "سعيد"],
}
EMOTION_LEXICON_EN = {
    "sad": ["sad", "depressed", "down", "hopeless", "miserable"],
    "anxious": ["anxious", "worried", "nervous", "panic", "on edge"],
    "angry": ["angry", "mad", "furious", "irritated"],
    "stressed": ["stressed", "overwhelmed", "burned out", "pressure"],
    "hopeful": ["hopeful", "optimistic", "confident", "grateful", "happy"],
}

CULTURAL_POSITIVE = ["إن شاء الله", "بإذن الله", "الحمد لله", "أهل", "عائلة", "بر الوالدين"]
CULTURAL_RED_FLAGS = [
    "ignore parents", "break family ties", "individual first always",
    "religion is not important"
]
ISLAMIC_COPING_BY_EMOTION = {
    "anxious": "جرّب ذكر الله والتنفس العميق: 'لا إله إلا الله' مع شهيق وزفير هادئ.",
    "sad": "تذكّر قول الله: 'إن مع العسر يسرا'. الدعم موجود وأنت لست وحدك.",
    "angry": "استعذ بالله من الشيطان، وتوضأ إن استطعت، وخذ دقيقة للتهدئة.",
    "stressed": "توكل على الله وخذ الأمور خطوة خطوة. سنضع خطة صغيرة معًا.",
}

# -------------------------------------------------------------------
# Helpers: language, safety, emotion, culture, code-switch spans
# -------------------------------------------------------------------
def contains_arabic(text: str) -> bool:
    return any('\u0600' <= ch <= '\u06FF' for ch in text or "")

def detect_language(text: str) -> str:
    """Return 'ar' or 'en' (simple heuristic on transcript)."""
    return "ar" if contains_arabic(text) else "en"

def risk_detect(text: str, lang: str) -> bool:
    t = (text or "").lower()
    keys = RISK_AR if lang == "ar" else RISK_EN
    return any(k in t for k in keys)

def detect_emotion(text: str, lang: str) -> Dict[str, float]:
    t = (text or "").lower()
    lex = EMOTION_LEXICON_AR if lang == "ar" else EMOTION_LEXICON_EN
    scores: Dict[str, float] = {}
    for label, words in lex.items():
        hits = sum(1 for w in words if w in t)
        if hits:
            scores[label] = min(1.0, hits / max(1, len(words)))
    if not scores:
        scores["neutral"] = 0.5
    return scores

def assess_culture(text: str) -> Dict[str, any]:
    score = 0.8
    issues: List[str] = []

    pos_hits = sum(1 for p in CULTURAL_POSITIVE if p in (text or ""))
    score += min(0.2, pos_hits * 0.05)

    t_low = (text or "").lower()
    neg_hits = sum(1 for r in CULTURAL_RED_FLAGS if r in t_low)
    if neg_hits:
        score -= min(0.3, 0.15 * neg_hits)
        issues.append("May conflict with local family/religious values.")

    if re.search(r"حيات[كه]\s*الجنسية|مشاعر\s*رومانسية|تفاصيل\s*حميمية", text or ""):
        score -= 0.2
        issues.append("Avoid intimate/sexual probing; increase sensitivity.")

    score = max(0.0, min(1.0, score))
    return {"score": score, "issues": issues, "appropriate": score >= 0.7}

def maybe_add_religious_sensitivity(bot_text: str, emotion_scores: Dict[str, float], user_text: str, lang: str) -> str:
    if lang != "ar":
        return bot_text
    need = any(k in (user_text or "") for k in ["الله", "دين", "دعاء", "صلاة"]) or \
           max(emotion_scores.values()) >= 0.7 and any(k in emotion_scores for k in ["anxious","sad","stressed","angry"])
    if not need:
        return bot_text
    if any(p in bot_text for p in CULTURAL_POSITIVE):
        return bot_text
    negative = [(k, v) for k, v in emotion_scores.items() if k in ISLAMIC_COPING_BY_EMOTION]
    negative.sort(key=lambda kv: kv[1], reverse=True)
    addon = ISLAMIC_COPING_BY_EMOTION.get(negative[0][0], None) if negative else None
    return f"{bot_text}\n\n{addon}" if addon else bot_text

async def openai_moderation_block(text: str) -> Optional[str]:
    if not oai:
        return None
    try:
        mod = oai.moderations.create(model="omni-moderation-latest", input=text)
        flagged = getattr(mod.results[0], "flagged", False)
        if flagged:
            return "moderation_flagged"
        return None
    except Exception:
        return None

# --------- Code-switching utilities (script spans + SSML) ----------
AR_RANGE = ('\u0600', '\u06FF')

def _is_ar(ch: str) -> bool:
    return AR_RANGE[0] <= ch <= AR_RANGE[1]

def split_by_script_inline(text: str):
    """
    Returns spans like: [{"lang":"ar","text":"..."}, {"lang":"en","text":"..."}]
    based on Arabic vs non-Arabic Unicode ranges.
    """
    if not text: return []
    spans = []
    # seed by first strong char
    cur_lang = "ar" if any(_is_ar(c) for c in text[:8]) else "en"
    buf = []
    for ch in text:
        lang = "ar" if _is_ar(ch) else "en"
        if lang != cur_lang and buf:
            spans.append({"lang": cur_lang, "text": "".join(buf)})
            buf = [ch]; cur_lang = lang
        else:
            buf.append(ch)
    if buf: spans.append({"lang": cur_lang, "text": "".join(buf)})

    # merge trivial flips (spaces/punct)
    merged = []
    for s in spans:
        if merged and s["lang"] == merged[-1]["lang"]:
            merged[-1]["text"] += s["text"]
        else:
            if len(s["text"].strip()) == 0 and merged:
                merged[-1]["text"] += s["text"]
            else:
                merged.append(s)
    return [s for s in merged if s["text"]]

def build_mixed_ssml(spans, default_lang: str):
    """
    Build SSML using per-span <voice><lang> islands so each language is synthesized
    with its native voice/phonemes in one audio file.
    """
    def voice_for(lang): return VOICE_AR if lang=="ar" else VOICE_EN
    def locale_for(lang): return "ar-OM" if lang=="ar" else "en-US"
    if not spans or all(len((s.get("text") or "").strip()) == 0 for s in spans):
        spans = [{"lang": default_lang, "text": ""}]

    parts = []
    for s in spans:
        txt = (s.get("text") or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        parts.append(
            f"<voice name='{voice_for(s['lang'])}'><lang xml:lang='{locale_for(s['lang'])}'>{txt}</lang></voice>"
        )
    root_locale = "ar-OM" if default_lang=="ar" else "en-US"
    return f"<speak version='1.0' xml:lang='{root_locale}'>{''.join(parts)}</speak>"

def tts_via_rest_ssml(ssml: str) -> bytes:
    endpoint = AZ_ENDPOINT or f"https://{AZ_REGION}.api.cognitive.microsoft.com"
    tok = requests.post(f"{endpoint}/sts/v1.0/issueToken",
                        headers={"Ocp-Apim-Subscription-Key": AZ_KEY}, timeout=20)
    tok.raise_for_status()
    token = tok.text
    r = requests.post(
        f"https://{AZ_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
            "User-Agent": "omani-therapist-voice/1.0",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.content

# -------------------------------------------------------------------
# Azure Speech: dual-language STT + per-language TTS
# -------------------------------------------------------------------
def _speech_cfg_recog():
    assert AZ_KEY, "AZURE_SPEECH_KEY missing"
    cfg = speechsdk.SpeechConfig(subscription=AZ_KEY, region=AZ_REGION)
    # language via auto-detect below
    return cfg

def _speech_cfg_tts(voice_name: str):
    assert AZ_KEY, "AZURE_SPEECH_KEY missing"
    cfg = speechsdk.SpeechConfig(subscription=AZ_KEY, region=AZ_REGION)
    cfg.speech_synthesis_voice_name = voice_name
    return cfg

def pick_voice(lang: str) -> str:
    return VOICE_AR if lang == "ar" else VOICE_EN

async def stt_from_wav_bytes_autolang(wav_bytes: bytes) -> Dict[str, str]:
    """
    Auto-detect between ar-OM and en-US, return {'text':..., 'lang': 'ar'|'en'}.
    """
    cfg = _speech_cfg_recog()
    stream = speechsdk.audio.PushAudioInputStream()
    audio_cfg = speechsdk.audio.AudioConfig(stream=stream)

    auto = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["ar-OM", "en-US"])
    reco = speechsdk.SpeechRecognizer(speech_config=cfg, auto_detect_source_language_config=auto, audio_config=audio_cfg)

    async def _feed():
        stream.write(wav_bytes)
        stream.close()
    asyncio.create_task(_feed())

    res = await asyncio.get_event_loop().run_in_executor(None, reco.recognize_once)

    if res.reason == speechsdk.ResultReason.RecognizedSpeech:
        # Extract detected locale
        lang_result = res.properties.get(
            speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult
        ) or ""
        lang_code = "ar" if "ar" in lang_result else "en"
        return {"text": res.text or "", "lang": lang_code}

    if res.reason == speechsdk.ResultReason.NoMatch:
        return {"text": "", "lang": "ar"}  # default

    details = getattr(res.cancellation_details, "error_details", "")
    raise RuntimeError(f"STT failed: {res.reason} {details}")

def tts_via_rest(text: str, voice_name: str, locale_tag: str) -> bytes:
    endpoint = AZ_ENDPOINT or f"https://{AZ_REGION}.api.cognitive.microsoft.com"
    tok = requests.post(f"{endpoint}/sts/v1.0/issueToken",
                        headers={"Ocp-Apim-Subscription-Key": AZ_KEY}, timeout=20)
    tok.raise_for_status()
    token = tok.text

    ssml = f"""<speak version='1.0' xml:lang='{locale_tag}'>
  <voice xml:lang='{locale_tag}' name='{voice_name}'>{text}</voice>
</speak>"""
    r = requests.post(
        f"https://{AZ_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
            "User-Agent": "omani-therapist-voice/1.0",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.content

async def tts_to_mp3_bytes(text: str, lang: str) -> bytes:
    voice = pick_voice(lang)
    locale = "ar-OM" if lang == "ar" else "en-US"
    try:
        cfg = _speech_cfg_tts(voice)
        tmp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
        out = speechsdk.audio.AudioOutputConfig(filename=tmp)
        syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
        res = await asyncio.get_event_loop().run_in_executor(None, lambda: syn.speak_text(text))
        if res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            with open(tmp, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"[SDK TTS] falling back to REST: {e}")
    return await asyncio.to_thread(tts_via_rest, text, voice, locale)

async def tts_mixed_or_plain(text: str, lang: str, spans=None) -> bytes:
    """
    If spans indicate mixed scripts, synthesize SSML islands; otherwise use plain TTS.
    We never force mixing—only speak what's present in assistant text.
    """
    if CODE_SWITCHING and spans and len([s for s in spans if (s.get("text") or "").strip()]) > 1:
        ssml = build_mixed_ssml(spans, default_lang=lang)
        # Try SDK SSML first
        try:
            cfg = _speech_cfg_tts(pick_voice(lang))
            tmp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
            out = speechsdk.audio.AudioOutputConfig(filename=tmp)
            syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
            res = await asyncio.get_event_loop().run_in_executor(None, lambda: syn.speak_ssml(ssml))
            if res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                with open(tmp, "rb") as f:
                    return f.read()
        except Exception as e:
            print(f"[SDK SSML] falling back to REST: {e}")
        # REST SSML fallback
        return await asyncio.to_thread(tts_via_rest_ssml, ssml)
    # Plain path
    return await tts_to_mp3_bytes(text, lang)

# -------------------------------------------------------------------
# LLM
# -------------------------------------------------------------------
async def gpt_reply(user_text: str, history: List[Dict], lang: str) -> str:
    if not oai:
        return "أفهمك. خلّنا نفهم أكثر: متى بدأ هذا الشعور؟ وما المواقف التي تزيده؟" if lang == "ar" \
               else "I hear you. When did this start, and what tends to make it feel stronger?"
    sys = SYS_AR if lang == "ar" else SYS_EN
    msgs = [{"role":"system","content":sys}] + history + [{"role":"user","content":user_text}]
    res = oai.chat.completions.create(model="gpt-4o-mini", messages=msgs, temperature=0.4, max_tokens=180)
    return (res.choices[0].message.content or "").strip()

# -------------------------------------------------------------------
# HTTP
# -------------------------------------------------------------------
@app.get("/health", tags=["misc"])
def health():
    return {"status":"ok","region":AZ_REGION,"voice_ar":VOICE_AR,"voice_en":VOICE_EN,"openai":bool(oai),"code_switching":CODE_SWITCHING}

class TTSIn(BaseModel): text: str; lang: Optional[str] = "ar"
@app.post("/tts", tags=["speech"])
async def tts_endpoint(body: TTSIn):
    spans = split_by_script_inline(body.text) if CODE_SWITCHING else None
    mp3 = await tts_mixed_or_plain(body.text, body.lang or "ar", spans=spans)
    return StreamingResponse(io.BytesIO(mp3), media_type="audio/mpeg")

@app.post("/stt", tags=["speech"])
async def stt_endpoint(file: UploadFile = File(...)):
    data = await file.read()
    res = await stt_from_wav_bytes_autolang(data)
    return res  # {"text":..., "lang":"ar"|"en"}

class ChatIn(BaseModel): user_text: str
@app.post("/chat", tags=["chat"])
async def chat_endpoint(body: ChatIn):
    u = body.user_text or ""
    lang = detect_language(u)

    if risk_detect(u, lang):
        crisis = ("سلامتك أولاً. إذا كان هناك خطر مباشر، اتصل بالطوارئ فورًا (999). خط المساعدة: 80077.") if lang=="ar" \
                 else ("Your safety comes first. If you’re in immediate danger call local emergency services now. In Oman, dial 999. Helpline: 80077.")
        return {"assistant_text": crisis, "safety":"crisis", "lang": lang, "emotion": detect_emotion(u, lang)}

    mod_flag = await openai_moderation_block(u)
    if mod_flag in {"moderation_flagged"}:
        crisis = ("أقدّر صراحتك. إذا كان هناك خطر مباشر اتصل بالطوارئ (999). خط المساعدة: 80077.") if lang=="ar" \
                 else ("Thanks for sharing. If there’s any immediate danger call 999 (in Oman). Mental health helpline: 80077.")
        return {"assistant_text": crisis, "safety":"crisis", "lang": lang, "emotion": detect_emotion(u, lang)}

    a = await gpt_reply(u, history=[], lang=lang)
    emo = detect_emotion(u, lang)
    a = maybe_add_religious_sensitivity(a, emo, u, lang)  # only affects Arabic
    cult = assess_culture(a)

    # Code-switch TTS spans are driven by assistant text itself (if mixed)
    spans_bot = split_by_script_inline(a) if CODE_SWITCHING else None

    return {
        "assistant_text": a,
        "safety":"ok",
        "lang": lang,
        "emotion": emo,
        "culture": cult,
        "mixed_spans": spans_bot  # useful for clients if needed
    }

# -------------------------------------------------------------------
# WebSocket (voice+text)
# -------------------------------------------------------------------
@app.websocket("/ws/{session_id}")
async def ws_handler(ws: WebSocket, session_id: str):
    await ws.accept()
    history: List[Dict] = []
    showed_disclaimer = False

    async def send_disclaimer(lang: str):
        nonlocal showed_disclaimer
        if showed_disclaimer: return
        txt = ("أنا دعم نفسي عام ولست بديلاً عن رعاية طبية طارئة. "
               "لو في خطر مباشر اتصل بالطوارئ 999. خصوصيتك مهمة لنا.") if lang=="ar" else \
              ("I provide supportive counseling and am not a substitute for emergency care. "
               "If you’re in immediate danger call 999. Your privacy matters.")
        await ws.send_text(json.dumps({"type":"notice","kind":"disclaimer","text":txt,"lang":lang}))
        showed_disclaimer = True

    async def respond(user_text: str, lang: str):
        start = time.perf_counter()

        await send_disclaimer(lang)

        # Safety
        if risk_detect(user_text, lang):
            bot = ("سلامتك أولاً. إذا كان هناك خطر مباشر، اتصل بالطوارئ فورًا (999). خط المساعدة: 80077.") if lang=="ar" \
                  else ("Your safety comes first. If there’s immediate danger call 999. Helpline: 80077.")
            mp3 = await tts_to_mp3_bytes(bot, lang)
            await ws.send_text(json.dumps({"type":"crisis_alert","response":bot,"lang":lang}))
            await ws.send_text(json.dumps({
                "type":"audio_response",
                "transcript": user_text,
                "response_text": bot,
                "audio_data": base64.b64encode(mp3).decode("ascii"),
                "processing_time": time.perf_counter() - start,
                "emotion": detect_emotion(user_text, lang),
                "culture": assess_culture(bot),
                "safety": "crisis",
                "lang": lang
            }))
            history.extend([{"role":"user","content":user_text},{"role":"assistant","content":bot}])
            return

        mod_flag = await openai_moderation_block(user_text)
        if mod_flag in {"moderation_flagged"}:
            bot = ("أقدّر مشاركتك. إذا كان هناك خطر مباشر اتصل بالطوارئ (999). خط المساعدة: 80077.") if lang=="ar" \
                  else ("I appreciate you sharing. If there’s immediate danger call 999. Helpline: 80077.")
            mp3 = await tts_to_mp3_bytes(bot, lang)
            await ws.send_text(json.dumps({"type":"crisis_alert","response":bot,"lang":lang}))
            await ws.send_text(json.dumps({
                "type":"audio_response",
                "transcript": user_text,
                "response_text": bot,
                "audio_data": base64.b64encode(mp3).decode("ascii"),
                "processing_time": time.perf_counter() - start,
                "emotion": detect_emotion(user_text, lang),
                "culture": assess_culture(bot),
                "safety": "crisis",
                "lang": lang
            }))
            history.extend([{"role":"user","content":user_text},{"role":"assistant","content":bot}])
            return

        # Normal flow
        bot = await gpt_reply(user_text, history, lang=lang)
        emo = detect_emotion(user_text, lang)
        bot = maybe_add_religious_sensitivity(bot, emo, user_text, lang)
        cult = assess_culture(bot)

        history.extend([{"role":"user","content":user_text},{"role":"assistant","content":bot}])

        # Text response for UI
        await ws.send_text(json.dumps({
            "type":"text_response", "response": bot, "emotion": emo, "culture": cult, "safety":"ok", "lang": lang
        }))

        # Voice response (code-switching if assistant text is mixed)
        spans_bot = split_by_script_inline(bot) if CODE_SWITCHING else None
        mp3 = await tts_mixed_or_plain(bot, lang, spans=spans_bot)
        await ws.send_text(json.dumps({
            "type":"audio_response",
            "transcript": user_text,
            "response_text": bot,
            "audio_data": base64.b64encode(mp3).decode("ascii"),
            "processing_time": time.perf_counter() - start,
            "emotion": emo,
            "culture": cult,
            "safety": "ok",
            "lang": lang
        }))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                await ws.send_text(json.dumps({"type":"error","message":"bad_json"}))
                continue

            t = data.get("type")
            if t == "audio_chunk":
                try:
                    wav_b64 = data["audio_data"]
                    wav = base64.b64decode(wav_b64)
                    stt = await stt_from_wav_bytes_autolang(wav)  # {"text":..., "lang":...}
                    user_text, lang = stt.get("text",""), stt.get("lang","ar")
                    await respond(user_text, lang)
                except Exception as e:
                    await ws.send_text(json.dumps({"type":"error","message":f"audio_error: {e}"}))

            elif t == "text_message":
                msg = (data.get("message") or "").strip()
                if not msg:
                    await ws.send_text(json.dumps({"type":"error","message":"empty_message"}))
                    continue
                lang = detect_language(msg)
                await respond(msg, lang)

            else:
                await ws.send_text(json.dumps({"type":"error","message":"unknown_type"}))

    except WebSocketDisconnect:
        pass
