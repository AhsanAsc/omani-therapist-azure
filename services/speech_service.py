"""
Speech Service - Free Implementation using Whisper + Coqui TTS
Handles Omani Arabic speech recognition and synthesis
"""

import os
import asyncio
import logging
import base64
import io
import tempfile
from typing import Optional, Dict, Any

import whisper
import torch
import numpy as np
from TTS.api import TTS
from pydub import AudioSegment
import soundfile as sf

from torch.serialization import add_safe_globals
from TTS.tts.configs.xtts_config import XttsConfig

logger = logging.getLogger(__name__)

class SpeechService:
    def __init__(self):
        self.whisper_model = None
        self.tts_model = None
        self.model_size = os.getenv("WHISPER_MODEL_SIZE", "medium")
        #self.tts_model_name = os.getenv("TTS_MODEL", "tts_models/ar/common_voice/tacotron2-DDC")
        self.tts_model_name = os.getenv("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
        self.tts_language = os.getenv("TTS_LANGUAGE", "ar")
        self.tts_speaker_wav = os.getenv("TTS_SPEAKER_WAV", "").strip() or None

        add_safe_globals([XttsConfig])
        self.tts_model_name = self._normalize_tts_model_name(self.tts_model_name)
        logger.info(f"Loading TTS model: {self.tts_model_name}")
        self.tts_model = TTS(self.tts_model_name)
        logger.info("TTS model loaded successfully")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.ready = False

        self.tts_language = os.getenv("TTS_LANGUAGE", "ar")
        self.tts_speaker_wav = os.getenv("TTS_SPEAKER_WAV", "").strip() or None


    async def initialize(self):
        """Initialize speech models"""
        try:
            logger.info("Initializing Speech Service...")
            
            # Load Whisper model
            logger.info(f"Loading Whisper {self.model_size} model...")
            self.whisper_model = whisper.load_model(self.model_size, device=self.device)
            logger.info("Whisper model loaded successfully")
            
            add_safe_globals([XttsConfig])
            self.tts_model_name = self._normalize_tts_model_name(self.tts_model_name)
            logger.info(f"Loading TTS model: {self.tts_model_name}")
            self.tts_model = TTS(self.tts_model_name)

            # Load TTS model
            logger.info(f"Loading TTS model: {self.tts_model_name}")
            self.tts_model = TTS(self.tts_model_name)
            logger.info("TTS model loaded successfully")

            self.ready = True
            logger.info("Speech Service initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize Speech Service: {e}")
            raise

    async def speech_to_text(self, audio_data: bytes, language: str = "ar") -> str:
        """Convert speech to text using Whisper"""
        if not self.ready:
            raise RuntimeError("Speech service not initialized")
        
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Transcribe using Whisper
                result = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self._transcribe_audio, 
                    temp_file_path, 
                    language
                )
                
                return result["text"].strip()
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"STT Error: {e}")
            raise

    def _transcribe_audio(self, audio_path: str, language: str) -> Dict[str, Any]:
        """Internal method to transcribe audio"""
        return self.whisper_model.transcribe(
            audio_path,
            language=language,
            task="transcribe",
            fp16=False,
            temperature=0.0,
            best_of=5,
            beam_size=5,
            patience=1.0,
            length_penalty=1.0,
            suppress_tokens="-1",
            initial_prompt="هذا محادثة علاجية باللهجة العمانية العربية"
        )

    async def text_to_speech(self, text: str, language: str = "ar") -> str:
        """Convert text to speech using Coqui TTS"""
        if not self.ready:
            raise RuntimeError("Speech service not initialized")
        
        try:
            # Clean and prepare text
            cleaned_text = self._clean_arabic_text(text)
            
            # Generate speech
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            try:
                # Run TTS in executor to avoid blocking
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._synthesize_speech,
                    cleaned_text,
                    temp_file_path
                )
                
                # Read generated audio and encode as base64
                with open(temp_file_path, "rb") as audio_file:
                    audio_data = audio_file.read()
                    
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                return audio_base64
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            # Return empty audio if TTS fails
            return ""

    def _synthesize_speech(self, text: str, output_path: str):
        """Internal method to synthesize speech"""
        try:
            kwargs = {}
            # Only pass language if the model supports it (XTTS v2 does)
            if self.tts_language:
                kwargs["language"] = self.tts_language  # e.g., "ar"

            if self.tts_speaker_wav:
                kwargs["speaker_wav"] = self.tts_speaker_wav  # optional voice cloning

            self.tts_model.tts_to_file(
                text=text,
                file_path=output_path,
                **kwargs
            )

            self._optimize_audio_file(output_path)

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            self._create_silent_audio(output_path)


    def _clean_arabic_text(self, text: str) -> str:
        """Clean Arabic text for better TTS"""
        import re
        import arabic_reshaper
        from bidi.algorithm import get_display
        
        try:
            # Remove excessive punctuation
            text = re.sub(r'[.]{2,}', '.', text)
            text = re.sub(r'[!]{2,}', '!', text)
            text = re.sub(r'[?]{2,}', '?', text)
            
            # Handle Arabic text shaping
            reshaped_text = arabic_reshaper.reshape(text)
            display_text = get_display(reshaped_text)
            
            return display_text
            
        except Exception as e:
            logger.warning(f"Text cleaning error: {e}")
            return text

    def _optimize_audio_file(self, file_path: str):
        """Optimize audio file for web delivery"""
        try:
            # Load audio
            audio = AudioSegment.from_wav(file_path)
            
            # Normalize audio
            audio = audio.normalize()
            
            # Set optimal parameters for speech
            audio = audio.set_frame_rate(22050)  # Good quality, smaller size
            audio = audio.set_channels(1)        # Mono
            
            # Apply gentle compression
            audio = audio.compress_dynamic_range(threshold=-20.0, ratio=4.0)
            
            # Export optimized version
            audio.export(file_path, format="wav", parameters=["-ac", "1", "-ar", "22050"])
            
        except Exception as e:
            logger.warning(f"Audio optimization failed: {e}")

    def _create_silent_audio(self, output_path: str, duration_ms: int = 1000):
        """Create silent audio as fallback"""
        try:
            silent_audio = AudioSegment.silent(duration=duration_ms)
            silent_audio.export(output_path, format="wav")
            
        except Exception as e:
            logger.error(f"Failed to create silent audio: {e}")

    async def detect_emotion_from_audio(self, audio_data: bytes) -> Dict[str, Any]:
        """Detect emotional state from audio (basic implementation)"""
        try:
            # This is a simplified emotion detection
            # In production, you'd use specialized models
            
            # Convert audio to analyze
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Load audio for analysis
                audio, sr = sf.read(temp_file_path)
                
                # Basic audio features
                energy = np.mean(audio ** 2)
                zero_crossing_rate = np.mean(np.diff(np.signbit(audio), prepend=0))
                
                # Simple emotion classification based on audio features
                if energy > 0.01 and zero_crossing_rate > 0.1:
                    emotion = "stressed"
                    confidence = min(0.8, energy * 50)
                elif energy < 0.001:
                    emotion = "calm"
                    confidence = 0.7
                else:
                    emotion = "neutral"
                    confidence = 0.6
                
                return {
                    "emotion": emotion,
                    "confidence": confidence,
                    "features": {
                        "energy": float(energy),
                        "zero_crossing_rate": float(zero_crossing_rate)
                    }
                }
                
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"Emotion detection error: {e}")
            return {
                "emotion": "neutral",
                "confidence": 0.5,
                "features": {}
            }

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self.ready and self.whisper_model is not None and self.tts_model is not None

    async def health_check(self) -> Dict[str, Any]:
        """Health check for the service"""
        return {
            "status": "healthy" if self.ready else "unhealthy",
            "whisper_model": self.model_size,
            "tts_model": self.tts_model_name,
            "device": self.device,
            "models_loaded": {
                "whisper": self.whisper_model is not None,
                "tts": self.tts_model is not None
            }
        }

    async def get_supported_languages(self) -> list:
        """Get supported languages"""
        return [
            {"code": "ar", "name": "Arabic", "dialect": "Omani"},
            {"code": "en", "name": "English", "dialect": "Mixed"}
        ]

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'whisper_model'):
                del self.whisper_model
            if hasattr(self, 'tts_model'):
                del self.tts_model
            
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            self.ready = False
            logger.info("Speech Service cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def _normalize_tts_model_name(self, name: str) -> str:
        # Coqui expects a full model ID; a bare 'ar' is invalid.
        if name.lower() in {"ar", "arabic"}:
            logger.warning("TTS_MODEL was set to a language code ('%s'); "
                        "falling back to XTTS v2.", name)
            return "tts_models/multilingual/multi-dataset/xtts_v2"
        return name
    

# Alternative TTS models for different scenarios
ALTERNATIVE_TTS_MODELS = {
    "fast": "tts_models/ar/common_voice/glow-tts",  # Faster but lower quality
    "quality": "tts_models/ar/common_voice/tacotron2-DDC",  # Better quality
    "multilingual": "tts_models/multilingual/multi-dataset/xtts_v2"  # Supports multiple languages
}