import re

CULTURAL_POSITIVE = ["إن شاء الله","بإذن الله","الحمد لله","أهل","عائلة","بر الوالدين"]
CULTURAL_RED_FLAGS = ["ignore parents","break family ties","individual first always","religion is not important"]
ISLAMIC_COPING = {
    "anxious": "جرّب ذكر الله والتنفس العميق: 'لا إله إلا الله' مع شهيق وزفير هادئ.",
    "sad": "تذكّر قول الله: 'إن مع العسر يسرا'. الدعم موجود وأنت لست وحدك.",
    "angry": "استعذ بالله من الشيطان، وتوضأ إن استطعت، وخذ دقيقة للتهدئة.",
    "stressed": "توكل على الله وخذ الأمور خطوة خطوة. سنضع خطة صغيرة معًا.",
}

def assess(text: str) -> dict:
    score = 0.8; issues=[]
    pos_hits = sum(1 for p in CULTURAL_POSITIVE if p in (text or ""))
    score += min(0.2, pos_hits * 0.05)
    tl = (text or "").lower()
    neg_hits = sum(1 for r in CULTURAL_RED_FLAGS if r in tl)
    if neg_hits:
        score -= min(0.3, 0.15 * neg_hits)
        issues.append("May conflict with local family/religious values.")
    if re.search(r"حيات[كه]\s*الجنسية|مشاعر\s*رومانسية|تفاصيل\s*حميمية", text or ""):
        score -= 0.2; issues.append("Avoid intimate/sexual probing; increase sensitivity.")
    return {"score": max(0.0, min(1.0, score)), "issues": issues, "appropriate": score >= 0.7}

def maybe_add_religious(bot_text: str, lang: str, emotion_hint: str|None, user_text: str) -> str:
    if lang != "ar": return bot_text
    if any(k in (user_text or "") for k in ["الله","دين","دعاء","صلاة"]):
        addon = ISLAMIC_COPING.get(emotion_hint or "", None)
        if addon and all(p not in bot_text for p in CULTURAL_POSITIVE):
            return f"{bot_text}\n\n{addon}"
    return bot_text
