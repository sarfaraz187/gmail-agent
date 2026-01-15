"""Pydantic schemas for API request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# INPUT SIZE LIMITS (Security)
# =============================================================================

MAX_EMAIL_SUBJECT_LENGTH = 500
MAX_EMAIL_BODY_LENGTH = 50000  # 50KB per email
MAX_EMAIL_ADDRESS_LENGTH = 320  # RFC 5321 limit
MAX_THREAD_SIZE = 50  # Maximum emails in a thread


class EmailMessage(BaseModel):
    """Single email message in a thread."""

    from_: str = Field(
        ...,
        alias="from",
        description="Sender email address",
        max_length=MAX_EMAIL_ADDRESS_LENGTH,
    )
    to: str = Field(
        ...,
        description="Recipient email address",
        max_length=MAX_EMAIL_ADDRESS_LENGTH,
    )
    date: str = Field(
        ...,
        description="ISO format date string",
        max_length=100,
    )
    subject: str = Field(
        ...,
        description="Email subject",
        max_length=MAX_EMAIL_SUBJECT_LENGTH,
    )
    body: str = Field(
        ...,
        description="Email body content",
        max_length=MAX_EMAIL_BODY_LENGTH,
    )

    class Config:
        populate_by_name = True


class GenerateDraftRequest(BaseModel):
    """Request body for generating a draft reply."""

    thread: list[EmailMessage] = Field(
        ...,
        description="List of email messages in the thread",
        max_length=MAX_THREAD_SIZE,
    )
    user_email: str = Field(
        ...,
        description="Current user's email address",
        max_length=MAX_EMAIL_ADDRESS_LENGTH,
    )
    subject: str = Field(
        ...,
        description="Email thread subject",
        max_length=MAX_EMAIL_SUBJECT_LENGTH,
    )

    @field_validator("thread")
    @classmethod
    def validate_thread_not_empty(cls, v: list[EmailMessage]) -> list[EmailMessage]:
        """Ensure thread has at least one message."""
        if not v:
            raise ValueError("Thread must contain at least one email")
        return v


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


# =============================================================================
# Webhook Schemas (for Gmail Push Notifications via Pub/Sub)
# =============================================================================


class PubSubMessage(BaseModel):
    """
    Inner message from Pub/Sub push.

    The 'data' field contains base64-encoded JSON from Gmail.
    """

    data: str = Field(..., description="Base64-encoded message data from Gmail")
    messageId: str = Field(..., description="Unique Pub/Sub message ID")
    publishTime: datetime = Field(..., description="When message was published")


class PubSubPushRequest(BaseModel):
    """
    Request body from Pub/Sub push delivery.

    This is what Pub/Sub sends to our /webhook/gmail endpoint.
    The actual Gmail notification is base64-encoded inside message.data.
    """

    message: PubSubMessage = Field(..., description="The Pub/Sub message")
    subscription: str = Field(..., description="Subscription that delivered this message")


class GmailNotificationData(BaseModel):
    """
    Decoded Gmail notification data.

    This is the JSON inside the base64-encoded message.data field.
    Gmail only tells us THAT something changed (historyId), not WHAT changed.
    """

    emailAddress: str = Field(..., description="Email address that changed")
    historyId: int = Field(..., description="Gmail history ID for this change")


class WebhookAckResponse(BaseModel):
    """
    Response from the webhook endpoint.

    Pub/Sub expects a 2xx response to acknowledge the message.
    """

    status: str = Field(default="ok", description="Processing status")
    processed: int = Field(default=0, description="Number of emails processed")
    skipped: int = Field(default=0, description="Number of emails skipped")


class RenewWatchResponse(BaseModel):
    """Response from the /renew-watch endpoint."""

    success: bool = Field(..., description="Whether renewal succeeded")
    message: str = Field(..., description="Status message")
    history_id: int | None = Field(None, description="New starting history ID")
    expiration: datetime | None = Field(None, description="When watch expires")


class WatchStatusResponse(BaseModel):
    """Response from the /watch-status endpoint."""

    active: bool = Field(..., description="Whether a watch is currently active")
    expiration: datetime | None = Field(None, description="When watch expires")
    label_name: str = Field(..., description="Label being watched")
    pubsub_topic: str = Field(..., description="Pub/Sub topic for notifications")
