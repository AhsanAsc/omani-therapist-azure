from app.services.llm_service import get_client
import re

RISK_AR = ["انتحار","أؤذي نفسي","أقتل نفسي","أذى","قتل","مميت","ميؤوس","لا أريد العيش","أموت","سأنهي حياتي"]
RISK_EN = ["suicide","kill myself","end my life","self harm","hurt myself","i want to die","no reason to live","hopeless"]

def risk_detect(text: str, lang: str) -> bool:
    t = (text or "").lower()
    keys = RISK_AR if lang == "ar" else RISK_EN
    return any(k in t for k in keys)

async def openai_moderation_block(text: str) -> bool:
    cli = get_client()
    if not cli: return False
    try:
        mod = cli.moderations.create(model="omni-moderation-latest", input=text)
        return bool(getattr(mod.results[0], "flagged", False))
    except Exception:
        return False
