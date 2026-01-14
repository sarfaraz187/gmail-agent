"""
Email classification for decision detection.

This module determines whether the agent can auto-respond to an email
or if user input is required.

Classification Categories:
- AUTO_RESPOND: Agent can handle fully (meeting requests, acknowledgments)
- NEEDS_CHOICE: User must pick between options (A/B/C)
- NEEDS_APPROVAL: User must approve (money, contracts, commitments)
- NEEDS_INPUT: Ambiguous - needs clarification

The classifier uses:
1. Pattern matching for decision-required content
2. User preferences from config.yaml
3. Email type detection
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of decisions the classifier can make."""

    AUTO_RESPOND = "auto"  # Agent handles fully
    NEEDS_CHOICE = "choice"  # User picks A/B/C
    NEEDS_APPROVAL = "approve"  # User approves/rejects
    NEEDS_INPUT = "input"  # Ambiguous - needs clarification


class EmailType(Enum):
    """Detected email types for auto-respond classification."""

    MEETING_CONFIRMATION = "meeting_confirmation"
    SIMPLE_ACKNOWLEDGMENT = "simple_acknowledgment"
    SCHEDULING_REQUEST = "scheduling_request"
    FOLLOW_UP = "follow_up"
    INFO_REQUEST = "info_request"
    STATUS_UPDATE = "status_update"  # Rejections, notifications, status changes
    UNKNOWN = "unknown"


@dataclass
class DecisionResult:
    """Result of email classification."""

    decision: DecisionType
    email_type: EmailType
    confidence: float
    reason: str
    matched_patterns: list[str] = field(default_factory=list)
    detected_language: str = "en"


# =============================================================================
# Pattern Definitions
# =============================================================================

# Patterns that indicate user decision is required
DECISION_REQUIRED_PATTERNS: dict[str, list[str]] = {
    # Binary/Multiple choices
    "choice": [
        r"option\s+[a-z]\s+(or|vs\.?|versus)\s+(option\s+)?[a-z]",
        r"which\s+(one|option|choice|approach|solution)",
        r"do\s+you\s+prefer",
        r"would\s+you\s+(prefer|like|rather|choose)",
        r"should\s+(we|i)\s+(go\s+with|choose|pick|select)",
        r"please\s+(choose|select|pick)",
        r"what\s+do\s+you\s+think\s+(about|of)",
        r"(option|choice)\s*[1-9a-z][\s:]+.*?(option|choice)\s*[1-9a-z]",
    ],
    # Money and budget
    "money": [
        r"\$\s*[\d,]+(?:\.\d{2})?",  # Dollar amounts
        r"€\s*[\d,]+(?:\.\d{2})?",  # Euro amounts
        r"£\s*[\d,]+(?:\.\d{2})?",  # Pound amounts
        r"\b(budget|cost|price|expense|payment|invoice)\b",
        r"\b(approve|approval|authorize|authorization)\b",
        r"\b(quote|quotation|estimate|pricing)\b",
    ],
    # Commitments and deadlines
    "commitment": [
        r"\b(can\s+you\s+)?(commit|promise|guarantee)\b",
        r"\b(deadline|due\s+date|deliver\s+by|complete\s+by)\b",
        r"\b(by\s+)?(end\s+of|before)\s+(the\s+)?(day|week|month|quarter)",
        r"when\s+can\s+you\s+(deliver|complete|finish)",
        r"is\s+it\s+possible\s+to\s+(deliver|complete|finish)",
    ],
    # Sensitive/Legal
    "sensitive": [
        r"\b(confidential|sensitive|private)\b",
        r"\b(urgent|asap|immediately|critical)\b",
        r"\b(legal|lawyer|attorney|lawsuit)\b",
        r"\b(contract|agreement|terms|nda|mou)\b",
        r"\b(sign|signature|execute)\s+(this|the)\s+(document|agreement|contract)",
        r"\b(compliance|regulatory|audit)\b",
    ],
}

# Patterns for auto-respond email types
AUTO_RESPOND_PATTERNS: dict[str, list[str]] = {
    "meeting_confirmation": [
        r"(can|could)\s+(we|you)\s+(meet|sync|chat|talk|call)",
        r"(are|is)\s+(you|your\s+team)\s+(free|available)",
        r"(schedule|set\s+up|arrange)\s+(a\s+)?(meeting|call|sync)",
        r"(let'?s|shall\s+we)\s+(meet|sync|chat|talk|call)",
        r"(how\s+about|what\s+about)\s+\w+day",
    ],
    "simple_acknowledgment": [
        r"\b(thanks|thank\s+you|thx|ty)\s*[!.]*\s*$",
        r"(got\s+it|received|noted|understood)",
        r"(sounds\s+good|looks\s+good|perfect|great)",
        r"(will\s+do|on\s+it)",
    ],
    "scheduling_request": [
        r"when\s+(are|is)\s+(you|your\s+team)\s+(free|available)",
        r"(your|what'?s\s+your)\s+availability",
        r"(let\s+me\s+know|lmk)\s+(when|your\s+availability)",
        r"(can\s+you\s+share|share)\s+your\s+(calendar|availability)",
    ],
    "follow_up": [
        r"(just\s+)?(checking\s+in|following\s+up)",
        r"(did\s+you\s+(get|receive|see))",
        r"(any\s+update|updates?)\s+(on|about|regarding)",
        r"(wanted\s+to\s+)?(touch\s+base|check\s+in)",
    ],
    "status_update": [
        # Rejection patterns
        r"(unfortunately|regret\s+to\s+inform)",
        r"(not\s+(been\s+)?selected|not\s+moving\s+forward)",
        r"(decided\s+to\s+pursue|chosen\s+to\s+proceed\s+with)\s+other",
        r"(position\s+has\s+been\s+filled|role\s+has\s+been\s+filled)",
        r"(will\s+not\s+be\s+(proceeding|moving\s+forward))",
        r"(after\s+careful\s+consideration)",
        # General status/notification patterns
        r"(this\s+is\s+(a\s+)?(to\s+)?(notify|inform|update)\s+you)",
        r"(wanted\s+to\s+let\s+you\s+know)",
        r"(for\s+your\s+(information|records|reference))",
        r"(please\s+be\s+(advised|informed))",
        r"(status\s+update|update\s+on\s+your)",
    ],
}


class EmailClassifier:
    """
    Classifies emails to determine if auto-response is possible.

    Uses pattern matching and user preferences to categorize emails.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        """
        Initialize the classifier.

        Args:
            config_path: Path to config.yaml. Auto-detected if None.
        """
        self._config: dict | None = None
        self._config_path = config_path

    @property
    def config(self) -> dict:
        """Load and cache user configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> dict:
        """Load configuration from config.yaml."""
        if self._config_path:
            config_path = Path(self._config_path)
        else:
            # Try common locations
            possible_paths = [
                Path("config.yaml"),
                Path(__file__).parent.parent.parent.parent.parent / "config.yaml",
            ]
            config_path = None
            for p in possible_paths:
                if p.exists():
                    config_path = p
                    break

        if config_path and config_path.exists():
            try:
                return yaml.safe_load(config_path.read_text())
            except Exception as e:
                logger.warning(f"Failed to load config.yaml: {e}")

        # Return default config
        return {
            "preferences": {
                "always_notify_senders": [],
                "auto_respond_types": [
                    "meeting_confirmation",
                    "simple_acknowledgment",
                    "scheduling_request",
                    "status_update",
                ],
            }
        }

    def classify(
        self,
        subject: str,
        body: str,
        sender_email: str,
        thread_context: list[str] | None = None,
    ) -> DecisionResult:
        """
        Classify an email to determine if auto-response is possible.

        Args:
            subject: Email subject.
            body: Email body text.
            sender_email: Sender's email address.
            thread_context: Optional list of previous email bodies in thread.

        Returns:
            DecisionResult with classification details.
        """
        # Normalize text for pattern matching
        text_to_check = f"{subject}\n{body}".lower()

        # 1. Check always_notify_senders first (highest priority)
        always_notify = self.config.get("preferences", {}).get(
            "always_notify_senders", []
        )
        if self._sender_in_list(sender_email, always_notify):
            logger.debug(f"Sender {sender_email} in always_notify list")
            return DecisionResult(
                decision=DecisionType.NEEDS_INPUT,
                email_type=EmailType.UNKNOWN,
                confidence=1.0,
                reason=f"Sender '{sender_email}' is in always_notify_senders list",
                matched_patterns=[],
            )

        # 2. Check for decision-required patterns
        decision_patterns_matched = self._check_decision_patterns(text_to_check)

        if decision_patterns_matched:
            decision_type = self._determine_decision_type(decision_patterns_matched)
            return DecisionResult(
                decision=decision_type,
                email_type=EmailType.UNKNOWN,
                confidence=0.85,
                reason=f"Matched decision patterns: {', '.join(decision_patterns_matched.keys())}",
                matched_patterns=list(decision_patterns_matched.keys()),
            )

        # 3. Check for auto-respond email types
        email_type, confidence = self._detect_email_type(text_to_check)

        auto_respond_types = self.config.get("preferences", {}).get(
            "auto_respond_types", []
        )

        if email_type.value in auto_respond_types and confidence >= 0.6:
            return DecisionResult(
                decision=DecisionType.AUTO_RESPOND,
                email_type=email_type,
                confidence=confidence,
                reason=f"Detected as '{email_type.value}' which is in auto_respond_types",
                matched_patterns=[email_type.value],
            )

        # 4. Default: Need user input for unknown email types
        return DecisionResult(
            decision=DecisionType.NEEDS_INPUT,
            email_type=email_type,
            confidence=0.5,
            reason="No clear patterns matched; defaulting to user input",
            matched_patterns=[],
        )

    def _sender_in_list(self, sender_email: str, email_list: list[str]) -> bool:
        """Check if sender email matches any in the list."""
        sender_lower = sender_email.lower().strip()

        for email in email_list:
            email_lower = email.lower().strip()
            # Exact match or domain match (e.g., "@company.com")
            if email_lower.startswith("@"):
                if sender_lower.endswith(email_lower):
                    return True
            elif sender_lower == email_lower:
                return True

        return False

    def _check_decision_patterns(self, text: str) -> dict[str, list[str]]:
        """
        Check text against decision-required patterns.

        Args:
            text: Normalized text to check.

        Returns:
            Dict of category -> matched patterns.
        """
        matches: dict[str, list[str]] = {}

        for category, patterns in DECISION_REQUIRED_PATTERNS.items():
            category_matches = []
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    category_matches.append(pattern)

            if category_matches:
                matches[category] = category_matches

        return matches

    def _determine_decision_type(
        self, matched_patterns: dict[str, list[str]]
    ) -> DecisionType:
        """
        Determine the decision type based on matched pattern categories.

        Priority:
        1. sensitive -> NEEDS_APPROVAL
        2. money -> NEEDS_APPROVAL
        3. commitment -> NEEDS_APPROVAL
        4. choice -> NEEDS_CHOICE
        """
        if "sensitive" in matched_patterns:
            return DecisionType.NEEDS_APPROVAL

        if "money" in matched_patterns:
            return DecisionType.NEEDS_APPROVAL

        if "commitment" in matched_patterns:
            return DecisionType.NEEDS_APPROVAL

        if "choice" in matched_patterns:
            return DecisionType.NEEDS_CHOICE

        return DecisionType.NEEDS_INPUT

    def _detect_email_type(self, text: str) -> tuple[EmailType, float]:
        """
        Detect the type of email for auto-respond classification.

        Args:
            text: Normalized text to check.

        Returns:
            Tuple of (EmailType, confidence score).
        """
        best_match = EmailType.UNKNOWN
        best_score = 0.0

        for email_type_str, patterns in AUTO_RESPOND_PATTERNS.items():
            match_count = 0
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    match_count += 1

            if match_count > 0:
                # Score based on number of patterns matched
                score = min(0.6 + (match_count * 0.1), 0.95)
                if score > best_score:
                    best_score = score
                    best_match = EmailType(email_type_str)

        return best_match, best_score

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the email.

        For MVP, we use simple heuristics. In future, could use LLM.

        Args:
            text: Email text.

        Returns:
            ISO language code (e.g., 'en', 'es', 'fr').
        """
        # Simple heuristic: check for common words in different languages
        text_lower = text.lower()

        language_indicators = {
            "es": [
                r"\b(hola|gracias|buenos|buenas|saludos|atentamente)\b",
                r"\b(por favor|estimado|querido)\b",
            ],
            "fr": [
                r"\b(bonjour|merci|salut|cordialement|bonsoir)\b",
                r"\b(s'il vous plaît|cher|chère)\b",
            ],
            "de": [
                r"\b(hallo|danke|guten|vielen dank|freundliche)\b",
                r"\b(bitte|liebe|lieber)\b",
            ],
            "pt": [
                r"\b(olá|obrigado|obrigada|bom dia|boa tarde)\b",
                r"\b(por favor|prezado|prezada)\b",
            ],
            "it": [
                r"\b(ciao|grazie|buongiorno|saluti|cordiali)\b",
                r"\b(per favore|gentile|caro|cara)\b",
            ],
        }

        for lang, patterns in language_indicators.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return lang

        # Default to English
        return "en"


# Singleton instance for easy import
email_classifier = EmailClassifier()
