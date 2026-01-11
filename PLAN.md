# Gmail AI Draft Agent - Project Plan

## Overview

A personal Gmail AI agent that automatically drafts email replies by reading the entire conversation thread and matching the tone of the sender.

---

## Problem Statement

- Replying to emails is time-consuming
- Need to read entire threads to understand context
- Tone should match the conversation (formal vs casual)
- Goal: AI pre-drafts replies, user reviews/edits and sends

---

## Solution

A Google Workspace Add-on that appears in Gmail's sidebar with a "Generate Draft" button. When clicked, it sends the email thread to a Python backend that uses OpenAI to generate a contextual reply.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  GMAIL                                                        │
│  ┌────────────────────────┐  ┌─────────────────────────────┐ │
│  │  Email Thread          │  │  YOUR ADD-ON (Sidebar)      │ │
│  │                        │  │                             │ │
│  │  "Hi, can we meet      │  │  [✨ Generate Draft]        │ │
│  │   tomorrow at 3pm?"    │  │                             │ │
│  │                        │  │  Generated Reply:           │ │
│  │                        │  │  "Hi! Yes, 3pm works        │ │
│  │                        │  │   great for me. See you     │ │
│  │                        │  │   then!"                    │ │
│  │                        │  │                             │ │
│  │                        │  │  [📋 Copy to Reply]         │ │
│  └────────────────────────┘  └──────────────┬──────────────┘ │
└─────────────────────────────────────────────│────────────────┘
                                              │ HTTPS
                                              ▼
┌──────────────────────────────────────────────────────────────┐
│  PYTHON BACKEND (Docker → AWS)                                │
│                                                               │
│  FastAPI + Pydantic + LangChain + OpenAI GPT-4o              │
│                                                               │
│  • Receives email thread                                      │
│  • Detects tone (formal/casual)                               │
│  • Generates contextual reply                                 │
│  • Returns draft                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.12 | Backend development |
| Package Manager | UV | Fast, modern Python tooling |
| API Framework | FastAPI | HTTP endpoints for add-on |
| Validation | Pydantic | Request/response models |
| LLM Orchestration | LangChain | Prompt management, chains |
| LLM Provider | OpenAI GPT-4o | Draft generation |
| Container | Docker | Local dev + AWS deployment |
| Gmail Integration | Google Workspace Add-on | Sidebar UI in Gmail |
| Local Tunnel | ngrok | Expose localhost to Google |
| Production | AWS (ECS Fargate or Lambda) | Future hosting |

---

## Project Structure

```
email-agent/
├── pyproject.toml              # UV/Python dependencies
├── uv.lock                     # Lock file
├── Dockerfile                  # Container config
├── docker-compose.yml          # Local dev orchestration
├── .env                        # API keys (gitignored)
├── .env.example                # Template for env vars
├── README.md                   # Project documentation
├── PLAN.md                     # This file
│
├── src/
│   └── email_agent/
│       ├── __init__.py
│       ├── main.py             # FastAPI app entry point
│       ├── config.py           # Pydantic settings
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py       # Add-on HTTP endpoints
│       │   └── schemas.py      # Pydantic request/response models
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── email_parser.py     # Parse email thread
│       │   ├── tone_detector.py    # Detect formal/casual tone
│       │   └── draft_generator.py  # LangChain + OpenAI logic
│       │
│       └── prompts/
│           ├── __init__.py
│           └── templates.py    # Prompt templates
│
├── addon/
│   ├── appsscript.json         # Add-on manifest
│   └── Code.gs                 # Apps Script code
│
└── tests/
    ├── __init__.py
    ├── test_api.py
    └── test_services.py
```

---

## Core User Flow

1. User opens an email in Gmail
2. User clicks on the add-on icon in the sidebar
3. Add-on displays a card with "Generate Draft Reply" button
4. User clicks the button
5. Apps Script extracts email thread and sends to Python backend
6. Backend:
   - Parses the email thread
   - Detects tone (formal/casual) from sender's messages
   - Generates contextual reply using LangChain + OpenAI
   - Returns the draft
7. Add-on displays the draft in the sidebar
8. User clicks "Copy to Reply" to use the draft
9. User reviews, edits if needed, and sends

---

## API Design

### Endpoint: POST /generate-draft

**Request:**
```json
{
  "thread": [
    {
      "from": "sender@example.com",
      "to": "you@gmail.com",
      "date": "2025-01-08T10:00:00Z",
      "subject": "Meeting Tomorrow",
      "body": "Hi, can we meet tomorrow at 3pm to discuss the project?"
    }
  ],
  "user_email": "you@gmail.com",
  "subject": "Meeting Tomorrow"
}
```

**Response:**
```json
{
  "draft": "Hi! Yes, 3pm works great for me. Looking forward to discussing the project. See you then!",
  "detected_tone": "casual",
  "confidence": 0.85
}
```

### Endpoint: GET /health

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## Implementation Phases

### Phase 1: Project Setup
**Goal:** Initialize Python project with UV, create folder structure

**Tasks:**
- [ ] Initialize project with `uv init`
- [ ] Add dependencies (fastapi, pydantic, langchain, etc.)
- [ ] Create folder structure
- [ ] Set up .env.example
- [ ] Create basic README.md

**Dependencies:**
```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
langchain
langchain-openai
python-dotenv
```

---

### Phase 2: Core Backend
**Goal:** Build FastAPI app with Pydantic models and config

**Tasks:**
- [ ] Create `config.py` with Pydantic settings
- [ ] Create `api/schemas.py` with request/response models
- [ ] Create `api/routes.py` with endpoints
- [ ] Create `main.py` FastAPI app
- [ ] Test locally with `uv run uvicorn`

**Files:**
- `src/email_agent/config.py`
- `src/email_agent/api/schemas.py`
- `src/email_agent/api/routes.py`
- `src/email_agent/main.py`

---

### Phase 3: LLM Integration
**Goal:** Implement LangChain + OpenAI for draft generation

**Tasks:**
- [ ] Create prompt templates for draft generation
- [ ] Implement tone detection logic
- [ ] Implement draft generator service
- [ ] Add email parsing utilities
- [ ] Test with sample emails

**Files:**
- `src/email_agent/prompts/templates.py`
- `src/email_agent/services/tone_detector.py`
- `src/email_agent/services/draft_generator.py`
- `src/email_agent/services/email_parser.py`

**Prompt Strategy:**
1. System prompt defines the assistant's role
2. Include full email thread as context
3. Detect tone from sender's messages
4. Generate reply matching detected tone
5. Keep responses concise and natural

---

### Phase 4: Docker Setup
**Goal:** Containerize for local dev and AWS deployment

**Tasks:**
- [ ] Create Dockerfile with UV
- [ ] Create docker-compose.yml for local dev
- [ ] Add volume mounts for hot reload
- [ ] Test container build and run
- [ ] Document Docker commands

**Files:**
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

---

### Phase 5: Google Add-on
**Goal:** Create Gmail sidebar add-on that calls the backend

**Tasks:**
- [ ] Create Google Cloud Project
- [ ] Enable Google Workspace Add-ons API
- [ ] Configure OAuth consent screen (External)
- [ ] Create Apps Script project
- [ ] Implement card UI with button
- [ ] Implement HTTP calls to backend
- [ ] Deploy as test add-on
- [ ] Install on personal Gmail

**Files:**
- `addon/appsscript.json`
- `addon/Code.gs`

**Google Cloud Setup:**
1. Go to console.cloud.google.com
2. Create new project: "Gmail AI Draft Agent"
3. Enable APIs: Google Workspace Add-ons API
4. OAuth consent screen: External, add yourself as test user
5. Create Apps Script, link to Cloud project

---

### Phase 6: Testing & Refinement
**Goal:** End-to-end testing in real Gmail

**Tasks:**
- [ ] Start Docker container
- [ ] Run ngrok to expose localhost
- [ ] Update add-on config with ngrok URL
- [ ] Test with various email types
- [ ] Refine prompts based on output quality
- [ ] Handle edge cases (empty threads, non-English, etc.)

**Test Scenarios:**
- Single email (no thread)
- Long thread (5+ emails)
- Formal business email
- Casual email from friend
- Email with questions to answer
- Email with action items

---

## Future Enhancements (Post-MVP)

| Feature | Description |
|---------|-------------|
| Style learning | Learn user's writing style from sent emails |
| Multiple drafts | Generate 2-3 options to choose from |
| Quick actions | Predefined responses (Accept, Decline, Reschedule) |
| Calendar integration | Check availability when scheduling |
| Attachment awareness | Reference attachments in replies |
| Multi-language | Support non-English emails |
| AWS deployment | Move from ngrok to ECS/Lambda |

---

## Infrastructure Costs

### Development (Free)
| Service | Cost |
|---------|------|
| Gmail account | Free |
| Google Cloud Project | Free tier |
| ngrok | Free tier |
| Docker | Free |

### Production (Minimal)
| Service | Estimated Cost |
|---------|----------------|
| OpenAI API | ~$0.01/email (~$3/month for 300 emails) |
| AWS Lambda | ~$0-2/month (free tier covers most) |
| OR AWS ECS Fargate | ~$5-10/month |

---

## Security Considerations

- API keys stored in .env, never committed
- .env added to .gitignore
- OAuth consent screen in test mode (only you as user)
- HTTPS required for production
- No email content stored/logged
- Backend only accessible via ngrok URL (temporary) or AWS (authenticated)

---

## Commands Reference

### Local Development
```bash
# Start backend
uv run uvicorn src.email_agent.main:app --reload --port 8000

# Start with Docker
docker-compose up --build

# Run ngrok
ngrok http 8000
```

### Testing
```bash
# Run tests
uv run pytest

# Test endpoint manually
curl -X POST http://localhost:8000/generate-draft \
  -H "Content-Type: application/json" \
  -d '{"thread": [...], "user_email": "you@gmail.com", "subject": "Test"}'
```

---

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [Google Workspace Add-ons](https://developers.google.com/workspace/add-ons)
- [Apps Script Reference](https://developers.google.com/apps-script)
- [UV Documentation](https://docs.astral.sh/uv/)
- [OpenAI API](https://platform.openai.com/docs)

---

## Changelog

| Date | Change |
|------|--------|
| 2025-01-08 | Initial plan created |
