"""
Safety Monitoring Service
Detects concerning content, emergencies, and abuse indicators
Provides additional layer of protection beyond AI prompt guardrails
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class SafetyCategory(Enum):
    """Categories of safety concerns"""
    EMERGENCY_MEDICAL = "emergency_medical"
    SUICIDE_RISK = "suicide_risk"
    ABUSE_PHYSICAL = "abuse_physical"
    ABUSE_EMOTIONAL = "abuse_emotional"
    ABUSE_FINANCIAL = "abuse_financial"
    NEGLECT = "neglect"
    MEDICATION_ISSUE = "medication_issue"
    HARMFUL_ADVICE = "harmful_advice"
    SCAM_ATTEMPT = "scam_attempt"


class SafetyMonitor:
    """Monitors conversations for safety concerns"""

    def __init__(self):
        """Initialize safety monitoring patterns"""

        # Emergency medical keywords
        self.emergency_medical_patterns = [
            r"\b(chest pain|heart attack|can'?t breathe|difficulty breathing|stroke)\b",
            r"\b(severe bleeding|bleeding heavily|uncontrollable bleeding)\b",
            r"\b(fell and can'?t get up|broken bone|severe pain)\b",
            r"\b(face drooping|arm weakness|speech slurred)\b",
            r"\b(unconscious|passed out|blacked out)\b",
            r"\b(choking|can'?t swallow|throat closing)\b"
        ]

        # Suicide/self-harm keywords
        self.suicide_patterns = [
            r"\b(want to die|wish I was dead|kill myself|end my life|suicide)\b",
            r"\b(better off dead|no reason to live|life isn'?t worth living)\b",
            r"\b(hurt myself|harm myself|cut myself)\b",
            r"\b(made a plan to|wrote a note|saying goodbye)\b"
        ]

        # Physical abuse keywords
        self.abuse_physical_patterns = [
            r"\b(hit me|hits me|beat me|beats me|pushed me|shoved me)\b",
            r"\b(slapped|punched|kicked|hurt me physically)\b",
            r"\b(bruises|black eye|injured me|physically abusive)\b",
            r"\b(afraid of|scared of|terrified of)\b.*\b(him|her|them|caregiver)\b"
        ]

        # Emotional abuse keywords
        self.abuse_emotional_patterns = [
            r"\b(screams at me|yells at me|calls me names|insults me)\b",
            r"\b(threatens me|intimidates me|humiliates me)\b",
            r"\b(makes me feel worthless|tells me I'?m useless)\b",
            r"\b(isolates me|won'?t let me see|keeps me from)\b"
        ]

        # Financial exploitation keywords
        self.abuse_financial_patterns = [
            r"\b(taking my money|stole from me|forged my signature)\b",
            r"\b(won'?t give me my money|controls all my money)\b",
            r"\b(forced me to sign|tricked me into signing)\b",
            r"\b(emptied my account|unauthorized charges)\b"
        ]

        # Neglect keywords
        self.neglect_patterns = [
            r"\b(no food|nothing to eat|haven'?t eaten|starving)\b",
            r"\b(no medication|can'?t get medication|out of medication)\b",
            r"\b(dirty|unsanitary|no clean clothes|smell bad)\b",
            r"\b(alone all day|no one checks|abandoned me)\b"
        ]

        # Medication safety issues
        self.medication_patterns = [
            r"\b(took too many|double dose|wrong medication)\b",
            r"\b(ran out of|no refills|can'?t afford)\b",
            r"\b(bad reaction|side effects|allergic)\b",
            r"\b(mixing|combined with|took with alcohol)\b"
        ]

        # Compile all patterns
        self._compile_patterns()

        logger.info("Safety Monitor initialized with comprehensive pattern detection")

    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self.emergency_medical_regex = [re.compile(p, re.IGNORECASE) for p in self.emergency_medical_patterns]
        self.suicide_regex = [re.compile(p, re.IGNORECASE) for p in self.suicide_patterns]
        self.abuse_physical_regex = [re.compile(p, re.IGNORECASE) for p in self.abuse_physical_patterns]
        self.abuse_emotional_regex = [re.compile(p, re.IGNORECASE) for p in self.abuse_emotional_patterns]
        self.abuse_financial_regex = [re.compile(p, re.IGNORECASE) for p in self.abuse_financial_patterns]
        self.neglect_regex = [re.compile(p, re.IGNORECASE) for p in self.neglect_patterns]
        self.medication_regex = [re.compile(p, re.IGNORECASE) for p in self.medication_patterns]

    def analyze_message(self, message: str, role: str = "user") -> Dict:
        """
        Analyze a message for safety concerns

        Args:
            message: Message text to analyze
            role: 'user' or 'assistant'

        Returns:
            Dictionary with safety analysis results
        """
        result = {
            "alert_level": AlertLevel.NONE.value,
            "categories": [],
            "matched_patterns": [],
            "recommended_action": None,
            "message": message,
            "role": role,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Check for emergency medical situations
        for pattern in self.emergency_medical_regex:
            if pattern.search(message):
                result["alert_level"] = AlertLevel.EMERGENCY.value
                result["categories"].append(SafetyCategory.EMERGENCY_MEDICAL.value)
                result["matched_patterns"].append(pattern.pattern)
                result["recommended_action"] = "CALL 911 IMMEDIATELY - Medical emergency detected"

        # Check for suicide/self-harm
        for pattern in self.suicide_regex:
            if pattern.search(message):
                if result["alert_level"] != AlertLevel.EMERGENCY.value:
                    result["alert_level"] = AlertLevel.EMERGENCY.value
                result["categories"].append(SafetyCategory.SUICIDE_RISK.value)
                result["matched_patterns"].append(pattern.pattern)
                result["recommended_action"] = "MENTAL HEALTH CRISIS - Contact 988 Suicide & Crisis Lifeline"

        # Check for physical abuse
        for pattern in self.abuse_physical_regex:
            if pattern.search(message):
                if result["alert_level"] not in [AlertLevel.EMERGENCY.value]:
                    result["alert_level"] = AlertLevel.URGENT.value
                result["categories"].append(SafetyCategory.ABUSE_PHYSICAL.value)
                result["matched_patterns"].append(pattern.pattern)
                result["recommended_action"] = "ABUSE ALERT - Contact Adult Protective Services"

        # Check for emotional abuse
        for pattern in self.abuse_emotional_regex:
            if pattern.search(message):
                if result["alert_level"] == AlertLevel.NONE.value:
                    result["alert_level"] = AlertLevel.URGENT.value
                result["categories"].append(SafetyCategory.ABUSE_EMOTIONAL.value)
                result["matched_patterns"].append(pattern.pattern)
                result["recommended_action"] = "ABUSE ALERT - Contact Adult Protective Services"

        # Check for financial exploitation
        for pattern in self.abuse_financial_regex:
            if pattern.search(message):
                if result["alert_level"] == AlertLevel.NONE.value:
                    result["alert_level"] = AlertLevel.URGENT.value
                result["categories"].append(SafetyCategory.ABUSE_FINANCIAL.value)
                result["matched_patterns"].append(pattern.pattern)
                result["recommended_action"] = "FINANCIAL EXPLOITATION - Contact Adult Protective Services and local police"

        # Check for neglect
        for pattern in self.neglect_regex:
            if pattern.search(message):
                if result["alert_level"] == AlertLevel.NONE.value:
                    result["alert_level"] = AlertLevel.URGENT.value
                result["categories"].append(SafetyCategory.NEGLECT.value)
                result["matched_patterns"].append(pattern.pattern)
                result["recommended_action"] = "NEGLECT ALERT - Contact Adult Protective Services"

        # Check for medication issues
        for pattern in self.medication_regex:
            if pattern.search(message):
                if result["alert_level"] == AlertLevel.NONE.value:
                    result["alert_level"] = AlertLevel.WARNING.value
                result["categories"].append(SafetyCategory.MEDICATION_ISSUE.value)
                result["matched_patterns"].append(pattern.pattern)
                if result["recommended_action"] is None:
                    result["recommended_action"] = "MEDICATION CONCERN - Contact healthcare provider"

        # Check AI responses for harmful advice (if assistant message)
        if role == "assistant":
            harmful_advice_result = self._check_harmful_advice(message)
            if harmful_advice_result["contains_harmful_advice"]:
                result["alert_level"] = AlertLevel.URGENT.value
                result["categories"].append(SafetyCategory.HARMFUL_ADVICE.value)
                result["matched_patterns"].extend(harmful_advice_result["issues"])
                result["recommended_action"] = "HARMFUL ADVICE DETECTED - Review and block message"

        return result

    def _check_harmful_advice(self, message: str) -> Dict:
        """
        Check if AI response contains harmful advice

        Args:
            message: AI response to check

        Returns:
            Dictionary with harmful advice detection results
        """
        issues = []

        # Patterns that should NEVER appear in AI responses
        dangerous_patterns = [
            (r"\b(stop taking|don'?t take|skip).*(medication|medicine|pills)\b", "Advising to stop medication"),
            (r"\b(try|take|use).*(this medication|these pills)\b(?!.*doctor)", "Recommending medication"),
            (r"\b(invest|buy|purchase|donate).*(money|funds)\b", "Financial advice"),
            (r"\byou should (hurt|harm)\b", "Suggesting harm"),
            (r"\bkeep (this|it|that) (secret|between us|private)\b", "Asking to keep secrets"),
            (r"\b(don'?t tell|don'?t mention).*(doctor|family|caregiver)\b", "Discouraging disclosure"),
            (r"\b(you'?re|they'?re) (overreacting|imagining|being dramatic)\b", "Invalidating concerns"),
            (r"\bignore (the pain|symptoms|doctor)\b", "Advising to ignore medical issues")
        ]

        for pattern, issue_description in dangerous_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                issues.append(issue_description)

        return {
            "contains_harmful_advice": len(issues) > 0,
            "issues": issues
        }

    def analyze_conversation(self, messages: List[Dict]) -> Dict:
        """
        Analyze entire conversation for safety concerns

        Args:
            messages: List of message dictionaries with 'role' and 'content'

        Returns:
            Dictionary with conversation-level safety analysis
        """
        conversation_analysis = {
            "total_messages": len(messages),
            "alerts": [],
            "highest_alert_level": AlertLevel.NONE.value,
            "safety_categories": set(),
            "timestamp": datetime.utcnow().isoformat()
        }

        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            analysis = self.analyze_message(content, role)

            if analysis["alert_level"] != AlertLevel.NONE.value:
                conversation_analysis["alerts"].append({
                    "message_index": i,
                    "role": role,
                    "analysis": analysis
                })

                # Update highest alert level
                alert_priority = {
                    AlertLevel.NONE.value: 0,
                    AlertLevel.INFO.value: 1,
                    AlertLevel.WARNING.value: 2,
                    AlertLevel.URGENT.value: 3,
                    AlertLevel.EMERGENCY.value: 4
                }

                current_priority = alert_priority.get(conversation_analysis["highest_alert_level"], 0)
                new_priority = alert_priority.get(analysis["alert_level"], 0)

                if new_priority > current_priority:
                    conversation_analysis["highest_alert_level"] = analysis["alert_level"]

                # Add categories
                for category in analysis["categories"]:
                    conversation_analysis["safety_categories"].add(category)

        conversation_analysis["safety_categories"] = list(conversation_analysis["safety_categories"])

        return conversation_analysis

    def get_crisis_resources(self) -> Dict[str, str]:
        """
        Get crisis resources contact information

        Returns:
            Dictionary of crisis resources
        """
        return {
            "suicide_crisis": "988 Suicide & Crisis Lifeline (call or text 988)",
            "elder_abuse": "National Elder Abuse Hotline: 1-800-677-1116",
            "emergency": "911 for immediate life-threatening emergencies",
            "domestic_violence": "National Domestic Violence Hotline: 1-800-799-7233",
            "poison_control": "Poison Control: 1-800-222-1222",
            "medicare": "Medicare Fraud Hotline: 1-800-633-4227"
        }

    def format_alert_message(self, analysis: Dict) -> str:
        """
        Format safety analysis into human-readable alert message

        Args:
            analysis: Safety analysis result

        Returns:
            Formatted alert message
        """
        if analysis["alert_level"] == AlertLevel.NONE.value:
            return "No safety concerns detected"

        message_parts = [
            f"🚨 SAFETY ALERT: {analysis['alert_level'].upper()}",
            f"Categories: {', '.join(analysis['categories'])}",
            f"Recommended Action: {analysis['recommended_action']}"
        ]

        if analysis["matched_patterns"]:
            message_parts.append(f"Matched {len(analysis['matched_patterns'])} concerning pattern(s)")

        return "\n".join(message_parts)


# Global instance
safety_monitor = SafetyMonitor()
