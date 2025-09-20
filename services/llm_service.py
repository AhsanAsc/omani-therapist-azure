"""
LLM Service - Free Implementation using Ollama
Handles therapeutic conversation generation in Omani Arabic
"""

import os
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
import httpx

from utils.prompts import TherapeuticPrompts
from utils.cultural_utils import OmaniCulturalContext

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.model_name = os.getenv("LLM_MODEL", "llama3.1:8b")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.client = None
        self.ready = False
        self.prompts = TherapeuticPrompts()
        self.cultural_context = OmaniCulturalContext()
        self.response_cache = {}
        self.max_cache_size = 100


    async def initialize(self):
        """Initialize LLM service"""
        try:
            logger.info("Initializing LLM Service...")
            
            # Create HTTP client
            self.client = httpx.AsyncClient(timeout=60.0)
            
            # Test Ollama connection
            await self._test_connection()
            
            # Ensure model is available
            await self._ensure_model_available()
            
            self.ready = True
            logger.info("LLM Service initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM Service: {e}")
            raise

    async def _test_connection(self):
        """Test connection to Ollama"""
        try:
            response = await self.client.get(f"{self.ollama_url}/api/tags")
            if response.status_code != 200:
                raise Exception(f"Ollama not responding: {response.status_code}")
            logger.info("Ollama connection successful")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            raise

    async def _ensure_model_available(self):
        """Ensure the required model is available"""
        try:
            # Check if model exists
            response = await self.client.get(f"{self.ollama_url}/api/tags")
            models = response.json()
            
            model_exists = any(
                model["name"] == self.model_name 
                for model in models.get("models", [])
            )
            
            if not model_exists:
                logger.info(f"Model {self.model_name} not found. Pulling...")
                await self._pull_model()
            else:
                logger.info(f"Model {self.model_name} is available")
                
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            raise

    async def _pull_model(self):
        """Pull model from Ollama"""
        try:
            pull_data = {"name": self.model_name}
            
            async with self.client.stream(
                "POST",
                f"{self.ollama_url}/api/pull",
                json=pull_data
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "status" in data:
                            logger.info(f"Pull status: {data['status']}")
                        if data.get("status") == "success":
                            break
            
            logger.info(f"Successfully pulled model {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            raise

    async def generate_therapeutic_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        user_context: Dict[str, Any],
        emotional_state: str = "neutral"
    ) -> Dict[str, Any]:
        """Generate therapeutic response"""
        if not self.ready:
            raise RuntimeError("LLM service not initialized")
        
        try:
            # Build therapeutic prompt
            system_prompt = self.prompts.get_therapeutic_system_prompt(
                emotional_state=emotional_state,
                cultural_context=self.cultural_context.get_context_for_user(user_context)
            )
            
            # Build conversation context
            conversation_prompt = self._build_conversation_prompt(
                user_message,
                conversation_history,
                user_context
            )
            
            # Generate response
            response = await self._call_ollama(
                system_prompt=system_prompt,
                user_prompt=conversation_prompt,
                temperature=0.7,
                max_tokens=300
            )
            
            # Post-process response
            processed_response = self._post_process_response(
                response,
                user_message,
                emotional_state
            )
            
            return processed_response
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return self._get_fallback_response(emotional_state)

    async def _call_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 300
    ) -> str:
        """Call Ollama API"""
        try:
            prompt = f"{system_prompt}\n\nUser: {user_prompt}\nTherapist:"
            
            generate_data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                    "top_k": 40,
                    "repeat_penalty": 1.1
                }
            }
            
            response = await self.client.post(
                f"{self.ollama_url}/api/generate",
                json=generate_data
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            result = response.json()
            return result.get("response", "").strip()
            
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise

    def _build_conversation_prompt(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        context: Dict[str, Any]
    ) -> str:
        """Build conversation prompt with context"""
        
        # Add recent conversation history (last 5 exchanges)
        history_text = ""
        for exchange in history[-5:]:
            history_text += f"User: {exchange.get('user', '')}\n"
            history_text += f"Therapist: {exchange.get('bot', '')}\n\n"
        
        # Add cultural context
        cultural_notes = self.cultural_context.get_relevant_context(user_message)
        
        prompt = f"""
Previous conversation:
{history_text}

Cultural context: {cultural_notes}

Current user message: {user_message}

Please respond as a culturally sensitive Omani Arabic therapist.
"""
        
        return prompt

    def _post_process_response(
        self,
        response: str,
        user_message: str,
        emotional_state: str
    ) -> Dict[str, Any]:
        """Post-process the generated response"""
        
        # Clean up response
        cleaned_response = self._clean_response_text(response)
        
        # Analyze emotional tone
        detected_emotion = self._analyze_response_emotion(cleaned_response)
        
        # Add therapeutic techniques used
        techniques = self._identify_therapeutic_techniques(cleaned_response)
        
        return {
            "text": cleaned_response,
            "emotional_state": detected_emotion,
            "techniques_used": techniques,
            "confidence": 0.8,
            "cultural_appropriateness": self._check_cultural_appropriateness(cleaned_response)
        }

    def _clean_response_text(self, text: str) -> str:
        """Clean and format response text"""
        
        # Remove model artifacts
        text = text.replace("Therapist:", "").strip()
        text = text.replace("User:", "").strip()
        
        # Ensure proper Arabic formatting
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('User:', 'Therapist:', 'AI:', 'Assistant:')):
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # Ensure response is in Arabic if possible
        if not self._contains_arabic(result) and len(result) > 10:
            # Fallback to Arabic
            result = "أفهم ما تشعر به. هل يمكنك أن تخبرني أكثر عن هذا الموضوع؟"
        
        return result

    def _contains_arabic(self, text: str) -> bool:
        """Check if text contains Arabic characters"""
        arabic_chars = set(range(0x0600, 0x06FF))
        return any(ord(char) in arabic_chars for char in text)

    def _analyze_response_emotion(self, response: str) -> str:
        """Analyze emotional tone of response"""
        
        # Simple keyword-based emotion detection
        empathy_words = ["أفهم", "أشعر", "أقدر", "طبيعي", "مشاعرك"]
        supportive_words = ["سأساعدك", "معاً", "تستطيع", "قادر", "قوي"]
        calming_words = ["هادئ", "استرخي", "تنفس", "اطمئن", "بخير"]
        
        if any(word in response for word in empathy_words):
            return "empathetic"
        elif any(word in response for word in supportive_words):
            return "supportive"
        elif any(word in response for word in calming_words):
            return "calming"
        else:
            return "neutral"

    def _identify_therapeutic_techniques(self, response: str) -> List[str]:
        """Identify therapeutic techniques used in response"""
        
        techniques = []
        
        # CBT indicators
        if any(word in response for word in ["أفكار", "معتقد", "تفكر", "رأيك"]):
            techniques.append("cognitive_restructuring")
        
        # Active listening
        if any(word in response for word in ["أفهم", "تقصد", "أسمعك", "واضح"]):
            techniques.append("active_listening")
        
        # Emotional validation
        if any(word in response for word in ["طبيعي", "مقبول", "مفهوم", "حقك"]):
            techniques.append("emotional_validation")
        
        # Solution-focused
        if any(word in response for word in ["خطوات", "خطة", "هدف", "تحقق"]):
            techniques.append("solution_focused")
        
        return techniques

    def _check_cultural_appropriateness(self, response: str) -> float:
        """Check cultural appropriateness score"""
        
        # Check for Islamic/cultural sensitivity
        score = 1.0
        
        # Positive indicators
        cultural_positive = ["إن شاء الله", "بإذن الله", "الحمد لله", "أهل", "عائلة"]
        if any(phrase in response for phrase in cultural_positive):
            score += 0.1
        
        # Negative indicators (Western-centric advice)
        cultural_negative = ["individual", "personal choice", "yourself first"]
        if any(phrase in response.lower() for phrase in cultural_negative):
            score -= 0.2
        
        return max(0.0, min(1.0, score))

    def _get_fallback_response(self, emotional_state: str) -> Dict[str, Any]:
        """Get fallback response when generation fails"""
        
        fallback_responses = {
            "stressed": "أفهم أنك تشعر بالضغط. هل يمكننا أن نتحدث عن مصدر هذا الشعور؟",
            "sad": "أرى أنك تمر بوقت صعب. أنا هنا للاستماع إليك.",
            "anxious": "القلق شعور طبيعي. دعنا نتحدث عن ما يقلقك.",
            "angry": "أفهم غضبك. هل تريد أن تخبرني عما يضايقك؟",
            "neutral": "أنا هنا للاستماع إليك. ماذا تود أن نتحدث عنه؟"
        }
        
        return {
            "text": fallback_responses.get(emotional_state, fallback_responses["neutral"]),
            "emotional_state": "supportive",
            "techniques_used": ["active_listening"],
            "confidence": 0.6,
            "cultural_appropriateness": 0.8
        }

    async def analyze_crisis_indicators(self, text: str) -> Dict[str, Any]:
        """Analyze text for crisis indicators"""
        
        if not self.ready:
            return {"crisis_level": 0, "indicators": []}
        
        try:
            system_prompt = self.prompts.get_crisis_analysis_prompt()
            user_prompt = f"Analyze this message for crisis indicators: {text}"
            
            response = await self._call_ollama(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=100
            )
            
            # Parse crisis analysis
            crisis_level = self._extract_crisis_level(response)
            indicators = self._extract_crisis_indicators(text)
            
            return {
                "crisis_level": crisis_level,
                "indicators": indicators,
                "analysis": response
            }
            
        except Exception as e:
            logger.error(f"Crisis analysis error: {e}")
            # Fallback to keyword-based detection
            return self._fallback_crisis_detection(text)

    def _extract_crisis_level(self, analysis: str) -> int:
        """Extract crisis level from analysis"""
        
        import re
        numbers = re.findall(r'\d+', analysis)
        
        if numbers:
            try:
                level = int(numbers[0])
                return max(0, min(10, level))
            except:
                pass
        
        # Keyword-based fallback
        if "high" in analysis.lower() or "urgent" in analysis.lower():
            return 8
        elif "medium" in analysis.lower() or "moderate" in analysis.lower():
            return 5
        elif "low" in analysis.lower():
            return 2
        
        return 0

    def _extract_crisis_indicators(self, text: str) -> List[str]:
        """Extract crisis indicators from text"""
        
        indicators = []
        
        # Arabic crisis keywords
        crisis_keywords = {
            "suicide": ["انتحار", "أقتل نفسي", "لا أريد العيش", "أموت"],
            "self_harm": ["أؤذي نفسي", "أجرح نفسي", "أضرب نفسي"],
            "hopelessness": ["لا أمل", "ميؤوس", "انتهيت", "فقدت الأمل"],
            "substance_abuse": ["مخدرات", "شرب", "كحول", "إدمان"]
        }
        
        text_lower = text.lower()
        
        for category, keywords in crisis_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                indicators.append(category)
        
        return indicators

    def _fallback_crisis_detection(self, text: str) -> Dict[str, Any]:
        """Fallback crisis detection using keywords"""
        
        crisis_keywords = [
            "انتحار", "أقتل نفسي", "لا أريد العيش", "أموت",
            "أؤذي نفسي", "لا أمل", "انتهيت", "فقدت الأمل"
        ]
        
        text_lower = text.lower()
        found_keywords = [kw for kw in crisis_keywords if kw in text_lower]
        
        crisis_level = min(9, len(found_keywords) * 3)
        
        return {
            "crisis_level": crisis_level,
            "indicators": found_keywords,
            "analysis": "Keyword-based detection"
        }

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self.ready

    async def health_check(self) -> Dict[str, Any]:
        """Health check for the service"""
        try:
            # Test a simple generation
            test_response = await self._call_ollama(
                system_prompt="You are a helpful assistant.",
                user_prompt="Hello",
                max_tokens=10
            )
            
            return {
                "status": "healthy",
                "model": self.model_name,
                "ollama_url": self.ollama_url,
                "test_response": bool(test_response)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": self.model_name
            }

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.client:
                await self.client.aclose()
            self.ready = False
            logger.info("LLM Service cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
