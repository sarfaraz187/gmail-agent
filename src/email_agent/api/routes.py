"""API routes for the email draft agent."""

import logging

from fastapi import APIRouter, HTTPException

from email_agent.api.schemas import (
    GenerateDraftRequest,
    GenerateDraftResponse,
    HealthResponse,
)
from email_agent.config import settings
from email_agent.services.draft_generator import draft_generator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version=settings.app_version)


@router.post("/generate-draft", response_model=GenerateDraftResponse)
async def generate_draft(request: GenerateDraftRequest) -> GenerateDraftResponse:
    """
    Generate a draft reply for an email thread.

    This endpoint receives the email thread from the Gmail add-on,
    detects the tone, and generates an appropriate reply.
    """
    logger.info(
        f"Generating draft for thread with {len(request.thread)} messages, "
        f"subject: {request.subject}"
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
            for msg in request.thread
        ]

        draft, tone, confidence = draft_generator.generate_draft(
            thread=thread_data,
            user_email=request.user_email,
            subject=request.subject,
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
            detail=f"Failed to generate draft: {str(e)}",
        )
