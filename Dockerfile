# Build stage - install dependencies with UV
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files (README.md needed for hatchling build)
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install dependencies using UV
RUN uv sync --frozen --no-dev --no-editable

# Runtime stage - minimal image
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src ./src
COPY config.yaml ./

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Cloud Run sets PORT environment variable
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "src.email_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
