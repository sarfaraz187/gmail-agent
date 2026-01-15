"""API routes for the email draft agent."""

import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from email_agent.api.schemas import (
    GenerateDraftRequest,
    GenerateDraftResponse,
    HealthResponse,
)
from email_agent.config import settings
from email_agent.security.sanitization import redact_sensitive_for_logging
from email_agent.services.draft_generator import draft_generator

logger = logging.getLogger(__name__)

router = APIRouter()

# Get limiter from app state (set in main.py)
# This allows us to use the same limiter instance
limiter = Limiter(key_func=get_remote_address)


@router.get("/health", response_model=HealthResponse)
@limiter.limit("60/minute")
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version=settings.app_version)


@router.post("/generate-draft", response_model=GenerateDraftResponse)
@limiter.limit("20/minute")  # More restrictive - prevents API cost abuse
async def generate_draft(
    request: Request,
    draft_request: GenerateDraftRequest,
) -> GenerateDraftResponse:
    """
    Generate a draft reply for an email thread.

    This endpoint receives the email thread from the Gmail add-on,
    detects the tone, and generates an appropriate reply.

    Rate limited to 20 requests/minute to prevent API cost abuse.
    """
    # Log with redacted subject for privacy
    redacted_subject = redact_sensitive_for_logging(draft_request.subject)
    logger.info(
        f"Generating draft for thread with {len(draft_request.thread)} messages, "
        f"subject: {redacted_subject}"
    )

    try:
        thread_data = [
            {
                "from_": msg.from_,
                "to": msg.to,
                "date": msg.date,
                "subject": msg.subject,
                "body": msg.body,
            }
            for msg in draft_request.thread
        ]

        draft, tone, confidence = draft_generator.generate_draft(
            thread=thread_data,
            user_email=draft_request.user_email,
            subject=draft_request.subject,
        )

        logger.info(f"Generated draft with tone: {tone}, confidence: {confidence:.2f}")

        return GenerateDraftResponse(
            draft=draft,
            detected_tone=tone,
            confidence=confidence,
        )

    except Exception as e:
        logger.exception("Failed to generate draft")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate draft. Please try again.",
        )
