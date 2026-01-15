"""FastAPI application entry point."""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from email_agent.api.routes import router
from email_agent.api.webhook import webhook_router
from email_agent.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# =============================================================================
# RATE LIMITING CONFIGURATION
# =============================================================================

# Custom key function that uses X-Forwarded-For in Cloud Run
def get_client_ip(request: Request) -> str:
    """Get client IP, handling Cloud Run's X-Forwarded-For header."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


# Initialize rate limiter
# Storage defaults to in-memory, which resets on restart
# For production with multiple instances, use Redis storage
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["100/minute"],  # Global default
)


# =============================================================================
# CORS CONFIGURATION
# =============================================================================

def get_allowed_origins() -> list[str]:
    """
    Get allowed CORS origins based on environment.

    In production, restricts to known origins.
    In development, allows localhost.
    """
    # Allow override via environment variable (comma-separated)
    if custom_origins := os.getenv("CORS_ALLOWED_ORIGINS"):
        return [origin.strip() for origin in custom_origins.split(",")]

    # Default allowed origins
    allowed = [
        "https://mail.google.com",
        "https://inbox.google.com",
    ]

    # Add service URL if available (for Cloud Run)
    if service_url := os.getenv("SERVICE_URL"):
        allowed.append(service_url)

    # In development, allow localhost
    if not os.getenv("K_SERVICE"):  # Not in Cloud Run
        allowed.extend([
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ])

    return allowed


# =============================================================================
# APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered email draft generation for Gmail",
    # Disable automatic docs in production for security
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add rate limiter to app state
app.state.limiter = limiter

# Add rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware with restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router)
app.include_router(webhook_router)


# =============================================================================
# EVENT HANDLERS
# =============================================================================


@app.on_event("startup")
async def startup_event() -> None:
    """Log startup information."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Using OpenAI model: {settings.openai_model}")
    logger.info(f"CORS allowed origins: {get_allowed_origins()}")
    logger.info(f"Rate limiting: {limiter._default_limits}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
