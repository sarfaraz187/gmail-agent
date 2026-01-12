# Gmail AI Agent

An autonomous AI agent for Gmail that automatically responds to emails based on content classification. The agent watches for emails you label "Agent Respond" and either auto-replies or marks them for your review.

## Features

- **Autonomous Email Processing**: Automatically responds to simple emails (meeting requests, acknowledgments, scheduling)
- **Smart Classification**: Uses pattern matching to detect when your input is needed (budget decisions, contracts, choices)
- **Gmail Integration**: Full Gmail API integration with push notifications via Pub/Sub
- **Event-Driven**: Instant processing via Gmail push notifications (~1-5 seconds)
- **Label-Based Control**: You control what the agent handles by applying labels
- **Tone Matching**: Detects and matches the tone of incoming emails (formal/casual)
- **Multi-Language Support**: Detects email language for appropriate responses
- **Signature Support**: Automatically appends your signature from config

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. You apply "Agent Respond" label to an email                 │
│                           ↓                                     │
│  2. Gmail sends push notification to Cloud Run                  │
│                           ↓                                     │
│  3. Agent classifies the email:                                 │
│     • AUTO_RESPOND → Generate draft, send reply, mark "Done"    │
│     • NEEDS_INPUT  → Mark as "Agent Pending" for your review    │
└─────────────────────────────────────────────────────────────────┘
```

### Gmail Labels

| Label | Purpose | Applied By |
|-------|---------|------------|
| `Agent Respond` | Agent should handle this email | You (manually) |
| `Agent Done` | Agent has processed and replied | Agent (auto) |
| `Agent Pending` | Waiting for your decision | Agent (auto) |

### Classification Categories

**Auto-Respond (agent handles):**
- Meeting confirmations
- Simple acknowledgments
- Scheduling requests
- Follow-up questions

**Needs Your Input (marked pending):**
- Budget/money decisions ($X amounts)
- Binary choices (Option A or B)
- Contracts and legal matters
- Commitments and deadlines
- Sensitive/urgent topics

## Quick Start

### Prerequisites

- Python 3.12+
- [UV](https://github.com/astral-sh/uv) package manager
- Google Cloud Platform account
- OpenAI API key

### Local Development

1. **Clone and install:**
   ```bash
   git clone https://github.com/sarfaraz187/gmail-agent.git
   cd gmail-agent
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Configure user settings:**
   ```bash
   # Edit config.yaml with your email and signature
   ```

4. **Run locally:**
   ```bash
   uv run uvicorn src.email_agent.main:app --reload --port 8000
   ```

5. **For webhook testing, use ngrok:**
   ```bash
   ngrok http 8000
   ```

### GCP Deployment

See [PLAN.md](PLAN.md) for detailed deployment instructions. Quick overview:

1. **Enable GCP APIs:**
   ```bash
   gcloud services enable run.googleapis.com \
     artifactregistry.googleapis.com \
     secretmanager.googleapis.com \
     pubsub.googleapis.com \
     gmail.googleapis.com
   ```

2. **Set up OAuth and get refresh token:**
   ```bash
   python scripts/gmail_auth.py
   ```

3. **Store secrets:**
   ```bash
   echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-
   echo -n "your-refresh-token" | gcloud secrets create gmail-refresh-token --data-file=-
   ```

4. **Build and deploy:**
   ```bash
   gcloud builds submit --tag europe-west1-docker.pkg.dev/PROJECT_ID/email-agent/email-agent
   gcloud run deploy email-agent \
     --image europe-west1-docker.pkg.dev/PROJECT_ID/email-agent/email-agent:latest \
     --region europe-west1 \
     --allow-unauthenticated \
     --set-secrets="OPENAI_API_KEY=openai-api-key:latest,GMAIL_REFRESH_TOKEN=gmail-refresh-token:latest"
   ```

5. **Set up Gmail labels:**
   ```bash
   python scripts/setup_gmail_labels.py
   ```

6. **Set up Pub/Sub and Gmail watch:**
   ```bash
   # Create topic and subscription
   gcloud pubsub topics create gmail-agent
   gcloud pubsub subscriptions create gmail-agent-sub \
     --topic=gmail-agent \
     --push-endpoint=https://YOUR-SERVICE-URL/webhook/gmail

   # Start Gmail watch
   curl -X POST https://YOUR-SERVICE-URL/renew-watch
   ```

## Configuration

### Environment Variables (.env)

```bash
OPENAI_API_KEY=sk-...           # Required: OpenAI API key
OPENAI_MODEL=gpt-4o-mini        # Optional: Model to use (default: gpt-4o-mini)
GCP_PROJECT=your-project-id     # Required for GCP deployment
```

### User Settings (config.yaml)

```yaml
user:
  email: "your@email.com"
  signature: |
    Best regards,
    Your Name

preferences:
  default_tone: "professional"

  # Always ask before responding to these senders
  always_notify_senders:
    - "ceo@company.com"
    - "legal@company.com"

  # Types of emails to auto-respond
  auto_respond_types:
    - "meeting_confirmation"
    - "simple_acknowledgment"
    - "scheduling_request"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhook/gmail` | POST | Gmail push notification handler |
| `/renew-watch` | POST | Renew Gmail watch (call every 6 days) |
| `/watch-status` | GET | Check Gmail watch status |
| `/generate-draft` | POST | Manual draft generation |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Google Cloud Platform                                               │
│                                                                      │
│  Gmail API → Pub/Sub → Cloud Run (email-agent)                      │
│                              │                                       │
│                              ├── Classifier (pattern matching)       │
│                              ├── Draft Generator (OpenAI LLM)        │
│                              ├── Gmail Client (send/labels)          │
│                              └── History Tracker (Firestore)         │
│                                                                      │
│  Secret Manager: API keys, OAuth tokens                             │
│  Cloud Scheduler: Watch renewal (every 6 days)                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
email_agent/
├── src/email_agent/
│   ├── api/
│   │   ├── routes.py          # Manual API endpoints
│   │   ├── webhook.py         # Gmail webhook handler
│   │   └── schemas.py         # Pydantic models
│   ├── agent/
│   │   └── classifier.py      # Email classification logic
│   ├── gmail/
│   │   ├── client.py          # Gmail API client
│   │   ├── labels.py          # Label management
│   │   └── watch.py           # Gmail watch setup
│   ├── services/
│   │   ├── draft_generator.py # LLM draft generation
│   │   └── tone_detector.py   # Tone detection
│   ├── storage/
│   │   └── history_tracker.py # Firestore history tracking
│   ├── config.py              # Environment settings
│   └── user_config.py         # YAML config loading
├── tests/                     # 125 unit tests
├── scripts/                   # Setup scripts
├── config.yaml                # User configuration
├── Dockerfile                 # Multi-stage Docker build
└── PLAN.md                    # Detailed project plan
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/email_agent --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_classifier.py -v
```

Current status: **125 tests passing**

## Monitoring

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=email-agent" --limit=50

# Check agent status
curl https://YOUR-SERVICE-URL/health
curl https://YOUR-SERVICE-URL/watch-status
```

## Cost Estimate

| Service | Monthly Cost |
|---------|--------------|
| Cloud Run | $0-10 (free tier covers most usage) |
| Pub/Sub | $0-1 |
| OpenAI API | $5-20 (depends on volume) |
| **Total** | **~$5-30/month** |

## Security

- API keys stored in Secret Manager (never in code)
- OAuth2 with refresh token for Gmail access
- Gmail watch only on specific label (not all emails)
- No email content stored long-term
- HTTPS everywhere

## Roadmap

- [x] Phase 1-4: Core backend and Gmail Add-on
- [x] Phase 5: Testing (100% coverage)
- [x] Phase 6: GCP Deployment
- [x] Phase 7: Gmail Push Notifications
- [x] Phase 8: Decision Classification
- [x] Phase 10: Auto-respond Flow
- [ ] Phase 11: Memory System (style learning)
- [ ] Phase 12: Agent Tools (calendar, contacts)
- [ ] Phase 13: LangGraph Agent
- [ ] Phase 14: Feedback Loop

## License

MIT

## Contributing

Contributions welcome! Please read the [PLAN.md](PLAN.md) for architecture details.
