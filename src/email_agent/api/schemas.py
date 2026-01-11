"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, EmailStr, Field


class EmailMessage(BaseModel):
    """Single email message in a thread."""

    from_: str = Field(..., alias="from", description="Sender email address")
    to: str = Field(..., description="Recipient email address")
    date: str = Field(..., description="ISO format date string")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")

    class Config:
        populate_by_name = True


class GenerateDraftRequest(BaseModel):
    """Request body for generating a draft reply."""

    thread: list[EmailMessage] = Field(
        ..., description="List of email messages in the thread"
    )
    user_email: str = Field(..., description="Current user's email address")
    subject: str = Field(..., description="Email thread subject")


class GenerateDraftResponse(BaseModel):
    """Response containing the generated draft."""

    draft: str = Field(..., description="Generated email draft")
    detected_tone: str = Field(..., description="Detected tone (formal/casual)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for tone detection"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy")
    version: str
