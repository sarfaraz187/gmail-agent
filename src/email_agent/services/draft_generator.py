"""Draft generation service using LLM."""

import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from email_agent.config import settings
from email_agent.prompts.templates import (
    DRAFT_GENERATION_PROMPT,
    format_thread_for_prompt,
)
from email_agent.services.tone_detector import tone_detector

logger = logging.getLogger(__name__)


class DraftGenerator:
    """Generates email draft replies using LLM."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )

    def generate_draft(
        self,
        thread: list[dict],
        user_email: str,
        subject: str,
    ) -> tuple[str, str, float]:
        """
        Generate a draft reply for an email thread.

        Args:
            thread: List of email message dictionaries
            user_email: The user's email address
            subject: Email thread subject

        Returns:
            Tuple of (draft_text, detected_tone, confidence)
        """
        tone, confidence = tone_detector.detect_tone(thread)
        logger.info(f"Detected tone: {tone} (confidence: {confidence:.2f})")

        thread_text = format_thread_for_prompt(thread)
        prompt = DRAFT_GENERATION_PROMPT.format(
            tone=tone,
            user_email=user_email,
            thread_text=thread_text,
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        draft = response.content.strip()

        return draft, tone, confidence


draft_generator = DraftGenerator()
