"""
Unit tests for the email classifier.

Tests cover:
- Decision pattern detection (choice, money, commitment, sensitive)
- Email type detection (meeting, scheduling, acknowledgment)
- User preference overrides (always_notify_senders)
- Language detection
- Edge cases
"""

import pytest

from email_agent.agent.classifier import (
    DecisionResult,
    DecisionType,
    EmailClassifier,
    EmailType,
)


@pytest.fixture
def classifier() -> EmailClassifier:
    """Create a classifier with default config."""
    return EmailClassifier()


@pytest.fixture
def classifier_with_config(tmp_path) -> EmailClassifier:
    """Create a classifier with custom config."""
    config_content = """
user:
  email: "test@example.com"

preferences:
  always_notify_senders:
    - "ceo@company.com"
    - "legal@company.com"
    - "@important.org"
  auto_respond_types:
    - "meeting_confirmation"
    - "simple_acknowledgment"
    - "scheduling_request"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return EmailClassifier(config_path=config_file)


class TestDecisionPatterns:
    """Tests for decision-required pattern detection."""

    def test_binary_choice_option_a_or_b(self, classifier: EmailClassifier) -> None:
        """Test detection of 'Option A or B' pattern."""
        result = classifier.classify(
            subject="Design Options",
            body="Please choose: Option A or Option B for the logo design.",
            sender_email="colleague@company.com",
        )

        assert result.decision == DecisionType.NEEDS_CHOICE
        assert "choice" in result.matched_patterns

    def test_which_one_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of 'which one' pattern."""
        result = classifier.classify(
            subject="Design Review",
            body="I've prepared two mockups. Which one do you prefer?",
            sender_email="designer@company.com",
        )

        assert result.decision == DecisionType.NEEDS_CHOICE
        assert "choice" in result.matched_patterns

    def test_do_you_prefer_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of 'do you prefer' pattern."""
        result = classifier.classify(
            subject="Meeting Time",
            body="Do you prefer morning or afternoon for our call?",
            sender_email="colleague@company.com",
        )

        assert result.decision == DecisionType.NEEDS_CHOICE

    def test_dollar_amount_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of dollar amounts."""
        result = classifier.classify(
            subject="Invoice Approval",
            body="Please approve the invoice for $5,000.",
            sender_email="vendor@supplier.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL
        assert "money" in result.matched_patterns

    def test_budget_keyword_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of budget-related keywords."""
        result = classifier.classify(
            subject="Q4 Planning",
            body="We need your approval for the marketing budget.",
            sender_email="finance@company.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL
        assert "money" in result.matched_patterns

    def test_deadline_commitment_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of deadline/commitment patterns."""
        result = classifier.classify(
            subject="Project Timeline",
            body="Can you commit to delivering by end of the month?",
            sender_email="pm@company.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL
        assert "commitment" in result.matched_patterns

    def test_contract_sensitive_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of sensitive/legal patterns."""
        result = classifier.classify(
            subject="NDA Review",
            body="Please sign this confidential agreement.",
            sender_email="legal@company.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL
        assert "sensitive" in result.matched_patterns

    def test_urgent_sensitive_pattern(self, classifier: EmailClassifier) -> None:
        """Test detection of urgent keyword."""
        result = classifier.classify(
            subject="URGENT: Action Required",
            body="This is urgent and requires your immediate attention.",
            sender_email="boss@company.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL
        assert "sensitive" in result.matched_patterns


class TestAutoRespondPatterns:
    """Tests for auto-respond email type detection."""

    def test_meeting_request(self, classifier: EmailClassifier) -> None:
        """Test detection of simple meeting request."""
        result = classifier.classify(
            subject="Quick sync?",
            body="Can we meet tomorrow afternoon to discuss the project?",
            sender_email="colleague@company.com",
        )

        assert result.decision == DecisionType.AUTO_RESPOND
        assert result.email_type == EmailType.MEETING_CONFIRMATION

    def test_scheduling_request(self, classifier: EmailClassifier) -> None:
        """Test detection of scheduling request."""
        result = classifier.classify(
            subject="Availability",
            body="When are you free this week? Let me know your availability.",
            sender_email="colleague@company.com",
        )

        assert result.decision == DecisionType.AUTO_RESPOND
        assert result.email_type == EmailType.SCHEDULING_REQUEST

    def test_simple_acknowledgment(self, classifier: EmailClassifier) -> None:
        """Test detection of simple acknowledgment."""
        result = classifier.classify(
            subject="Re: Report",
            body="Thanks!",
            sender_email="colleague@company.com",
        )

        assert result.decision == DecisionType.AUTO_RESPOND
        assert result.email_type == EmailType.SIMPLE_ACKNOWLEDGMENT

    def test_follow_up_email(self, classifier: EmailClassifier) -> None:
        """Test detection of follow-up email."""
        result = classifier.classify(
            subject="Re: Proposal",
            body="Just checking in - did you get my email from last week?",
            sender_email="client@external.com",
        )

        # follow_up is not in default auto_respond_types
        # so it should default to NEEDS_INPUT
        assert result.email_type == EmailType.FOLLOW_UP


class TestUserPreferences:
    """Tests for user preference overrides."""

    def test_always_notify_sender_exact_match(
        self, classifier_with_config: EmailClassifier
    ) -> None:
        """Test that always_notify_senders triggers NEEDS_INPUT."""
        result = classifier_with_config.classify(
            subject="Quick sync?",
            body="Can we meet tomorrow?",  # Would normally be AUTO_RESPOND
            sender_email="ceo@company.com",
        )

        assert result.decision == DecisionType.NEEDS_INPUT
        assert "always_notify_senders" in result.reason

    def test_always_notify_sender_domain_match(
        self, classifier_with_config: EmailClassifier
    ) -> None:
        """Test domain-based always_notify matching."""
        result = classifier_with_config.classify(
            subject="Hello",
            body="Just wanted to say hi!",
            sender_email="anyone@important.org",
        )

        assert result.decision == DecisionType.NEEDS_INPUT
        assert "always_notify_senders" in result.reason

    def test_always_notify_case_insensitive(
        self, classifier_with_config: EmailClassifier
    ) -> None:
        """Test case-insensitive matching for always_notify."""
        result = classifier_with_config.classify(
            subject="Meeting",
            body="Quick sync?",
            sender_email="CEO@COMPANY.COM",
        )

        assert result.decision == DecisionType.NEEDS_INPUT


class TestDecisionTypePriority:
    """Tests for decision type priority when multiple patterns match."""

    def test_sensitive_takes_priority(self, classifier: EmailClassifier) -> None:
        """Test that sensitive patterns take priority over choice."""
        result = classifier.classify(
            subject="Confidential Contract",
            body="Please choose Option A or Option B for this confidential agreement.",
            sender_email="legal@company.com",
        )

        # Should be NEEDS_APPROVAL (sensitive) not NEEDS_CHOICE
        assert result.decision == DecisionType.NEEDS_APPROVAL

    def test_money_takes_priority_over_choice(
        self, classifier: EmailClassifier
    ) -> None:
        """Test that money patterns take priority over choice."""
        result = classifier.classify(
            subject="Budget Options",
            body="Which option do you prefer? Option A is $10,000, Option B is $15,000.",
            sender_email="finance@company.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL
        assert "money" in result.matched_patterns


class TestLanguageDetection:
    """Tests for language detection."""

    def test_english_default(self, classifier: EmailClassifier) -> None:
        """Test that English is the default language."""
        lang = classifier.detect_language("Hello, how are you doing today?")
        assert lang == "en"

    def test_spanish_detection(self, classifier: EmailClassifier) -> None:
        """Test Spanish language detection."""
        lang = classifier.detect_language("Hola, gracias por tu mensaje.")
        assert lang == "es"

    def test_french_detection(self, classifier: EmailClassifier) -> None:
        """Test French language detection."""
        lang = classifier.detect_language("Bonjour, merci pour votre email.")
        assert lang == "fr"

    def test_german_detection(self, classifier: EmailClassifier) -> None:
        """Test German language detection."""
        lang = classifier.detect_language("Hallo, vielen Dank für Ihre Nachricht.")
        assert lang == "de"

    def test_portuguese_detection(self, classifier: EmailClassifier) -> None:
        """Test Portuguese language detection."""
        lang = classifier.detect_language("Olá, obrigado pela mensagem.")
        assert lang == "pt"

    def test_italian_detection(self, classifier: EmailClassifier) -> None:
        """Test Italian language detection."""
        lang = classifier.detect_language("Ciao, grazie per il messaggio.")
        assert lang == "it"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_body(self, classifier: EmailClassifier) -> None:
        """Test classification with empty body defaults to NEEDS_INPUT."""
        result = classifier.classify(
            subject="Random topic",
            body="",
            sender_email="colleague@company.com",
        )

        # With no body and no matching patterns, should default to NEEDS_INPUT
        assert result.decision == DecisionType.NEEDS_INPUT

    def test_empty_subject(self, classifier: EmailClassifier) -> None:
        """Test classification with empty subject."""
        result = classifier.classify(
            subject="",
            body="Can we schedule a meeting for tomorrow?",
            sender_email="colleague@company.com",
        )

        assert result.decision == DecisionType.AUTO_RESPOND

    def test_no_patterns_matched(self, classifier: EmailClassifier) -> None:
        """Test default behavior when no patterns match."""
        result = classifier.classify(
            subject="Random Subject",
            body="This is a random email with no clear patterns.",
            sender_email="stranger@example.com",
        )

        assert result.decision == DecisionType.NEEDS_INPUT
        assert result.confidence == 0.5

    def test_mixed_case_patterns(self, classifier: EmailClassifier) -> None:
        """Test pattern matching is case-insensitive."""
        result = classifier.classify(
            subject="BUDGET APPROVAL NEEDED",
            body="PLEASE APPROVE THIS $5000 BUDGET REQUEST.",
            sender_email="finance@company.com",
        )

        assert result.decision == DecisionType.NEEDS_APPROVAL

    def test_multiple_currencies(self, classifier: EmailClassifier) -> None:
        """Test detection of different currency symbols."""
        for currency, amount in [("$", "1000"), ("€", "500"), ("£", "750")]:
            result = classifier.classify(
                subject="Payment",
                body=f"Please approve the payment of {currency}{amount}.",
                sender_email="vendor@supplier.com",
            )
            assert result.decision == DecisionType.NEEDS_APPROVAL
            assert "money" in result.matched_patterns


class TestDecisionResultDataclass:
    """Tests for DecisionResult dataclass."""

    def test_decision_result_fields(self, classifier: EmailClassifier) -> None:
        """Test that DecisionResult has all expected fields."""
        result = classifier.classify(
            subject="Test",
            body="Can we meet?",
            sender_email="test@example.com",
        )

        assert hasattr(result, "decision")
        assert hasattr(result, "email_type")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reason")
        assert hasattr(result, "matched_patterns")
        assert hasattr(result, "detected_language")

    def test_confidence_range(self, classifier: EmailClassifier) -> None:
        """Test that confidence is within valid range."""
        result = classifier.classify(
            subject="Budget",
            body="Please approve $5000.",
            sender_email="test@example.com",
        )

        assert 0.0 <= result.confidence <= 1.0


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_default_config_when_file_missing(self) -> None:
        """Test that default config is used when file doesn't exist."""
        classifier = EmailClassifier(config_path="/nonexistent/path/config.yaml")
        config = classifier.config

        assert "preferences" in config
        assert "auto_respond_types" in config["preferences"]

    def test_custom_config_loading(self, tmp_path) -> None:
        """Test loading of custom config file."""
        config_content = """
preferences:
  always_notify_senders:
    - "important@vip.com"
  auto_respond_types:
    - "meeting_confirmation"
"""
        config_file = tmp_path / "custom_config.yaml"
        config_file.write_text(config_content)

        classifier = EmailClassifier(config_path=config_file)
        config = classifier.config

        assert "important@vip.com" in config["preferences"]["always_notify_senders"]
