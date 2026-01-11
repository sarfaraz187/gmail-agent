# Gmail AI Draft Agent

AI-powered email draft generation for Gmail.

## Setup

1. Copy `.env.example` to `.env` and add your OpenAI API key
2. Install dependencies: `uv sync`
3. Run the server: `uv run uvicorn src.email_agent.main:app --reload --port 8000`

## Usage

The backend exposes a POST endpoint at `/generate-draft` that accepts email thread data and returns an AI-generated reply.
