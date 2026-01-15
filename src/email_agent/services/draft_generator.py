"""Draft generation service using LLM."""

import logging
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from email_agent.config import settings
from email_agent.prompts.templates import (
    DRAFT_GENERATION_PROMPT,
    DRAFT_GENERATION_PROMPT_WITH_MEMORY,
    format_thread_for_prompt,
)
from email_agent.services.tone_detector import tone_detector
from email_agent.storage.contact_memory import contact_memory_store

logger = logging.getLogger(__name__)

# Sign-off patterns to remove (LLM sometimes adds these despite instructions)
SIGN_OFF_PATTERNS = [
    r"^(Best regards?|Kind regards?|Warm regards?|Regards),?\s*$",
    r"^(Sincerely|Yours sincerely|Yours truly),?\s*$",
    r"^(Thanks?|Thank you|Many thanks),?\s*$",
    r"^(Cheers|All the best|Best wishes),?\s*$",
    r"^[A-Z][a-z]+ [A-Z][a-z]+\s*$",  # Standalone name like "Mohammed Sarfaraz"
]


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
        recipient_email: str | None = None,
        recipient_name: str | None = None,
    ) -> tuple[str, str, float]:
        """
        Generate a draft reply for an email thread.

        If recipient_email is provided and contact memory exists,
        uses memory-enhanced prompt for personalized responses.

        Args:
            thread: List of email message dictionaries
            user_email: The user's email address
            subject: Email thread subject
            recipient_email: Recipient's email (for memory lookup)
            recipient_name: Recipient's name (for personalization)

        Returns:
            Tuple of (draft_text, detected_tone, confidence)
        """
        thread_text = format_thread_for_prompt(thread)

        # Try to use contact memory if recipient is known
        contact_memory = None
        if recipient_email:
            contact_memory = contact_memory_store.get_contact(recipient_email)

        if contact_memory and contact_memory.style.sample_count > 0:
            # Use memory-enhanced generation
            return self._generate_with_memory(
                thread_text=thread_text,
                user_email=user_email,
                recipient_email=recipient_email,
                recipient_name=recipient_name or contact_memory.name or "",
                contact_memory=contact_memory,
            )
        else:
            # Fall back to tone detection
            return self._generate_standard(
                thread=thread,
                thread_text=thread_text,
                user_email=user_email,
            )

    def _generate_standard(
        self,
        thread: list[dict],
        thread_text: str,
        user_email: str,
    ) -> tuple[str, str, float]:
        """Generate draft using standard tone detection."""
        tone, confidence = tone_detector.detect_tone(thread)
        logger.info(f"Detected tone: {tone} (confidence: {confidence:.2f})")

        prompt = DRAFT_GENERATION_PROMPT.format(
            tone=tone,
            user_email=user_email,
            thread_text=thread_text,
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        draft = response.content.strip()

        # Clean up the draft (remove duplicates, sign-offs)
        draft = self._cleanup_draft(draft)

        return draft, tone, confidence

    def _generate_with_memory(
        self,
        thread_text: str,
        user_email: str,
        recipient_email: str,
        recipient_name: str,
        contact_memory,
    ) -> tuple[str, str, float]:
        """Generate draft using contact memory for personalization."""
        style = contact_memory.style

        # Format recent topics
        recent_topics = ", ".join(
            [t.topic for t in contact_memory.topics[:5]]
        ) or "None recorded"

        logger.info(
            f"Using contact memory for {recipient_email}: "
            f"tone={style.tone}, formality={style.formality_score:.2f}, "
            f"samples={style.sample_count}"
        )

        prompt = DRAFT_GENERATION_PROMPT_WITH_MEMORY.format(
            user_email=user_email,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            tone=style.tone,
            formality_score=f"{style.formality_score:.1f}",
            greeting_preference=style.greeting_preference or "appropriate greeting",
            response_length=style.avg_response_length,
            recent_topics=recent_topics,
            thread_text=thread_text,
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        draft = response.content.strip()

        # Clean up the draft (remove duplicates, sign-offs)
        draft = self._cleanup_draft(draft)

        # Higher confidence when using memory
        confidence = min(0.9, 0.7 + (style.sample_count * 0.05))

        return draft, style.tone, confidence

    def _cleanup_draft(self, draft: str) -> str:
        """
        Clean up LLM-generated draft.

        Removes:
        - Duplicate paragraphs
        - Sign-off lines (LLM sometimes adds despite instructions)
        - Trailing whitespace

        Args:
            draft: Raw draft from LLM.

        Returns:
            Cleaned draft text.
        """
        if not draft:
            return draft

        lines = draft.strip().split("\n")

        # Remove sign-off lines from the end
        while lines:
            last_line = lines[-1].strip()
            if not last_line:
                lines.pop()
                continue

            # Check if last line matches any sign-off pattern
            is_sign_off = False
            for pattern in SIGN_OFF_PATTERNS:
                if re.match(pattern, last_line, re.IGNORECASE):
                    is_sign_off = True
                    logger.debug(f"Removing sign-off line: {last_line}")
                    break

            if is_sign_off:
                lines.pop()
            else:
                break

        # Rejoin and split into paragraphs
        text = "\n".join(lines).strip()
        paragraphs = re.split(r"\n\n+", text)

        # Remove duplicate paragraphs (keep first occurrence)
        seen = set()
        unique_paragraphs = []
        for para in paragraphs:
            # Normalize for comparison (lowercase, strip extra spaces)
            normalized = " ".join(para.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                unique_paragraphs.append(para)
            else:
                logger.debug(f"Removing duplicate paragraph: {para[:50]}...")

        return "\n\n".join(unique_paragraphs)


draft_generator = DraftGenerator()
