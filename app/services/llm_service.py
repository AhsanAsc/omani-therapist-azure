from openai import OpenAI
from app.config import get_settings

SYS_AR = ("أنت معالج/ـة نفسي/ة عماني/ة باللهجة العُمانية. كن موجزاً (٢–٣ جمل) واختم بسؤال متابعة واحد. "
          "استخدم تقنيات مثبتة بالدليل: الإنصات النشط، التحقق/التطبيع، صياغة معرفية مبسطة، تنظيم الانفعال. "
          "راعِ القيم الإسلامية والأسرة والخصوصية. تجنّب التشخيص الطبي أو الأدوية.")
SYS_EN = ("You are an Omani, culturally-aware therapist. Be brief (2–3 sentences) and end with one follow-up question. "
          "Use evidence-based methods (active listening, validation, simple CBT, emotion regulation). "
          "Respect Islamic values, family context, and privacy. No diagnoses/medication advice.")

_client = None
def get_client() -> OpenAI | None:
    global _client
    s = get_settings()
    if not s.OPENAI_API_KEY:
        return None
    if _client is None:
        _client = OpenAI(api_key=s.OPENAI_API_KEY)
    return _client

def _sys(lang: str) -> str:
    return SYS_AR if lang == "ar" else SYS_EN

async def chat_reply(user_text: str, history: list[dict], lang: str) -> str:
    cli = get_client()
    if not cli:
        return ("أفهمك. خلّنا نفهم أكثر: متى بدأ هذا الشعور؟ وما المواقف التي تزيده؟"
                if lang == "ar" else
                "I hear you. When did this start, and what tends to make it stronger?")
    s = get_settings()
    msgs = [{"role": "system", "content": _sys(lang)}] + history + [{"role": "user", "content": user_text}]
    res = cli.chat.completions.create(
        model=s.OPENAI_MODEL, messages=msgs, temperature=s.TEMP, max_tokens=s.MAX_TOKENS
    )
    return (res.choices[0].message.content or "").strip()
