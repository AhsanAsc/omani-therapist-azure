"""
Therapy Service - Core therapeutic conversation management
Handles session management, therapeutic techniques, and conversation flow
"""

import logging
import asyncio
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional

from services.llm_service import LLMService
from utils.database import DatabaseManager
from utils.cultural_utils import OmaniCulturalContext
from utils.prompts import TherapeuticPrompts

logger = logging.getLogger(__name__)

class TherapyService:
    def __init__(self, llm_service: LLMService, db_manager: DatabaseManager):
        self.llm_service = llm_service
        self.db_manager = db_manager
        self.cultural_context = OmaniCulturalContext()
        self.prompts = TherapeuticPrompts()
        
        # Session tracking
        self.active_sessions = {}
        
        # Therapeutic techniques
        self.techniques = {
            "active_listening": self._apply_active_listening,
            "cognitive_restructuring": self._apply_cognitive_restructuring,
            "emotional_validation": self._apply_emotional_validation,
            "solution_focused": self._apply_solution_focused,
            "islamic_coping": self._apply_islamic_coping
        }

    async def generate_response(
        self,
        user_message: str,
        session_id: str,
        session_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate therapeutic response to user message"""
        
        try:
            # Update session context
            await self._update_session_context(session_id, user_message, session_context)
            
            # Analyze user message
            analysis = await self._analyze_user_message(user_message, session_context)
            
            # Determine appropriate therapeutic approach
            approach = await self._select_therapeutic_approach(analysis, session_context)
            
            # Generate contextual response
            response = await self._generate_contextual_response(
                user_message,
                analysis,
                approach,
                session_context
            )
            
            # Apply therapeutic techniques
            enhanced_response = await self._apply_therapeutic_techniques(
                response,
                analysis,
                approach
            )
            
            # Log session data
            await self._log_session_interaction(session_id, user_message, enhanced_response)
            
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Error generating therapy response: {e}")
            return await self._get_fallback_response(session_context.get("emotional_state", "neutral"))

    async def _update_session_context(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any]
    ):
        """Update session context with new information"""
        
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                "start_time": datetime.now(),
                "message_count": 0,
                "topics_discussed": [],
                "emotional_progression": [],
                "techniques_used": [],
                "cultural_context": {},
                "crisis_indicators": []
            }
        
        session = self.active_sessions[session_id]
        session["message_count"] += 1
        session["last_activity"] = datetime.now()
        
        # Update emotional progression
        current_emotion = context.get("emotional_state", "neutral")
        session["emotional_progression"].append({
            "timestamp": datetime.now(),
            "emotion": current_emotion,
            "intensity": self._estimate_emotional_intensity(message)
        })
        
        # Extract and update topics
        topics = await self._extract_topics(message)
        session["topics_discussed"].extend(topics)
        session["topics_discussed"] = list(set(session["topics_discussed"]))  # Remove duplicates
        
        # Update cultural context
        cultural_info = self.cultural_context.get_relevant_context(message)
        if cultural_info:
            session["cultural_context"]["current"] = cultural_info

    async def _analyze_user_message(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze user message for therapeutic insights"""
        
        analysis = {
            "emotional_state": await self._detect_emotional_state(message),
            "crisis_level": await self._assess_crisis_level(message, context),
            "therapeutic_needs": await self._identify_therapeutic_needs(message),
            "cultural_sensitivity": await self._assess_cultural_sensitivity_needs(message),
            "communication_style": await self._analyze_communication_style(message),
            "topic_areas": await self._extract_topics(message)
        }
        
        return analysis

    async def _detect_emotional_state(self, message: str) -> Dict[str, Any]:
        """Detect emotional state from message content"""
        
        # Arabic emotion keywords
        emotion_indicators = {
            "sad": ["حزين", "مكتئب", "يائس", "بائس", "محبط", "منكسر"],
            "anxious": ["قلق", "خائف", "متوتر", "مهموم", "مضطرب", "قلقان"],
            "angry": ["غاضب", "زعلان", "مستاء", "محتقن", "معصب", "مغتاظ"],
            "stressed": ["مضغوط", "متعب", "منهك", "مرهق", "تحت ضغط"],
            "hopeful": ["متفائل", "أمل", "واثق", "إيجابي", "مبسوط", "سعيد"],
            "confused": ["محتار", "مشوش", "لا أعرف", "ما أدري", "غير متأكد"],
            "grateful": ["شاكر", "ممتن", "الحمد لله", "مقدر", "راضي"]
        }
        
        message_lower = message.lower()
        detected_emotions = {}
        
        for emotion, keywords in emotion_indicators.items():
            count = sum(1 for keyword in keywords if keyword in message_lower)
            if count > 0:
                detected_emotions[emotion] = count / len(keywords)
        
        # Determine primary emotion
        if detected_emotions:
            primary_emotion = max(detected_emotions, key=detected_emotions.get)
            confidence = detected_emotions[primary_emotion]
        else:
            primary_emotion = "neutral"
            confidence = 0.5
        
        return {
            "primary": primary_emotion,
            "confidence": confidence,
            "all_detected": detected_emotions
        }

    async def _assess_crisis_level(self, message: str, context: Dict[str, Any]) -> int:
        """Assess crisis level (0-10 scale)"""
        
        # Use LLM for detailed crisis analysis
        crisis_analysis = await self.llm_service.analyze_crisis_indicators(message)
        
        base_level = crisis_analysis.get("crisis_level", 0)
        
        # Adjust based on context
        session_history = context.get("conversation_history", [])
        if len(session_history) > 3:
            # Check for escalating crisis indicators
            recent_messages = [msg.get("user", "") for msg in session_history[-3:]]
            recent_text = " ".join(recent_messages)
            
            escalation_indicators = ["أسوأ", "لا أستطيع", "انتهيت", "لا يمكن"]
            escalation_count = sum(1 for indicator in escalation_indicators if indicator in recent_text)
            
            if escalation_count > 1:
                base_level += 2
        
        return min(10, max(0, base_level))

    async def _identify_therapeutic_needs(self, message: str) -> List[str]:
        """Identify what therapeutic techniques might be helpful"""
        
        needs = []
        message_lower = message.lower()
        
        # Cognitive restructuring indicators
        cognitive_patterns = [
            "دائماً", "أبداً", "كل شيء", "لا شيء", "الأسوأ", "مستحيل"
        ]
        if any(pattern in message_lower for pattern in cognitive_patterns):
            needs.append("cognitive_restructuring")
        
        # Emotional validation indicators
        validation_needs = [
            "لا أحد يفهم", "وحيد", "مختلف", "غريب", "خطأ"
        ]
        if any(need in message_lower for need in validation_needs):
            needs.append("emotional_validation")
        
        # Solution-focused indicators
        solution_indicators = [
            "كيف", "ماذا أفعل", "أريد أن", "أحتاج", "ساعدني"
        ]
        if any(indicator in message_lower for indicator in solution_indicators):
            needs.append("solution_focused")
        
        # Islamic coping indicators
        religious_indicators = [
            "الله", "دعاء", "صلاة", "قدر", "ابتلاء", "أجر"
        ]
        if any(indicator in message_lower for indicator in religious_indicators):
            needs.append("islamic_coping")
        
        # Always include active listening
        needs.append("active_listening")
        
        return needs

    async def _assess_cultural_sensitivity_needs(self, message: str) -> Dict[str, Any]:
        """Assess what cultural considerations are needed"""
        
        cultural_needs = {
            "family_context": False,
            "religious_context": False,
            "gender_sensitivity": False,
            "honor_dignity": False,
            "social_pressure": False
        }
        
        message_lower = message.lower()
        
        # Family context
        family_terms = ["أهل", "عائلة", "والدي", "والدتي", "أخ", "أخت", "زوج"]
        if any(term in message_lower for term in family_terms):
            cultural_needs["family_context"] = True
        
        # Religious context
        religious_terms = ["الله", "دين", "حرام", "حلال", "مسجد", "صلاة"]
        if any(term in message_lower for term in religious_terms):
            cultural_needs["religious_context"] = True
        
        # Social pressure indicators
        pressure_terms = ["الناس", "المجتمع", "العيب", "الشرف", "السمعة"]
        if any(term in message_lower for term in pressure_terms):
            cultural_needs["social_pressure"] = True
            cultural_needs["honor_dignity"] = True
        
        return cultural_needs

    async def _analyze_communication_style(self, message: str) -> Dict[str, Any]:
        """Analyze user's communication style"""
        
        style = {
            "directness": "medium",
            "emotional_openness": "medium", 
            "formality": "medium",
            "detail_level": "medium"
        }
        
        # Analyze directness
        if any(word in message for word in ["مباشرة", "صراحة", "بوضوح"]):
            style["directness"] = "high"
        elif len(message.split()) > 50:  # Long, descriptive message
            style["directness"] = "low"
        
        # Analyze emotional openness
        emotion_words = ["أشعر", "أحس", "قلبي", "مشاعر", "أحزن", "أفرح"]
        if sum(1 for word in emotion_words if word in message) > 2:
            style["emotional_openness"] = "high"
        
        # Analyze formality
        formal_indicators = ["حضرتك", "سيادتك", "تفضل", "من فضلك"]
        if any(indicator in message for indicator in formal_indicators):
            style["formality"] = "high"
        elif any(word in message for word in ["يلا", "طيب", "ماشي"]):
            style["formality"] = "low"
        
        return style

    async def _extract_topics(self, message: str) -> List[str]:
        """Extract main topics from message"""
        
        topics = []
        message_lower = message.lower()
        
        topic_keywords = {
            "family": ["أهل", "عائلة", "والد", "والدة", "أخ", "أخت", "زوج", "أطفال"],
            "work": ["عمل", "وظيفة", "مدير", "زملاء", "راتب", "شركة"],
            "health": ["صحة", "مرض", "طبيب", "علاج", "دواء", "مستشفى"],
            "relationships": ["صديق", "حبيب", "علاقة", "زواج", "طلاق"],
            "money": ["مال", "فلوس", "دين", "قرض", "راتب", "غالي"],
            "education": ["دراسة", "جامعة", "مدرسة", "امتحان", "شهادة"],
            "religion": ["دين", "الله", "صلاة", "مسجد", "قرآن", "حج"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                topics.append(topic)
        
        return topics

    async def _select_therapeutic_approach(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Select most appropriate therapeutic approach"""
        
        crisis_level = analysis.get("crisis_level", 0)
        emotional_state = analysis.get("emotional_state", {}).get("primary", "neutral")
        needs = analysis.get("therapeutic_needs", [])
        
        # Crisis intervention takes priority
        if crisis_level > 7:
            return "crisis_intervention"
        
        # High emotional distress
        if emotional_state in ["sad", "anxious", "angry"] and analysis["emotional_state"]["confidence"] > 0.7:
            if "emotional_validation" in needs:
                return "validation_and_support"
            else:
                return "emotional_regulation"
        
        # Problem-solving focus
        if "solution_focused" in needs:
            return "solution_focused_therapy"
        
        # Cognitive issues
        if "cognitive_restructuring" in needs:
            return "cognitive_behavioral"
        
        # Religious/spiritual support
        if "islamic_coping" in needs:
            return "islamic_counseling"
        
        # Default: supportive listening
        return "supportive_listening"

    async def _generate_contextual_response(
        self,
        message: str,
        analysis: Dict[str, Any],
        approach: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate contextual therapeutic response"""
        
        # Build conversation history
        history = context.get("conversation_history", [])
        
        # Get cultural context
        cultural_context = self.cultural_context.get_context_for_user({
            "emotional_state": analysis["emotional_state"]["primary"],
            "topics": analysis["topic_areas"]
        })
        
        # Generate response using LLM
        response = await self.llm_service.generate_therapeutic_response(
            user_message=message,
            conversation_history=history,
            user_context={
                "emotional_state": analysis["emotional_state"]["primary"],
                "crisis_level": analysis["crisis_level"],
                "approach": approach,
                "cultural_needs": analysis["cultural_sensitivity"]
            },
            emotional_state=analysis["emotional_state"]["primary"]
        )
        
        return response

    async def _apply_therapeutic_techniques(
        self,
        response: Dict[str, Any],
        analysis: Dict[str, Any],
        approach: str
    ) -> Dict[str, Any]:
        """Apply specific therapeutic techniques to enhance response"""
        
        enhanced_response = response.copy()
        techniques_applied = []
        
        # Apply relevant techniques based on needs
        needs = analysis.get("therapeutic_needs", [])
        
        for need in needs:
            if need in self.techniques:
                try:
                    enhanced_text = await self.techniques[need](
                        enhanced_response["text"],
                        analysis,
                        approach
                    )
                    enhanced_response["text"] = enhanced_text
                    techniques_applied.append(need)
                except Exception as e:
                    logger.warning(f"Failed to apply technique {need}: {e}")
        
        enhanced_response["techniques_used"] = techniques_applied
        enhanced_response["approach"] = approach
        
        return enhanced_response

    # Therapeutic technique implementations
    async def _apply_active_listening(
        self,
        response_text: str,
        analysis: Dict[str, Any],
        approach: str
    ) -> str:
        """Apply active listening techniques"""
        
        listening_phrases = self.prompts.get_active_listening_responses()
        
        # Add reflection or summary if appropriate
        if len(response_text.split()) < 10:  # Short response
            reflection = np.random.choice(listening_phrases)
            response_text = f"{reflection} {response_text}"
        
        return response_text

    async def _apply_cognitive_restructuring(
        self,
        response_text: str,
        analysis: Dict[str, Any],
        approach: str
    ) -> str:
        """Apply cognitive restructuring techniques"""
        
        cbt_prompts = self.prompts.get_cbt_reframing_prompts()
        
        # Detect thinking patterns and add appropriate reframing
        if "دائماً" in response_text or "أبداً" in response_text:
            reframing = cbt_prompts.get("all_or_nothing", "")
            response_text += f"\n\n{reframing}"
        
        return response_text

    async def _apply_emotional_validation(
        self,
        response_text: str,
        analysis: Dict[str, Any],
        approach: str
    ) -> str:
        """Apply emotional validation techniques"""
        
        validation_phrases = self.prompts.get_validation_phrases()
        validation = np.random.choice(validation_phrases)
        
        # Add validation at the beginning
        response_text = f"{validation}. {response_text}"
        
        return response_text

    async def _apply_solution_focused(
        self,
        response_text: str,
        analysis: Dict[str, Any],
        approach: str
    ) -> str:
        """Apply solution-focused techniques"""
        
        # Add solution-oriented questions
        solution_questions = [
            "ما هي خطوة صغيرة يمكنك اتخاذها اليوم؟",
            "متى كان آخر مرة تعاملت فيها مع موقف مشابه بنجاح؟",
            "ما هي نقاط القوة التي يمكنك الاستعانة بها؟"
        ]
        
        if "كيف" in response_text or "ماذا" in response_text:
            question = np.random.choice(solution_questions)
            response_text += f"\n\n{question}"
        
        return response_text

    async def _apply_islamic_coping(
        self,
        response_text: str,
        analysis: Dict[str, Any],
        approach: str
    ) -> str:
        """Apply Islamic coping strategies"""
        
        emotional_state = analysis.get("emotional_state", {}).get("primary", "neutral")
        islamic_suggestion = self.cultural_context.get_islamic_coping_suggestion(emotional_state)
        
        # Add Islamic coping strategy
        response_text += f"\n\n{islamic_suggestion}"
        
        return response_text

    def _estimate_emotional_intensity(self, message: str) -> float:
        """Estimate emotional intensity from message"""
        
        # Count emotional indicators
        high_intensity = ["جداً", "كثيراً", "للغاية", "أقصى", "شديد"]
        medium_intensity = ["نوعاً ما", "قليلاً", "أحياناً"]
        
        high_count = sum(1 for word in high_intensity if word in message)
        medium_count = sum(1 for word in medium_intensity if word in message)
        
        if high_count > 0:
            return min(1.0, 0.7 + (high_count * 0.1))
        elif medium_count > 0:
            return 0.4 + (medium_count * 0.1)
        else:
            return 0.5

    async def _log_session_interaction(
        self,
        session_id: str,
        user_message: str,
        response: Dict[str, Any]
    ):
        """Log interaction for session tracking and analysis"""
        
        try:
            interaction_data = {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "user_message": user_message,
                "bot_response": response["text"],
                "emotional_state": response.get("emotional_state", "neutral"),
                "techniques_used": response.get("techniques_used", []),
                "approach": response.get("approach", "unknown"),
                "crisis_level": response.get("crisis_level", 0)
            }
            
            await self.db_manager.log_interaction(interaction_data)
            
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")

    async def _get_fallback_response(self, emotional_state: str) -> Dict[str, Any]:
        """Get fallback response when generation fails"""
        
        fallback_responses = {
            "sad": "أفهم أنك تمر بوقت صعب. أنا هنا معك.",
            "anxious": "أشعر بقلقك. دعنا نتحدث عن مصدر هذا القلق.",
            "angry": "أرى أن هناك شيئاً يضايقك. أريد أن أفهم ما يحدث.",
            "stressed": "يبدو أنك تحت ضغط. كيف يمكنني مساعدتك؟",
            "neutral": "أنا هنا للاستماع إليك. حدثني عما في بالك."
        }
        
        return {
            "text": fallback_responses.get(emotional_state, fallback_responses["neutral"]),
            "emotional_state": "supportive",
            "techniques_used": ["active_listening"],
            "confidence": 0.6,
            "approach": "supportive_listening"
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check for therapy service"""
        return {
            "status": "healthy",
            "active_sessions": len(self.active_sessions),
            "llm_ready": self.llm_service.is_ready(),
            "techniques_available": list(self.techniques.keys())
        }

    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of therapy session"""
        
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[session_id]
        
        return {
            "session_id": session_id,
            "duration": (datetime.now() - session["start_time"]).total_seconds(),
            "message_count": session["message_count"],
            "topics_discussed": session["topics_discussed"],
            "emotional_progression": session["emotional_progression"],
            "techniques_used": session["techniques_used"],
            "last_activity": session["last_activity"].isoformat()
        }

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """End therapy session and provide summary"""
        
        try:
            summary = await self.get_session_summary(session_id)
            
            # Save session to database
            await self.db_manager.save_session(session_id, summary)
            
            # Clean up active session
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            return {
                "status": "session_ended",
                "summary": summary,
                "closing_message": "شكراً لك على هذه الجلسة. أتمنى أن تكون مفيدة. في أمان الله."
            }
            
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {e}")
            return {"status": "error", "message": "خطأ في إنهاء الجلسة"}