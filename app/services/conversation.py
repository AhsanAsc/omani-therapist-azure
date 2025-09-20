from app.services.speech_service import tts_to_mp3
from app.services.llm_service import chat_reply
from app.services.safety import risk_detect, openai_moderation_block
from app.services.culture import assess, maybe_add_religious
from app.utils.language import detect_lang, emotion_hint

async def handle_turn(user_text: str, history: list[dict]):
    lang = detect_lang(user_text)
    # Safety checks
    if risk_detect(user_text, lang) or await openai_moderation_block(user_text):
        crisis = ("سلامتك أولاً. إذا كان هناك خطر مباشر، اتصل بالطوارئ فورًا (999). خط المساعدة: 80077."
                  if lang=="ar" else
                  "Your safety comes first. If there’s immediate danger call 999. Helpline: 80077.")
        mp3 = await tts_to_mp3(crisis, lang)
        return {"text": crisis, "lang": lang, "audio": mp3, "safety":"crisis", "culture": assess(crisis)}

    # Normal flow
    bot = await chat_reply(user_text, history, lang=lang)
    emo = emotion_hint(user_text, lang)
    bot = maybe_add_religious(bot, lang, emo, user_text)
    mp3 = await tts_to_mp3(bot, lang)
    return {"text": bot, "lang": lang, "audio": mp3, "safety":"ok", "culture": assess(bot), "emotion": emo}
