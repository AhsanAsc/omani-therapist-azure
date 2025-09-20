"""
Safety Service - Crisis detection and intervention system
Handles crisis assessment, safety protocols, and emergency response
"""

import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from utils.database import DatabaseManager
from utils.prompts import TherapeuticPrompts

logger = logging.getLogger(__name__)

class SafetyService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.prompts = TherapeuticPrompts()
        
        # Crisis detection thresholds
        self.crisis_thresholds = {
            "low": 3,
            "medium": 5,
            "high": 7,
            "critical": 9
        }
        
        # Load crisis keywords and patterns
        self.crisis_keywords = self._load_crisis_keywords()
        self.emergency_resources = self._load_emergency_resources()
        
        # Session tracking for escalation detection
        self.session_crisis_history = {}

    def _load_crisis_keywords(self) -> Dict[str, List[str]]:
        """Load crisis detection keywords in Arabic"""
        return {
            "suicide": [
                "انتحار", "أقتل نفسي", "أنهي حياتي", "لا أريد العيش",
                "أموت", "أريد أن أموت", "ما عدت أريد العيش", "انتهيت",
                "سأنهي هذا", "أفضل أن أموت", "الموت أفضل", "لا فائدة"
            ],
            "self_harm": [
                "أؤذي نفسي", "أجرح نفسي", "أضرب نفسي", "أحرق نفسي",
                "أقطع نفسي", "أعذب نفسي", "أذية النفس", "جروح",
                "أستحق الألم", "أعاقب نفسي"
            ],
            "hopelessness": [
                "لا أمل", "ميؤوس", "فقدت الأمل", "لا فائدة",
                "مستحيل", "لن يتحسن", "انتهى الأمر", "لا معنى",
                "فارغ", "ضائع", "لا أستطيع", "عاجز"
            ],
            "isolation": [
                "وحيد", "لا أحد", "منعزل", "مهجور", "منسي",
                "لا أحد يهتم", "لا أحد يفهم", "بمفردي", "معزول"
            ],
            "substance_abuse": [
                "مخدرات", "كحول", "شرب", "إدمان", "مدمن",
                "حبوب", "مواد", "تعاطي", "سكران", "مخمور"
            ],
            "violence": [
                "أضرب", "أعتدي", "أؤذي الآخرين", "عنف", "قتل",
                "أقتل", "أهدد", "انتقام", "أدمر", "أحطم"
            ],
            "psychosis": [
                "أسمع أصوات", "أرى أشياء", "يتحدثون عني", "يراقبونني",
                "مؤامرة", "يتبعونني", "أفكار غريبة", "لست أنا"
            ]
        }

    def _load_emergency_resources(self) -> Dict[str, Any]:
        """Load emergency contact information for Oman"""
        return {
            "hotlines": [
                {
                    "name": "خط المساعدة النفسية - وزارة الصحة",
                    "number": "80077",
                    "description": "خدمة مجانية متاحة 24/7",
                    "language": "العربية"
                },
                {
                    "name": "الطوارئ العامة",
                    "number": "999",
                    "description": "للحالات الطارئة التي تهدد الحياة",
                    "language": "العربية والإنجليزية"
                },
                {
                    "name": "الهلال الأحمر العماني",
                    "number": "999",
                    "description": "خدمات الإسعاف والطوارئ الطبية",
                    "language": "العربية"
                }
            ],
            "hospitals": [
                {
                    "name": "مستشفى الجامعة",
                    "location": "مسقط",
                    "phone": "+968-24141414",
                    "services": ["طب نفسي", "طوارئ نفسية"],
                    "hours": "24/7"
                },
                {
                    "name": "مستشفى خولة",
                    "location": "مسقط",
                    "phone": "+968-24560300",
                    "services": ["طوارئ عامة", "طب نفسي"],
                    "hours": "24/7"
                },
                {
                    "name": "المستشفى الوطني",
                    "location": "مسقط",
                    "phone": "+968-24583600",
                    "services": ["طب نفسي", "علاج الإدمان"],
                    "hours": "متاح بالمواعيد"
                }
            ],
            "counseling_centers": [
                {
                    "name": "مركز الإرشاد النفسي - جامعة السلطان قابوس",
                    "phone": "+968-24141111",
                    "services": ["إرشاد نفسي", "استشارات أسرية"],
                    "target": "طلاب وأفراد المجتمع"
                },
                {
                    "name": "مراكز الرعاية الصحية الأولية",
                    "description": "متوفرة في جميع المحافظات",
                    "services": ["استشارات نفسية أولية", "تحويل للمتخصصين"]
                }
            ],
            "online_resources": [
                {
                    "name": "موقع وزارة الصحة العمانية",
                    "url": "https://www.moh.gov.om",
                    "description": "معلومات عن الخدمات النفسية"
                },
                {
                    "name": "تطبيق صحتك",
                    "description": "تطبيق وزارة الصحة للاستشارات الطبية"
                }
            ]
        }

    async def analyze_safety(self, message: str, session_id: str) -> Dict[str, Any]:
        """Comprehensive safety analysis of user message"""
        
        try:
            # Basic keyword-based analysis
            keyword_analysis = await self._analyze_crisis_keywords(message)
            
            # Pattern-based analysis
            pattern_analysis = await self._analyze_crisis_patterns(message)
            
            # Session context analysis
            context_analysis = await self._analyze_session_context(session_id, message)
            
            # Calculate overall crisis level
            crisis_level = await self._calculate_crisis_level(
                keyword_analysis,
                pattern_analysis,
                context_analysis
            )
            
            # Determine crisis type
            crisis_type = await self._determine_crisis_type(
                keyword_analysis,
                pattern_analysis
            )
            
            # Assess urgency
            urgency = await self._assess_urgency(crisis_level, crisis_type, context_analysis)
            
            # Update session tracking
            await self._update_session_crisis_tracking(session_id, crisis_level, crisis_type)
            
            safety_analysis = {
                "crisis_level": crisis_level,
                "crisis_type": crisis_type,
                "urgency": urgency,
                "indicators": {
                    "keywords": keyword_analysis,
                    "patterns": pattern_analysis,
                    "context": context_analysis
                },
                "recommendations": await self._get_safety_recommendations(crisis_level, urgency),
                "requires_intervention": crisis_level >= self.crisis_thresholds["high"],
                "requires_escalation": crisis_level >= self.crisis_thresholds["critical"]
            }
            
            # Log crisis event if significant
            if crisis_level >= self.crisis_thresholds["medium"]:
                await self._log_crisis_event(session_id, message, safety_analysis)
            
            return safety_analysis
            
        except Exception as e:
            logger.error(f"Safety analysis failed: {e}")
            # Return conservative high-risk assessment on error
            return {
                "crisis_level": 8,
                "crisis_type": "unknown",
                "urgency": "high",
                "error": str(e),
                "requires_intervention": True,
                "requires_escalation": False
            }

    async def _analyze_crisis_keywords(self, message: str) -> Dict[str, Any]:
        """Analyze message for crisis-related keywords"""
        
        message_lower = message.lower()
        keyword_matches = {}
        total_severity = 0
        
        for category, keywords in self.crisis_keywords.items():
            matches = []
            category_severity = 0
            
            for keyword in keywords:
                if keyword in message_lower:
                    matches.append(keyword)
                    # Weight different categories differently
                    if category == "suicide":
                        category_severity += 3
                    elif category == "self_harm":
                        category_severity += 2.5
                    elif category == "violence":
                        category_severity += 2.5
                    elif category == "psychosis":
                        category_severity += 2
                    else:
                        category_severity += 1
            
            if matches:
                keyword_matches[category] = {
                    "matches": matches,
                    "count": len(matches),
                    "severity": category_severity
                }
                total_severity += category_severity
        
        return {
            "matches": keyword_matches,
            "total_severity": min(10, total_severity),
            "high_risk_categories": [
                cat for cat, data in keyword_matches.items() 
                if cat in ["suicide", "self_harm", "violence"] and data["count"] > 0
            ]
        }

    async def _analyze_crisis_patterns(self, message: str) -> Dict[str, Any]:
        """Analyze message for crisis-indicating patterns"""
        
        patterns = {
            "finality_statements": 0,
            "goodbye_messages": 0,
            "past_tense_future": 0,
            "extreme_language": 0,
            "isolation_expressions": 0,
            "worthlessness": 0,
            "burden_statements": 0
        }
        
        message_lower = message.lower()
        
        # Finality statements
        finality_words = ["آخر مرة", "لن أعود", "انتهى الأمر", "لا رجعة", "نهاية"]
        patterns["finality_statements"] = sum(1 for word in finality_words if word in message_lower)
        
        # Goodbye messages
        goodbye_words = ["وداع", "مع السلامة إلى الأبد", "لن نلتقي", "اعتنوا بأنفسكم"]
        patterns["goodbye_messages"] = sum(1 for word in goodbye_words if word in message_lower)
        
        # Extreme language
        extreme_words = ["دائماً", "أبداً", "كل شيء", "لا شيء", "الأسوأ", "مستحيل"]
        patterns["extreme_language"] = sum(1 for word in extreme_words if word in message_lower)
        
        # Worthlessness
        worthless_words = ["لا قيمة لي", "عديم الفائدة", "فاشل", "لا أستحق", "عبء"]
        patterns["worthlessness"] = sum(1 for word in worthless_words if word in message_lower)
        
        # Calculate pattern severity
        pattern_severity = (
            patterns["finality_statements"] * 3 +
            patterns["goodbye_messages"] * 3 +
            patterns["past_tense_future"] * 2 +
            patterns["extreme_language"] * 1 +
            patterns["isolation_expressions"] * 2 +
            patterns["worthlessness"] * 2 +
            patterns["burden_statements"] * 2
        )
        
        return {
            "patterns": patterns,
            "severity": min(10, pattern_severity),
            "high_risk_patterns": [
                pattern for pattern, count in patterns.items()
                if count > 0 and pattern in ["finality_statements", "goodbye_messages", "burden_statements"]
            ]
        }

    async def _analyze_session_context(self, session_id: str, current_message: str) -> Dict[str, Any]:
        """Analyze session context for crisis escalation"""
        
        context = {
            "escalation_detected": False,
            "repeated_crisis_themes": 0,
            "emotional_deterioration": False,
            "previous_interventions": 0,
            "session_duration": 0
        }
        
        try:
            # Get session history
            history = await self.db_manager.get_session_history(session_id)
            
            if not history:
                return context
            
            # Check for escalation in recent messages
            recent_messages = history[-3:] if len(history) >= 3 else history
            crisis_indicators_count = 0
            
            for msg in recent_messages:
                user_msg = msg.get("user", "").lower()
                # Count crisis keywords in recent history
                for keywords in self.crisis_keywords.values():
                    crisis_indicators_count += sum(1 for kw in keywords if kw in user_msg)
            
            context["repeated_crisis_themes"] = crisis_indicators_count
            context["escalation_detected"] = crisis_indicators_count > 2
            
            # Check emotional deterioration
            emotions = [msg.get("emotional_state", "") for msg in history]
            negative_emotions = ["sad", "anxious", "hopeless", "angry"]
            recent_negative = sum(1 for emotion in emotions[-5:] if emotion in negative_emotions)
            context["emotional_deterioration"] = recent_negative >= 3
            
            # Check for previous interventions
            session_crisis_data = self.session_crisis_history.get(session_id, [])
            context["previous_interventions"] = len(session_crisis_data)
            
            return context
            
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            return context

    async def _calculate_crisis_level(
        self,
        keyword_analysis: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        context_analysis: Dict[str, Any]
    ) -> int:
        """Calculate overall crisis level (0-10)"""
        
        # Base score from keywords (weighted heavily)
        keyword_score = keyword_analysis.get("total_severity", 0) * 0.5
        
        # Pattern score
        pattern_score = pattern_analysis.get("severity", 0) * 0.3
        
        # Context adjustments
        context_score = 0
        if context_analysis.get("escalation_detected"):
            context_score += 2
        if context_analysis.get("emotional_deterioration"):
            context_score += 1
        if context_analysis.get("previous_interventions", 0) > 1:
            context_score += 1
        
        # High-risk category bonus
        high_risk_categories = keyword_analysis.get("high_risk_categories", [])
        if high_risk_categories:
            context_score += len(high_risk_categories) * 1.5
        
        # Calculate final score
        total_score = keyword_score + pattern_score + context_score
        
        # Ensure score is within bounds
        crisis_level = max(0, min(10, int(total_score)))
        
        return crisis_level

    async def _determine_crisis_type(
        self,
        keyword_analysis: Dict[str, Any],
        pattern_analysis: Dict[str, Any]
    ) -> str:
        """Determine primary type of crisis"""
        
        keyword_matches = keyword_analysis.get("matches", {})
        
        # Priority order for crisis types
        if "suicide" in keyword_matches:
            return "suicide_risk"
        elif "self_harm" in keyword_matches:
            return "self_harm_risk"
        elif "violence" in keyword_matches:
            return "violence_risk"
        elif "psychosis" in keyword_matches:
            return "mental_health_emergency"
        elif "substance_abuse" in keyword_matches:
            return "substance_abuse"
        elif "hopelessness" in keyword_matches:
            return "severe_depression"
        elif "isolation" in keyword_matches:
            return "social_crisis"
        else:
            # Check patterns
            high_risk_patterns = pattern_analysis.get("high_risk_patterns", [])
            if "finality_statements" in high_risk_patterns:
                return "suicide_risk"
            elif "goodbye_messages" in high_risk_patterns:
                return "suicide_risk"
            else:
                return "emotional_distress"

    async def _assess_urgency(
        self,
        crisis_level: int,
        crisis_type: str,
        context_analysis: Dict[str, Any]
    ) -> str:
        """Assess urgency level for intervention"""
        
        # Immediate urgency criteria
        if crisis_level >= 9:
            return "immediate"
        
        if crisis_type in ["suicide_risk", "violence_risk", "mental_health_emergency"]:
            if crisis_level >= 7:
                return "immediate"
            elif crisis_level >= 5:
                return "urgent"
        
        # Context-based urgency
        if context_analysis.get("escalation_detected") and crisis_level >= 6:
            return "urgent"
        
        # Standard urgency levels
        if crisis_level >= 7:
            return "urgent"
        elif crisis_level >= 5:
            return "moderate"
        elif crisis_level >= 3:
            return "low"
        else:
            return "none"

    async def _update_session_crisis_tracking(
        self,
        session_id: str,
        crisis_level: int,
        crisis_type: str
    ):
        """Update session-level crisis tracking"""
        
        if session_id not in self.session_crisis_history:
            self.session_crisis_history[session_id] = []
        
        self.session_crisis_history[session_id].append({
            "timestamp": datetime.now(),
            "crisis_level": crisis_level,
            "crisis_type": crisis_type
        })
        
        # Keep only recent history (last 10 events)
        if len(self.session_crisis_history[session_id]) > 10:
            self.session_crisis_history[session_id] = self.session_crisis_history[session_id][-10:]

    async def _log_crisis_event(
        self,
        session_id: str,
        user_message: str,
        safety_analysis: Dict[str, Any]
    ):
        """Log crisis event to database"""
        
        crisis_data = {
            "session_id": session_id,
            "timestamp": datetime.now(),
            "crisis_level": safety_analysis["crisis_level"],
            "crisis_type": safety_analysis["crisis_type"],
            "user_message": user_message,
            "intervention_response": "",  # Will be filled by intervention
            "escalated": safety_analysis.get("requires_escalation", False),
            "follow_up_needed": safety_analysis.get("requires_intervention", True)
        }
        
        await self.db_manager.log_crisis_event(crisis_data)

    async def _get_safety_recommendations(
        self,
        crisis_level: int,
        urgency: str
    ) -> List[str]:
        """Get safety recommendations based on crisis level"""
        
        recommendations = []
        
        if urgency == "immediate":
            recommendations.extend([
                "تدخل فوري مطلوب",
                "تحويل للطوارئ النفسية",
                "عدم ترك المستخدم وحيداً",
                "تفعيل بروتوكول الطوارئ"
            ])
        elif urgency == "urgent":
            recommendations.extend([
                "مراقبة مستمرة مطلوبة",
                "تحويل لمختص في أقرب وقت",
                "إشراك الأسرة إذا أمكن",
                "متابعة خلال 24 ساعة"
            ])
        elif urgency == "moderate":
            recommendations.extend([
                "تقييم دوري للحالة",
                "تعزيز شبكة الدعم",
                "جدولة متابعة خلال أسبوع",
                "توفير موارد المساعدة الذاتية"
            ])
        else:
            recommendations.extend([
                "مواصلة الدعم العاطفي",
                "مراقبة التطور",
                "تعزيز آليات التأقلم الصحية"
            ])
        
        return recommendations

    async def get_crisis_response(self, safety_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get appropriate crisis intervention response"""
        
        crisis_level = safety_analysis["crisis_level"]
        crisis_type = safety_analysis["crisis_type"]
        urgency = safety_analysis["urgency"]
        
        # Get base response from prompts
        crisis_responses = self.prompts.get_crisis_intervention_responses()
        
        if crisis_type == "suicide_risk":
            base_response = crisis_responses["suicide_ideation"]
        elif crisis_type == "self_harm_risk":
            base_response = crisis_responses["self_harm"]
        elif crisis_type == "substance_abuse":
            base_response = crisis_responses["substance_abuse"]
        else:
            # General crisis response
            base_response = """
أقدر شجاعتك في مشاركة هذه المشاعر الصعبة معي. 
أريدك أن تعلم أنك لست وحيداً، وأن هناك أشخاص يهتمون بك ويريدون مساعدتك.
هذه المشاعر التي تمر بها الآن قاسية، لكنها مؤقتة ويمكن التعامل معها.
"""
        
        # Add emergency resources if high risk
        emergency_resources = []
        emergency_contacts = []
        
        if crisis_level >= self.crisis_thresholds["high"]:
            emergency_resources = self.emergency_resources["hotlines"]
            emergency_contacts = [
                {
                    "name": "خط المساعدة النفسية",
                    "number": "80077",
                    "available": "24/7"
                },
                {
                    "name": "الطوارئ",
                    "number": "999", 
                    "available": "24/7"
                }
            ]
        
        # Islamic/cultural support elements
        cultural_support = self._get_cultural_crisis_support(crisis_type)
        
        return {
            "message": base_response + "\n\n" + cultural_support,
            "crisis_level": crisis_level,
            "urgency": urgency,
            "resources": emergency_resources,
            "emergency_contacts": emergency_contacts,
            "immediate_actions": self._get_immediate_actions(crisis_level, crisis_type),
            "follow_up_required": crisis_level >= self.crisis_thresholds["medium"]
        }

    def _get_cultural_crisis_support(self, crisis_type: str) -> str:
        """Get culturally appropriate crisis support message"""
        
        cultural_context = self.prompts.get_crisis_cultural_context()
        
        base_message = cultural_context["suicide_prevention"]["islamic_perspective"]
        
        if crisis_type == "suicide_risk":
            return f"""
{base_message}

تذكر أن:
• الله سبحانه وتعالى قال: "ولا تقتلوا أنفسكم إن الله كان بكم رحيماً"
• حياتك أمانة من الله، وأنت مسؤول عن المحافظة عليها
• مع العسر يسراً، وهذا وعد من الله
• أهلك وأصدقاؤك يحبونك ويحتاجونك

أرجوك تواصل مع:
• إمام المسجد أو شيخ تثق به
• أفراد أسرتك أو أصدقائك المقربين
• خط المساعدة النفسية: 80077
"""
        else:
            return f"""
{base_message}

الله سبحانه وتعالى يقول: "ومن أحياها فكأنما أحيا الناس جميعاً"
أنت تستحق الحياة والسعادة، وهناك أمل دائماً.

لا تتردد في طلب المساعدة من:
• الأسرة والأصدقاء
• المختصين في الصحة النفسية
• المجتمع الديني
"""

    def _get_immediate_actions(self, crisis_level: int, crisis_type: str) -> List[str]:
        """Get immediate actions based on crisis level"""
        
        actions = []
        
        if crisis_level >= 9:
            actions.extend([
                "الاتصال بالطوارئ (999) فوراً",
                "عدم ترك الشخص وحيداً",
                "إزالة أي وسائل يمكن استخدامها للإيذاء",
                "النقل للمستشفى إذا لزم الأمر"
            ])
        elif crisis_level >= 7:
            actions.extend([
                "الاتصال بخط المساعدة النفسية (80077)",
                "إشراك شخص موثوق (أسرة/صديق)",
                "ترتيب زيارة عاجلة لمختص",
                "المتابعة المستمرة لمدة 24-48 ساعة"
            ])
        elif crisis_level >= 5:
            actions.extend([
                "جدولة موعد مع مختص نفسي",
                "إعلام شخص موثوق بالوضع",
                "إزالة مسببات الضغط الفورية",
                "تطبيق تقنيات التهدئة الذاتية"
            ])
        else:
            actions.extend([
                "تعزيز شبكة الدعم الاجتماعي",
                "ممارسة أنشطة مهدئة",
                "المتابعة الدورية للحالة النفسية"
            ])
        
        return actions

    async def check_escalation_needed(
        self,
        session_id: str,
        current_crisis_level: int
    ) -> Dict[str, Any]:
        """Check if crisis escalation to human intervention is needed"""
        
        session_history = self.session_crisis_history.get(session_id, [])
        
        escalation_criteria = {
            "sustained_high_risk": False,
            "increasing_severity": False,
            "failed_interventions": False,
            "immediate_danger": False
        }
        
        # Check for sustained high risk
        recent_high_risk = [
            event for event in session_history[-5:]
            if event["crisis_level"] >= self.crisis_thresholds["high"]
        ]
        escalation_criteria["sustained_high_risk"] = len(recent_high_risk) >= 3
        
        # Check for increasing severity
        if len(session_history) >= 3:
            recent_levels = [event["crisis_level"] for event in session_history[-3:]]
            escalation_criteria["increasing_severity"] = (
                recent_levels[-1] > recent_levels[0] and 
                sum(recent_levels) > 18  # Average > 6
            )
        
        # Check for immediate danger
        escalation_criteria["immediate_danger"] = current_crisis_level >= 9
        
        # Check for failed interventions
        escalation_criteria["failed_interventions"] = len(session_history) > 2
        
        # Determine if escalation is needed
        escalation_needed = any([
            escalation_criteria["immediate_danger"],
            escalation_criteria["sustained_high_risk"] and escalation_criteria["increasing_severity"],
            escalation_criteria["failed_interventions"] and current_crisis_level >= 7
        ])
        
        return {
            "escalation_needed": escalation_needed,
            "criteria_met": escalation_criteria,
            "recommended_action": self._get_escalation_recommendation(escalation_criteria),
            "urgency": "immediate" if escalation_criteria["immediate_danger"] else "urgent"
        }

    def _get_escalation_recommendation(self, criteria: Dict[str, bool]) -> str:
        """Get escalation recommendation based on criteria"""
        
        if criteria["immediate_danger"]:
            return "تدخل طوارئ فوري - اتصل بـ 999"
        elif criteria["sustained_high_risk"]:
            return "تحويل عاجل لطبيب نفسي متخصص"
        elif criteria["increasing_severity"]:
            return "تقييم نفسي شامل مطلوب"
        elif criteria["failed_interventions"]:
            return "إشراف طبي مباشر مطلوب"
        else:
            return "مواصلة المراقبة والدعم"

    def health_check(self) -> Dict[str, Any]:
        """Health check for safety service"""
        return {
            "status": "healthy",
            "crisis_keywords_loaded": len(self.crisis_keywords),
            "emergency_resources_loaded": len(self.emergency_resources["hotlines"]),
            "active_session_tracking": len(self.session_crisis_history),
            "crisis_thresholds": self.crisis_thresholds
        }

    async def get_safety_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get safety and crisis statistics"""
        try:
            crisis_stats = await self.db_manager.get_crisis_statistics(days)
            
            return {
                "period": f"Last {days} days",
                "crisis_events": crisis_stats,
                "active_monitoring": len(self.session_crisis_history),
                "intervention_success_rate": self._calculate_intervention_success_rate(),
                "common_crisis_types": crisis_stats.get("crisis_types", {}),
                "escalation_rate": self._calculate_escalation_rate(crisis_stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to get safety statistics: {e}")
            return {"error": str(e)}

    def _calculate_intervention_success_rate(self) -> float:
        """Calculate success rate of interventions (placeholder)"""
        return 0.85

    def _calculate_escalation_rate(self, crisis_stats: Dict[str, Any]) -> float:
        """Calculate rate of crisis escalation"""
        total_events = crisis_stats.get("total_crisis_events", 0)
        escalated_events = crisis_stats.get("escalated_events", 0)
        
        if total_events == 0:
            return 0.0
        
        return escalated_events / total_events

    async def generate_safety_report(self, session_id: str) -> Dict[str, Any]:
        """Generate comprehensive safety report for a session"""
        try:
            session_data = await self.db_manager.export_session_data(session_id)
            session_crisis_data = self.session_crisis_history.get(session_id, [])
            
            if "error" in session_data:
                return session_data
            
            # Analyze session for safety patterns
            crisis_events = session_data.get("crisis_events", [])
            interactions = session_data.get("interactions", [])
            
            safety_summary = {
                "session_id": session_id,
                "total_crisis_events": len(crisis_events),
                "highest_crisis_level": max([event.get("crisis_level", 0) for event in crisis_events], default=0),
                "crisis_types_encountered": list(set([event.get("crisis_type", "") for event in crisis_events])),
                "interventions_applied": len([event for event in crisis_events if event.get("escalated", False)]),
                "emotional_progression": self._analyze_emotional_progression(interactions),
                "safety_recommendations": self._generate_session_safety_recommendations(crisis_events, interactions),
                "follow_up_required": len(crisis_events) > 0 or any(
                    event.get("crisis_level", 0) >= self.crisis_thresholds["medium"] 
                    for event in crisis_events
                )
            }
            
            return safety_summary
            
        except Exception as e:
            logger.error(f"Failed to generate safety report: {e}")
            return {"error": str(e)}

    def _analyze_emotional_progression(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze emotional progression throughout session"""
        if not interactions:
            return {"status": "no_data"}
        
        emotions = [interaction.get("emotional_state", "neutral") for interaction in interactions]
        
        # Count emotional states
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        # Detect trends
        negative_emotions = ["sad", "anxious", "angry", "hopeless"]
        positive_emotions = ["happy", "grateful", "hopeful", "calm"]
        
        recent_emotions = emotions[-5:] if len(emotions) >= 5 else emotions
        negative_trend = sum(1 for e in recent_emotions if e in negative_emotions)
        positive_trend = sum(1 for e in recent_emotions if e in positive_emotions)
        
        return {
            "emotion_distribution": emotion_counts,
            "trend_analysis": {
                "recent_negative": negative_trend,
                "recent_positive": positive_trend,
                "overall_trend": "improving" if positive_trend > negative_trend else "concerning" if negative_trend > positive_trend else "stable"
            },
            "dominant_emotion": max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"
        }

    def _generate_session_safety_recommendations(
        self, 
        crisis_events: List[Dict[str, Any]], 
        interactions: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate safety recommendations for completed session"""
        
        recommendations = []
        
        if not crisis_events:
            recommendations.append("الجلسة تمت بأمان دون أحداث أزمة")
            return recommendations
        
        max_crisis_level = max([event.get("crisis_level", 0) for event in crisis_events], default=0)
        
        if max_crisis_level >= 8:
            recommendations.extend([
                "متابعة عاجلة خلال 24 ساعة",
                "تأكيد سلامة المستخدم",
                "تفعيل شبكة الدعم الأسرية",
                "تقييم الحاجة للتدخل المهني"
            ])
        elif max_crisis_level >= 6:
            recommendations.extend([
                "متابعة خلال 48-72 ساعة",
                "مراجعة استراتيجيات التأقلم",
                "تقوية الموارد النفسية",
                "مراقبة علامات التحسن أو التدهور"
            ])
        else:
            recommendations.extend([
                "متابعة روتينية",
                "تعزيز النجاحات المحققة",
                "الاستمرار في بناء المهارات النفسية"
            ])
        
        return recommendations
