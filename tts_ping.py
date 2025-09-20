# tts_ping.py
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")  # adjust path if your .env is elsewhere

import azure.cognitiveservices.speech as speechsdk

key = os.getenv("AZURE_SPEECH_KEY")
region = os.getenv("AZURE_SPEECH_REGION", "uae-north")
voice = os.getenv("VOICE_NAME", "en-US-AriaNeural")

assert key, "AZURE_SPEECH_KEY missing"
assert region, "AZURE_SPEECH_REGION missing"

cfg = speechsdk.SpeechConfig(subscription=key, region=region)
cfg.speech_synthesis_voice_name = voice
out = speechsdk.audio.AudioOutputConfig(filename="hello.mp3")
syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
res = syn.speak_text("مرحبا! هذا اختبار.")
print(res.reason, getattr(getattr(res, "cancellation_details", None), "error_details", ""))
