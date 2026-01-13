"""
Style learning service using LLM.

Analyzes sent emails to extract writing style preferences
and updates contact memory for personalized future responses.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from email_agent.config import settings
from email_agent.prompts.templates import STYLE_ANALYSIS_PROMPT
from email_agent.storage.contact_memory import (
    ContactMemoryStore,
    ContactStyle,
    ContactTopic,
    contact_memory_store,
)

logger = logging.getLogger(__name__)


@dataclass
class StyleAnalysis:
    """Result of analyzing a sent email for style."""

    tone: str  # "formal" | "casual"
    greeting_used: str  # e.g., "Hi John,"
    formality_score: float  # 0.0 to 1.0
    response_length: str  # "short" | "medium" | "long"
    topics_discussed: list[str]


class StyleLearner:
    """
    Learns writing style from sent emails using LLM.

    Extracts style preferences and topics from sent emails,
    then updates contact memory for future personalization.
    """

    def __init__(self, memory_store: ContactMemoryStore | None = None) -> None:
        """
        Initialize the style learner.

        Args:
            memory_store: ContactMemoryStore instance. Uses singleton if None.
        """
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,  # Low temperature for consistent analysis
            max_tokens=300,
        )
        self.memory_store = memory_store or contact_memory_store

    def analyze_sent_email(
        self,
        sent_body: str,
        recipient_email: str,
        recipient_name: str = "",
        thread_context: list[str] | None = None,
    ) -> StyleAnalysis:
        """
        Analyze a sent email to extract style and topics.

        Args:
            sent_body: The body of the sent email.
            recipient_email: Recipient's email address.
            recipient_name: Recipient's name (if known).
            thread_context: Previous emails in thread for context.

        Returns:
            StyleAnalysis with extracted style preferences.
        """
        context_text = "\n---\n".join(thread_context) if thread_context else "None"

        prompt = STYLE_ANALYSIS_PROMPT.format(
            recipient_email=recipient_email,
            recipient_name=recipient_name or "Unknown",
            sent_body=sent_body,
            thread_context=context_text,
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = json.loads(response.content.strip())

            return StyleAnalysis(
                tone=result.get("tone", "formal").lower(),
                greeting_used=result.get("greeting_used", ""),
                formality_score=float(result.get("formality_score", 0.5)),
                response_length=result.get("response_length", "medium"),
                topics_discussed=result.get("topics_discussed", [])[:3],
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse style analysis response: {e}")
            # Return defaults on parse failure
            return StyleAnalysis(
                tone="formal",
                greeting_used="",
                formality_score=0.5,
                response_length="medium",
                topics_discussed=[],
            )

    def merge_style(
        self,
        existing: ContactStyle | None,
        new_analysis: StyleAnalysis,
    ) -> ContactStyle:
        """
        Merge new analysis with existing style profile.

        Uses weighted averaging to update style over time,
        giving more weight to recent interactions.

        Args:
            existing: Existing ContactStyle (or None for new contact).
            new_analysis: New StyleAnalysis from latest email.

        Returns:
            Updated ContactStyle.
        """
        if existing is None or existing.sample_count == 0:
            # First email to this contact - use analysis directly
            return ContactStyle(
                tone=new_analysis.tone,
                greeting_preference=new_analysis.greeting_used,
                formality_score=new_analysis.formality_score,
                avg_response_length=new_analysis.response_length,
                sample_count=1,
            )

        # Weighted average for formality score
        # Give 30% weight to new data, 70% to existing
        new_weight = 0.3
        old_weight = 0.7

        new_formality = (
            old_weight * existing.formality_score
            + new_weight * new_analysis.formality_score
        )

        # Tone: switch only if consistent pattern emerges
        # Keep existing tone unless formality clearly indicates change
        if new_formality < 0.4:
            new_tone = "casual"
        elif new_formality > 0.6:
            new_tone = "formal"
        else:
            new_tone = existing.tone  # Keep existing for mixed

        # Greeting: prefer most recent if provided
        new_greeting = (
            new_analysis.greeting_used
            if new_analysis.greeting_used
            else existing.greeting_preference
        )

        # Response length: use most recent
        new_length = new_analysis.response_length or existing.avg_response_length

        return ContactStyle(
            tone=new_tone,
            greeting_preference=new_greeting,
            formality_score=round(new_formality, 2),
            avg_response_length=new_length,
            sample_count=existing.sample_count + 1,
        )

    def learn_from_sent_email(
        self,
        sent_body: str,
        recipient_email: str,
        recipient_name: str = "",
        thread_context: list[str] | None = None,
    ) -> None:
        """
        Learn from a sent email and update contact memory.

        This is the main entry point for the learning flow.
        Analyzes the email, merges with existing style, and saves.

        Args:
            sent_body: The body of the sent email.
            recipient_email: Recipient's email address.
            recipient_name: Recipient's name (if known).
            thread_context: Previous emails in thread for context.
        """
        try:
            # 1. Analyze the sent email
            analysis = self.analyze_sent_email(
                sent_body=sent_body,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                thread_context=thread_context,
            )

            logger.info(
                f"Style analysis for {recipient_email}: "
                f"tone={analysis.tone}, formality={analysis.formality_score:.2f}"
            )

            # 2. Get existing contact memory
            existing = self.memory_store.get_contact(recipient_email)

            # 3. Merge style
            updated_style = self.merge_style(
                existing.style if existing else None,
                analysis,
            )

            # 4. Update style in memory
            self.memory_store.update_style(recipient_email, updated_style)

            # 5. Update contact name if provided and not already set
            if recipient_name:
                self.memory_store.update_contact_name(recipient_email, recipient_name)

            # 6. Add topics
            now = datetime.utcnow().isoformat() + "Z"
            for topic in analysis.topics_discussed:
                if topic.strip():
                    self.memory_store.add_topic(
                        recipient_email,
                        ContactTopic(
                            topic=topic,
                            last_mentioned=now,
                            context_snippet=sent_body[:200] if sent_body else "",
                        ),
                    )

            logger.info(f"Updated contact memory for: {recipient_email}")

        except Exception as e:
            # Non-critical - log and continue
            logger.warning(f"Failed to learn from sent email: {e}")


# Singleton instance for easy import
style_learner = StyleLearner()
