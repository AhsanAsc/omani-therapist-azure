def contains_arabic(text: str) -> bool:
    return any('\u0600' <= ch <= '\u06FF' for ch in text or "")

def detect_lang(text: str) -> str:
    return "ar" if contains_arabic(text) else "en"

EMO_AR = {
    "sad": ["حزين","مكتئب","يائس","محبط","بائس"],
    "anxious": ["قلق","متوتر","خائف","مهموم","مضطرب"],
    "angry": ["غاضب","معصب","زعلان","مستاء"],
    "stressed": ["مضغوط","مرهق","منهك","ضغط"],
    "hopeful": ["متفائل","أمل","واثق","مبسوط","سعيد"]
}
EMO_EN = {
    "sad": ["sad","depressed","down","hopeless","miserable"],
    "anxious": ["anxious","worried","nervous","panic","on edge"],
    "angry": ["angry","mad","furious","irritated"],
    "stressed": ["stressed","overwhelmed","burned out","pressure"],
    "hopeful": ["hopeful","optimistic","confident","grateful","happy"]
}

def emotion_hint(text: str, lang: str) -> str|None:
    t = (text or "").lower()
    lex = EMO_AR if lang=="ar" else EMO_EN
    best=None; best_hits=0
    for label, words in lex.items():
        hits = sum(1 for w in words if w in t)
        if hits>best_hits: best, best_hits = label, hits
    return best
