"""Tone detection service using LLM."""

import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from email_agent.config import settings
from email_agent.prompts.templates import TONE_DETECTION_PROMPT, format_thread_for_prompt

logger = logging.getLogger(__name__)


class ToneDetector:
    """Detects the tone of an email thread using LLM."""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
            max_tokens=100,
        )

    def detect_tone(self, thread: list[dict]) -> tuple[str, float]:
        """
        Detect the tone of an email thread.

        Args:
            thread: List of email message dictionaries

        Returns:
            Tuple of (tone, confidence) where tone is 'formal' or 'casual'
        """
        thread_text = format_thread_for_prompt(thread)
        prompt = TONE_DETECTION_PROMPT.format(thread_text=thread_text)

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = json.loads(response.content.strip())

            tone = result.get("tone", "formal").lower()
            confidence = float(result.get("confidence", 0.7))

            if tone not in ("formal", "casual"):
                tone = "formal"

            return tone, min(max(confidence, 0.0), 1.0)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse tone detection response: {e}")
            return "formal", 0.5


tone_detector = ToneDetector()
