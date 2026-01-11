# Gmail AI Agent - Project Plan

## Overview

A **true AI agent** for Gmail that autonomously handles email replies with memory, tool use, planning, and continuous learning. The agent:

- **Watches** for emails you label "Agent Respond"
- **Decides** if it can auto-reply or needs your input
- **Remembers** your writing style and preferences
- **Uses tools** to check calendar, search past emails, lookup contacts
- **Labels emails** as "Agent Pending" when your decision is required
- **Learns** from your corrections to improve over time

---

## Operation Modes

### Label-Based Autonomous Control

```
┌─────────────────────────────────────────────────────────────────────┐
│  YOUR GMAIL INBOX                                                    │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ ★ Meeting request from John           [Agent Respond]          │ │
│  │   "Can we meet Thursday?"                                      │ │
│  │                                                                │ │
│  │   → Agent checks calendar                                      │ │
│  │   → Auto-sends: "Thursday works! See you then."               │ │
│  │   → Adds label: [Agent Done ✓]                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ ★ Contract question from Sarah        [Agent Respond]          │ │
│  │   "Should we go with Option A or B for the budget?"           │ │
│  │                                                                │ │
│  │   → Agent detects: DECISION REQUIRED                          │ │
│  │   → Notifies you: "Sarah asks: Option A or B?"                │ │
│  │   → Waits for your input                                      │ │
│  │   → You reply: "Option A"                                     │ │
│  │   → Agent sends response with your decision                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │   Newsletter from TechCrunch          (no label)               │ │
│  │                                                                │ │
│  │   → Agent IGNORES completely                                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Gmail Labels Used

| Label | Purpose | Who Applies |
|-------|---------|-------------|
| `Agent Respond` | Agent should handle this email | You (manually) |
| `Agent Done` | Agent has processed this email | Agent (auto) |
| `Agent Pending` | Waiting for your decision | Agent (auto) |

---

## What Makes This an Agent (vs. Simple LLM Tool)

| Capability | Simple Tool | This Agent |
|------------|-------------|------------|
| **Autonomy** | Waits for button click | Responds automatically to labeled emails |
| **Event-Driven** | Manual trigger only | Instant reaction via Gmail Push |
| **Memory** | Stateless | Remembers style, preferences, context |
| **Tools** | None | Calendar, email search, contacts |
| **Planning** | Single prompt→response | Multi-step reasoning |
| **Decision Detection** | None | Knows when to ask you first |
| **Learning** | Static prompts | Improves from feedback |

---

## Architecture

### Event-Driven Flow (Gmail Push Notifications)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EVENT-DRIVEN ARCHITECTURE                                               │
│                                                                          │
│  ┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Gmail   │───▶│  Cloud      │───▶│  Cloud Run  │───▶│   Gmail     │  │
│  │  Watch   │    │  Pub/Sub    │    │  Agent      │    │   Send      │  │
│  └──────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│       │                                    │                             │
│       │                                    ▼                             │
│  You add label              ┌──────────────────────────────┐            │
│  "Agent Respond"            │  Agent Decision:             │            │
│       │                     │                              │            │
│       │                     │  Simple email?               │            │
│       │                     │  → Auto-respond immediately  │            │
│       │                     │                              │            │
│       │                     │  Decision required?          │            │
│       │                     │  → Add "Agent Pending" label │            │
│       ▼                     └──────────────────────────────┘            │
│  Gmail sends push                                                       │
│  notification instantly     You check Gmail for "Agent Pending"        │
│  (~1-5 seconds)             emails when convenient                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Detailed System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GOOGLE CLOUD PLATFORM                                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Gmail API                                                       │    │
│  │  └── watch() on label "Agent Respond"                           │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                 │ Push notification                      │
│                                 ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Cloud Pub/Sub                                                   │    │
│  │  └── Topic: gmail-agent-notifications                           │    │
│  │      └── Subscription: push to Cloud Run                        │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                 │ HTTP POST                              │
│                                 ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Cloud Run: email-agent                                          │    │
│  │                                                                  │    │
│  │  ┌────────────────────────────────────────────────────────────┐ │    │
│  │  │  /webhook/gmail  ←── Receives Pub/Sub push                 │ │    │
│  │  │       │                                                     │ │    │
│  │  │       ▼                                                     │ │    │
│  │  │  ┌──────────────────────────────────────────────────────┐  │ │    │
│  │  │  │  AGENT CORE (LangGraph)                              │  │ │    │
│  │  │  │                                                      │  │ │    │
│  │  │  │  ANALYZE → CLASSIFY → PLAN → EXECUTE → WRITE/NOTIFY │  │ │    │
│  │  │  └──────────────────────────────────────────────────────┘  │ │    │
│  │  │       │                                                     │ │    │
│  │  │       ├── Memory (ChromaDB / Firestore)                    │ │    │
│  │  │       ├── Tools (Calendar, Contacts, Search)               │ │    │
│  │  │       └── LLM (OpenAI GPT-4o)                              │ │    │
│  │  └────────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Secret Manager                                                  │    │
│  │  └── OPENAI_API_KEY, GMAIL_REFRESH_TOKEN, etc.                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Cloud Firestore (optional)                                      │    │
│  │  └── Persistent memory, user preferences, decision queue        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Agent Decision Flow

```
                         ┌─────────────────┐
                         │  Gmail Webhook  │
                         │  (new labeled   │
                         │   email)        │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    ANALYZE      │
                         │    Email        │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   CLASSIFY      │
                         │   Decision      │
                         │   Required?     │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
           ┌───────────────┐          ┌───────────────┐
           │  NO DECISION  │          │   DECISION    │
           │  NEEDED       │          │   REQUIRED    │
           └───────┬───────┘          └───────┬───────┘
                   │                          │
                   ▼                          ▼
           ┌───────────────┐          ┌───────────────┐
           │  Execute      │          │  Add label:   │
           │  Tools        │          │  "Agent       │
           │  (calendar,   │          │   Pending"    │
           │   search)     │          └───────┬───────┘
           └───────┬───────┘                  │
                   │                          ▼
                   ▼                  ┌───────────────┐
           ┌───────────────┐          │  WAIT         │
           │  Generate     │          │  User checks  │
           │  Draft        │          │  Gmail later  │
           └───────┬───────┘          │  and replies  │
                   │                  └───────┬───────┘
                   ▼                          │
           ┌───────────────┐                  │
           │  SEND EMAIL   │          (Manual reply   │
           │  via Gmail    │           by user for    │
           │  API          │           MVP - future:  │
           └───────┬───────┘           agent drafts)  │
                   │                          │
                   ▼                          │
           ┌───────────────┐                  │
           │  Add label:   │                  │
           │  "Agent Done" │                  │
           └───────────────┘                  ▼
                                      ┌───────────────┐
                                      │  Done         │
                                      └───────────────┘
```

---

## Decision Classification

### Email Processing Rules

| Rule | Behavior |
|------|----------|
| **Thread Context** | Always read the FULL email thread (use `threads.get()`), not just the latest message |
| **Language Matching** | Reply in the SAME language as the incoming email (GPT-4o auto-detects) |
| **Attachments** | Ignore completely - don't mention or process them |
| **Auto-Reply Detection** | Never respond to noreply@, mailer-daemon, out-of-office, etc. |

---

### What the Agent Auto-Handles

| Email Type | Example | Agent Action |
|------------|---------|--------------|
| Meeting confirmation | "Can we meet Thursday?" | Check calendar → respond |
| Simple acknowledgment | "Thanks for the update" | Send acknowledgment |
| Info request (known) | "What's the project status?" | Respond with known info |
| Scheduling | "When are you free?" | Check calendar → offer times |
| Follow-up | "Did you get my email?" | Acknowledge + respond |

### What Requires Your Decision

| Email Type | Example | Agent Action |
|------------|---------|--------------|
| Binary choice | "Option A or Option B?" | **NOTIFY** → wait for choice |
| Money/Budget | "Can you approve $5000?" | **NOTIFY** → wait for approval |
| Commitments | "Can you deliver by Friday?" | **NOTIFY** → wait for confirmation |
| Contracts | "Please sign this agreement" | **NOTIFY** → wait for decision |
| Sensitive topics | Keywords: urgent, confidential | **NOTIFY** → wait for guidance |
| Ambiguous requests | Can't determine clear response | **NOTIFY** → ask for clarification |

### Decision Detection Logic

```python
DECISION_REQUIRED_PATTERNS = [
    # Binary choices
    r"option [a-z] or (option )?[a-z]",
    r"which (one|option|choice)",
    r"do you prefer",
    r"should (we|i)",

    # Money/Approval
    r"\$\d+",
    r"budget",
    r"approve",
    r"cost",
    r"price",

    # Commitments
    r"can you (commit|promise|guarantee)",
    r"deadline",
    r"deliver by",

    # Sensitive
    r"confidential",
    r"urgent",
    r"asap",
    r"legal",
    r"contract",
    r"agreement",
]

ALWAYS_NOTIFY_SENDERS = [
    "ceo@company.com",
    "legal@company.com",
]

# NEVER auto-respond to these (skip entirely)
NEVER_RESPOND_PATTERNS = [
    r"noreply@",
    r"no-reply@",
    r"donotreply@",
    r"do-not-reply@",
    r"mailer-daemon@",
    r"postmaster@",
    r"^auto-reply",
    r"out of office",
    r"automatic reply",
    r"away from.*office",
]
```

---

## Critical Design Decisions

### 1. Gmail Authentication (OAuth2 with Refresh Token)

Since Cloud Run needs to access your Gmail, we use OAuth2 with a stored refresh token.

**How it works:**
```
┌─────────────────────────────────────────────────────────────────┐
│  ONE-TIME SETUP (Local)                                          │
│                                                                  │
│  1. Run auth script locally                                      │
│  2. Browser opens → You login to Google                         │
│  3. Grant permissions (read, send, modify labels)               │
│  4. Script saves refresh_token                                  │
│  5. Upload refresh_token to Secret Manager                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  RUNTIME (Cloud Run)                                             │
│                                                                  │
│  1. Cloud Run fetches refresh_token from Secret Manager         │
│  2. Uses refresh_token to get access_token                      │
│  3. access_token used for Gmail API calls                       │
│  4. access_token auto-refreshes (handled by Google SDK)         │
└─────────────────────────────────────────────────────────────────┘
```

**Files needed:**
- `scripts/gmail_auth.py` - One-time OAuth flow
- Secret Manager: `gmail-refresh-token`

**Required OAuth Scopes:**
```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]
```

---

### 2. Watch Renewal (Cloud Scheduler)

Gmail watch expires every 7 days. Cloud Scheduler auto-renews it.

**Setup:**
```bash
# Create Cloud Scheduler job
gcloud scheduler jobs create http gmail-watch-renewal \
  --location=europe-west1 \
  --schedule="0 0 */6 * *" \
  --uri="https://email-agent-xxxxx.run.app/renew-watch" \
  --http-method=POST \
  --oidc-service-account-email=SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com
```

**Endpoint:**
```
POST /renew-watch
→ Calls gmail.users().watch() to renew
→ Returns new expiration date
```

---

### 3. Idempotency (Gmail Labels)

Pub/Sub may deliver duplicate notifications. We prevent double-processing using Gmail labels.

**Logic:**
```python
def should_process_email(email_id: str) -> bool:
    """Check if email should be processed."""
    email = gmail.users().messages().get(userId='me', id=email_id).execute()
    labels = email.get('labelIds', [])

    # Skip if already processed or pending
    if 'AGENT_DONE' in labels or 'AGENT_PENDING' in labels:
        return False

    # Only process if has "Agent Respond" label
    if 'AGENT_RESPOND' not in labels:
        return False

    return True
```

**No external database needed** - Gmail itself tracks state.

---

### 4. Error Handling (Logging Only - MVP)

For MVP, errors are logged. Enhanced error handling planned for later.

**Current approach:**
```python
try:
    process_email(email_id)
except Exception as e:
    logger.error(f"Failed to process email {email_id}: {e}")
    # TODO: Add Telegram notification for critical errors
    # TODO: Add "Agent Error" label to email
```

**Future enhancements (Post-MVP):**
- [ ] Retry with exponential backoff
- [ ] Telegram notification on failure
- [ ] "Agent Error" label for failed emails
- [ ] Dead letter queue for persistent failures

---

### 5. Pending Decision Timeout (Logging Only - MVP)

For MVP, pending decisions wait indefinitely. Timeout logic planned for later.

**Current approach:**
- Agent adds "Agent Pending" label
- Waits for user to check Gmail and respond (no timeout)

**Future enhancements (Post-MVP):**
- [ ] Reminder after 4 hours
- [ ] Auto-expire after 24 hours
- [ ] Mark as "skipped" and notify user

---

### 6. User Preferences (config.yaml)

User preferences stored in a separate YAML file for easy editing.

**File: `config.yaml`**
```yaml
user:
  email: "your@email.com"
  signature: |
    Best regards,
    Mohammed Sarfaraz

preferences:
  default_tone: "formal"

  # Always ask user before responding to these senders
  always_notify_senders:
    - "ceo@company.com"
    - "legal@company.com"

  # Types of emails to auto-respond without asking
  auto_respond_types:
    - "meeting_confirmation"
    - "simple_acknowledgment"
    - "scheduling_request"
```

**Loading in Python:**
```python
import yaml
from pathlib import Path

def load_config() -> dict:
    config_path = Path("config.yaml")
    if config_path.exists():
        return yaml.safe_load(config_path.read_text())
    return {}
```

**Why config.yaml (not .env):**
- Clean separation: secrets in `.env`, preferences in `config.yaml`
- YAML supports nested structures and lists
- Easy to edit without touching sensitive credentials
- Can be version controlled (unlike .env with secrets)

---

### 7. Email Signature (From config.yaml)

Agent appends your signature to all outgoing emails.

**Configuration (config.yaml):**
```yaml
user:
  signature: |
    Best regards,
    Mohammed Sarfaraz
```

**Usage in draft generation:**
```python
def generate_email_body(draft: str, config: dict) -> str:
    signature = config.get("user", {}).get("signature", "")
    if signature:
        return f"{draft}\n\n--\n{signature}"
    return draft
```

---

### 8. Rate Limiting (Error Handling)

For personal use, rate limits are unlikely to be hit. Handle gracefully if they occur.

**Approach:**
```python
from google.api_core.exceptions import ResourceExhausted

try:
    gmail.users().messages().send(...)
except ResourceExhausted:
    logger.warning("Rate limit hit, waiting 60 seconds...")
    time.sleep(60)
    # Retry once
    gmail.users().messages().send(...)
```

**Future enhancements (if needed):**
- [ ] Cloud Tasks queue for throttling
- [ ] Exponential backoff

---

### 9. Notifications (Gmail Labels Only - MVP)

For MVP, no push notifications. Use Gmail labels to track pending decisions.

**MVP Approach:**
```
┌─────────────────────────────────────────────────────────────────┐
│  DECISION REQUIRED?                                              │
│                                                                  │
│  1. Agent adds "Agent Pending" label                            │
│  2. You check Gmail periodically for "Agent Pending" emails     │
│  3. You reply manually                                          │
│  4. You remove "Agent Pending" label (or agent auto-removes)    │
└─────────────────────────────────────────────────────────────────┘
```

**Why skip Telegram for MVP:**
- Simpler architecture (no webhook handling for user responses)
- No extra bot setup required
- Gmail already has push notifications on mobile
- You can filter/star "Agent Pending" emails

**Future enhancement (Post-MVP):**
- Telegram bot for instant notifications
- Reply directly from Telegram to provide decisions
- Agent drafts response with your input

---

### 10. History ID Tracking

Gmail push notifications include a `historyId`. We must track the last processed history ID to avoid missing emails between notifications.

**Storage:** Firestore (simple key-value)

**Logic:**
```python
def get_new_emails_since_last_check(history_id: int) -> list:
    """Fetch emails changed since last known history ID."""
    # Get last processed history ID from Firestore
    last_history_id = firestore.get("last_history_id") or history_id

    # Fetch history changes
    history = gmail.users().history().list(
        userId='me',
        startHistoryId=last_history_id,
        labelId='AGENT_RESPOND'
    ).execute()

    # Update stored history ID
    firestore.set("last_history_id", history_id)

    # Return new message IDs
    return extract_new_message_ids(history)
```

**Why this matters:**
- Pub/Sub notifications only say "something changed" with a historyId
- Without tracking, you might miss emails if multiple arrive quickly
- Gmail's history API lets you catch up on any missed changes

---

### 11. Thread Replies (Automatic)

Replies are automatically threaded correctly using Gmail API.

**Implementation:**
```python
def create_reply(original_message: dict, reply_body: str) -> dict:
    """Create a properly threaded reply."""
    return {
        "threadId": original_message["threadId"],
        "raw": create_message_raw(
            to=extract_sender(original_message),
            subject=f"Re: {original_message['subject']}",
            body=reply_body,
            in_reply_to=original_message["Message-ID"],
            references=original_message["Message-ID"],
        )
    }
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.12 | Backend development |
| Package Manager | UV | Fast, modern Python tooling |
| API Framework | FastAPI | HTTP endpoints |
| Validation | Pydantic | Request/response models |
| **Agent Framework** | **LangGraph** | State machine, planning, tools |
| LLM Provider | OpenAI GPT-4o | Draft generation, reasoning |
| **Vector Store** | **ChromaDB** (future) | Memory: style learning |
| **Event Trigger** | **Cloud Pub/Sub** | Gmail push notifications |
| **Hosting** | **Cloud Run** | Serverless container |
| **Notifications** | Gmail Labels (MVP) | "Agent Pending" for decisions |
| Gmail Integration | Gmail API | Watch, read, send emails |
| Calendar | Google Calendar API | Check availability |
| Contacts | Google People API | Contact lookup |
| Secrets | Secret Manager | API keys storage |

---

## Project Structure

```
email_agent/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
├── PLAN.md
│
├── src/
│   └── email_agent/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app
│       ├── config.py               # Settings
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py           # Manual endpoints
│       │   ├── webhook.py          # NEW: Pub/Sub webhook handler
│       │   └── schemas.py          # Request/response models
│       │
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── graph.py            # LangGraph state machine
│       │   ├── state.py            # Agent state definition
│       │   ├── classifier.py       # NEW: Decision classifier
│       │   └── nodes/
│       │       ├── __init__.py
│       │       ├── analyze.py
│       │       ├── classify.py     # NEW: Decision classification
│       │       ├── plan.py
│       │       ├── execute.py
│       │       ├── notify.py       # NEW: User notification
│       │       └── write.py
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── calendar.py
│       │   ├── email_search.py
│       │   ├── contacts.py
│       │   └── gmail.py            # NEW: Gmail send/label
│       │
│       │
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── store.py
│       │   ├── style_learner.py
│       │   └── feedback.py
│       │
│       ├── gmail/                  # NEW: Gmail integration
│       │   ├── __init__.py
│       │   ├── watch.py            # Set up Gmail watch
│       │   ├── client.py           # Gmail API client
│       │   └── labels.py           # Label management
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── tone_detector.py
│       │   └── draft_generator.py
│       │
│       └── prompts/
│           ├── __init__.py
│           └── templates.py
│
├── addon/                          # Still works for manual use
│   ├── appsscript.json
│   └── Code.gs
│
├── data/
│   └── chroma/
│
├── scripts/                        # NEW: Deployment scripts
│   ├── setup_pubsub.sh
│   ├── setup_gmail_watch.py
│   └── deploy.sh
│
└── tests/
    ├── __init__.py
    ├── test_api.py
    ├── test_agent.py
    ├── test_classifier.py          # NEW
    └── test_webhook.py             # NEW
```

---

## API Design

### Webhook: POST /webhook/gmail

Receives Pub/Sub push notifications from Gmail.

**Request (from Pub/Sub):**
```json
{
  "message": {
    "data": "eyJlbWFpbEFkZHJlc3MiOiJ1c2VyQGdtYWlsLmNvbSIsImhpc3RvcnlJZCI6MTIzNDU2fQ==",
    "messageId": "123456789",
    "publishTime": "2025-01-11T10:00:00Z"
  }
}
```

**Decoded data:**
```json
{
  "emailAddress": "user@gmail.com",
  "historyId": 123456
}
```

**Agent then:**
1. Fetches email changes using `history.list()`
2. Processes new labeled emails
3. Decides: auto-respond or notify

---

### Endpoint: POST /generate-draft (Manual)

Still works for Gmail Add-on (manual button click).

---

### Endpoint: GET /status

Check agent status and pending decisions.

**Response:**
```json
{
  "status": "active",
  "gmail_watch": {
    "expiration": "2025-01-18T10:00:00Z",
    "label_id": "Label_123456"
  },
  "pending_decisions": [
    {
      "email_id": "abc123",
      "from": "sarah@client.com",
      "question": "Option A or B?",
      "waiting_since": "2025-01-11T09:30:00Z"
    }
  ],
  "stats": {
    "emails_processed_today": 12,
    "auto_responded": 10,
    "decisions_requested": 2
  }
}
```

---

## Implementation Phases

### Phase 1: Project Setup ✅ COMPLETED
- [x] Initialize project with UV
- [x] Add dependencies
- [x] Create folder structure
- [x] Set up .env.example

### Phase 2: Core Backend ✅ COMPLETED
- [x] Create config.py with Pydantic settings
- [x] Create API schemas
- [x] Create API routes
- [x] Create FastAPI main.py

### Phase 3: Basic LLM Integration ✅ COMPLETED
- [x] Create prompt templates
- [x] Implement tone detection
- [x] Implement draft generator

### Phase 4: Google Add-on ✅ COMPLETED
- [x] Create Google Cloud Project
- [x] Configure OAuth
- [x] Create Apps Script add-on
- [x] Connect to backend via ngrok

---

### Phase 5: Testing Setup ✅ COMPLETED
**Goal:** Comprehensive test coverage before deployment

**Tasks:**
- [x] Add test dependencies to pyproject.toml
- [x] Create test configuration (conftest.py)
- [x] Create sample email fixtures
- [x] Unit tests for tone detector
- [x] Unit tests for draft generator
- [ ] Unit tests for decision classifier (when built)
- [x] API endpoint tests (health, generate-draft)
- [x] Mock external services (OpenAI, Gmail API)

**Results:** 24 tests passing, 100% code coverage

**Dependencies:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.27.0",
    "respx>=0.21.0",
]
```

**Test Structure:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── fixtures/
│   └── sample_emails.json   # Test email data
├── unit/
│   ├── __init__.py
│   ├── test_tone_detector.py
│   └── test_draft_generator.py
└── api/
    ├── __init__.py
    └── test_routes.py
```

**Run Tests:**
```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=src/email_agent --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_tone_detector.py -v
```

---

### Phase 6: GCP Deployment
**Goal:** Deploy to Cloud Run with proper infrastructure

**Tasks:**
- [ ] Create Dockerfile optimized for Cloud Run
- [ ] Set up Artifact Registry for container images
- [ ] Create Cloud Run service
- [ ] Configure Secret Manager for API keys
- [ ] Create OAuth2 credentials in GCP Console
- [ ] Run `scripts/gmail_auth.py` locally to get refresh token
- [ ] Store refresh token in Secret Manager
- [ ] Set up custom domain (optional)

**New Files:**
- `Dockerfile`
- `scripts/gmail_auth.py` - OAuth2 flow to get refresh token
- `src/email_agent/gmail/auth.py` - Load credentials from Secret Manager

**GCP Services:**
```bash
# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  pubsub.googleapis.com \
  gmail.googleapis.com \
  calendar-json.googleapis.com \
  people.googleapis.com \
  cloudscheduler.googleapis.com
```

**OAuth2 Setup:**
1. Go to GCP Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download `credentials.json`
4. Run: `python scripts/gmail_auth.py`
5. Store refresh token: `gcloud secrets create gmail-refresh-token --data-file=token.json`

---

### Phase 7: Gmail Push Notifications
**Goal:** Event-driven email processing via Pub/Sub

**Tasks:**
- [ ] Create Pub/Sub topic for Gmail notifications
- [ ] Grant Gmail API publish permissions
- [ ] Create push subscription to Cloud Run
- [ ] Implement `/webhook/gmail` endpoint
- [ ] Implement `/renew-watch` endpoint
- [ ] Set up Gmail watch on "Agent Respond" label
- [ ] Create Cloud Scheduler job for watch renewal (every 6 days)
- [ ] Create Gmail labels: "Agent Respond", "Agent Done", "Agent Pending"
- [ ] Implement history ID tracking (Firestore) to avoid missing emails
- [ ] Implement full thread fetching (`threads.get()` instead of `messages.get()`)

**New Files:**
- `src/email_agent/api/webhook.py`
- `src/email_agent/gmail/watch.py`
- `src/email_agent/gmail/client.py`
- `src/email_agent/gmail/labels.py`
- `scripts/setup_pubsub.sh`
- `scripts/setup_scheduler.sh`

**Setup Commands:**
```bash
# Create Pub/Sub topic
gcloud pubsub topics create gmail-agent

# Grant Gmail permission to publish
gcloud pubsub topics add-iam-policy-binding gmail-agent \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

# Create push subscription
gcloud pubsub subscriptions create gmail-agent-sub \
  --topic=gmail-agent \
  --push-endpoint=https://email-agent-xxxxx.run.app/webhook/gmail

# Create Cloud Scheduler for watch renewal (every 6 days)
gcloud scheduler jobs create http gmail-watch-renewal \
  --location=europe-west1 \
  --schedule="0 0 */6 * *" \
  --uri="https://email-agent-xxxxx.run.app/renew-watch" \
  --http-method=POST \
  --oidc-service-account-email=SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com
```

---

### Phase 8: Decision Classification
**Goal:** Detect when user decision is required

**Tasks:**
- [ ] Create decision classifier module
- [ ] Define decision-required patterns
- [ ] Implement no-reply/auto-reply detection (skip these emails entirely)
- [ ] Implement classification logic
- [ ] Add CLASSIFY node to agent graph
- [ ] Add language detection for response generation
- [ ] Test with sample emails

**New Files:**
- `src/email_agent/agent/classifier.py`
- `src/email_agent/agent/nodes/classify.py`

**Decision Categories:**
```python
class DecisionType(Enum):
    AUTO_RESPOND = "auto"      # Agent handles fully
    NEEDS_CHOICE = "choice"    # User picks A/B/C
    NEEDS_APPROVAL = "approve" # User approves/rejects
    NEEDS_INPUT = "input"      # User provides info
```

---

### Phase 9: Notification System (FUTURE - Post MVP)
**Goal:** Add push notifications when agent needs decisions

**Status:** SKIPPED FOR MVP - Using Gmail labels instead

**MVP Approach:**
- Agent adds "Agent Pending" label to emails needing decisions
- User checks Gmail for "Agent Pending" emails periodically
- User replies manually to pending emails

**Future Options (Post-MVP):**
- [ ] Telegram bot for push notifications
- [ ] Email notification to separate address
- [ ] Slack integration
- [ ] Mobile app notifications

---

### Phase 10: Gmail Send & Label Management
**Goal:** Agent can send emails and manage labels

**Tasks:**
- [ ] Implement Gmail send functionality
- [ ] Create "Agent Done" and "Agent Pending" labels
- [ ] Implement label add/remove functions
- [ ] Add proper OAuth scopes for send/modify
- [ ] Test auto-response flow

**New Files:**
- `src/email_agent/gmail/labels.py`
- `src/email_agent/tools/gmail.py`

**Required Gmail Scopes:**
```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",  # For labels
]
```

---

### Phase 11: Memory System
**Goal:** Persistent memory for style and preferences

**Tasks:**
- [ ] Set up ChromaDB or Firestore
- [ ] Implement style learning
- [ ] Store contact-specific preferences
- [ ] Create memory retrieval for drafts

**New Files:**
- `src/email_agent/memory/store.py`
- `src/email_agent/memory/style_learner.py`

---

### Phase 12: Agent Tools
**Goal:** Calendar, contacts, email search tools

**Tasks:**
- [ ] Implement calendar_check tool
- [ ] Implement search_emails tool
- [ ] Implement lookup_contact tool
- [ ] Create tool registry
- [ ] Integrate with agent graph

---

### Phase 13: LangGraph Agent
**Goal:** Full agent with planning and routing

**Tasks:**
- [ ] Define complete agent state
- [ ] Implement all nodes
- [ ] Add conditional routing
- [ ] Test complex scenarios

---

### Phase 14: Feedback Loop
**Goal:** Learn from user corrections

**Tasks:**
- [ ] Track when user edits before sending
- [ ] Store correction patterns
- [ ] Update style model

---

### Phase 15: Advanced Features
**Goal:** Polish and enhance

**Tasks:**
- [ ] Multiple draft options
- [ ] Quick action buttons
- [ ] Dashboard for stats
- [ ] Multi-language support

---

## Current Status

```
Phase 1:  Project Setup       [████████████] 100% ✅
Phase 2:  Core Backend        [████████████] 100% ✅
Phase 3:  Basic LLM           [████████████] 100% ✅
Phase 4:  Google Add-on       [████████████] 100% ✅
Phase 5:  Testing Setup       [████████████] 100% ✅
Phase 6:  GCP Deployment      [░░░░░░░░░░░░]   0%  ← NEXT
Phase 7:  Gmail Push          [░░░░░░░░░░░░]   0%
Phase 8:  Decision Classifier [░░░░░░░░░░░░]   0%
Phase 9:  Notifications       [──────SKIP──] MVP (future)
Phase 10: Gmail Send/Labels   [░░░░░░░░░░░░]   0%
Phase 11: Memory System       [░░░░░░░░░░░░]   0%
Phase 12: Agent Tools         [░░░░░░░░░░░░]   0%
Phase 13: LangGraph Agent     [░░░░░░░░░░░░]   0%
Phase 14: Feedback Loop       [░░░░░░░░░░░░]   0%
Phase 15: Advanced Features   [░░░░░░░░░░░░]   0%
```

---

## Example Scenarios

### Scenario 1: Simple Meeting Request (Auto-Respond)

```
INPUT EMAIL:
From: john@company.com
Subject: Quick sync?
Label: [Agent Respond]

"Hey, can we do a quick call Thursday afternoon?"

AGENT EXECUTION:
[ANALYZE] Meeting request, Thursday afternoon
[CLASSIFY] → AUTO_RESPOND (simple scheduling)
[EXECUTE] calendar_check("Thursday PM") → Free 2-5pm
[WRITE] Generate response
[SEND] "Hey John! Thursday afternoon works great. How about 3pm? Talk soon!"
[LABEL] Add "Agent Done", remove "Agent Respond"

TIME: ~3 seconds total
```

### Scenario 2: Decision Required (Agent Pending)

```
INPUT EMAIL:
From: sarah@client.com
Subject: Budget approval needed
Label: [Agent Respond]

"Hi, we need to decide on the marketing budget.
Option A: $10,000 for social media focus
Option B: $15,000 for mixed media campaign
Which would you prefer?"

AGENT EXECUTION:
[ANALYZE] Budget decision, two options, money involved
[CLASSIFY] → NEEDS_CHOICE (binary choice + money)
[LABEL] Add "Agent Pending", remove "Agent Respond"
[DONE] Agent stops - waiting for user

USER LATER:
- Checks Gmail for "Agent Pending" label
- Sees Sarah's email needs a decision
- Replies manually: "Hi Sarah, let's go with Option B..."
- Removes "Agent Pending" label

FUTURE ENHANCEMENT:
- Telegram notification for instant alerts
- Agent drafts response after user provides choice
```

### Scenario 3: Complex Email (Multiple Tools)

```
INPUT EMAIL:
From: mike@partner.com
Subject: Re: Project Phoenix
Label: [Agent Respond]

"Can we reschedule our Friday meeting to next week?
Also, did you review the proposal I sent last Tuesday?"

AGENT EXECUTION:
[ANALYZE] Reschedule request + follow-up question
[CLASSIFY] → AUTO_RESPOND (scheduling + info lookup)
[PLAN] Need: calendar, email_search
[EXECUTE]
  - calendar_check("next week") → Free Mon 10am, Wed 2pm, Thu all day
  - search_emails("proposal from:mike") → Found "Project Phoenix Proposal" from Jan 7
[RECALL] Style with mike: casual, past topics: Project Phoenix
[WRITE] Generate comprehensive response
[SEND] "Hey Mike! Sure, let's push to next week. I'm free Monday
        morning, Wednesday afternoon, or pretty much all day Thursday.

        And yes, I reviewed the proposal you sent on the 7th - looks
        solid! I have a few thoughts on the timeline that we can
        discuss in our call.

        Let me know what works!"
[LABEL] Add "Agent Done"
```

---

## Infrastructure Costs (GCP)

### Development (Free Tier)
| Service | Cost |
|---------|------|
| Cloud Run | 2M requests/month free |
| Pub/Sub | 10GB/month free |
| Secret Manager | 6 secrets free |
| Gmail API | Free |
| Calendar API | Free |

### Production (Estimated)
| Service | Monthly Cost |
|---------|--------------|
| Cloud Run | $0-10 |
| Pub/Sub | $0-1 |
| OpenAI API | $5-20 |
| **Total** | **~$5-30/month** |

---

## Security Considerations

- API keys in Secret Manager (never in code)
- Service account with minimal permissions
- Gmail watch only on specific label (not all emails)
- No email content stored long-term
- Cloud Run with authentication for sensitive endpoints
- HTTPS everywhere

---

## Commands Reference

### Local Development
```bash
# Start backend
uv run uvicorn src.email_agent.main:app --reload --port 8000

# Run ngrok (for testing webhooks locally)
ngrok http 8000
```

### GCP Deployment
```bash
# Build and push container
gcloud builds submit --tag gcr.io/PROJECT_ID/email-agent

# Deploy to Cloud Run
gcloud run deploy email-agent \
  --image gcr.io/PROJECT_ID/email-agent \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated

# Set up Gmail watch
python scripts/setup_gmail_watch.py
```

### Monitoring
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision"

# Check agent status
curl https://your-agent.run.app/status
```

---

## Resources

- [Gmail Push Notifications](https://developers.google.com/gmail/api/guides/push)
- [Cloud Pub/Sub](https://cloud.google.com/pubsub/docs)
- [Cloud Run](https://cloud.google.com/run/docs)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Gmail API](https://developers.google.com/gmail/api)

---

## Changelog

| Date | Change |
|------|--------|
| 2025-01-08 | Initial plan created |
| 2025-01-11 | Phase 1-4 completed (basic working tool) |
| 2025-01-11 | Plan upgraded to true AI agent architecture |
| 2025-01-11 | Added event-driven architecture with Gmail Push + Pub/Sub |
| 2025-01-11 | Added label-based control ("Agent Respond") |
| 2025-01-11 | Added decision classification and Telegram notifications |
| 2025-01-11 | **Added Critical Design Decisions section** |
| 2025-01-11 | **Decided: OAuth2 with Refresh Token for Gmail auth** |
| 2025-01-11 | **Decided: Cloud Scheduler for watch renewal** |
| 2025-01-11 | **Decided: Gmail Labels for idempotency** |
| 2025-01-11 | **Decided: Logging only for error handling (MVP)** |
| 2025-01-11 | **Decided: Config file for email signature** |
| 2025-01-11 | **Decided: Skip Telegram for MVP - use Gmail labels only** |
| 2026-01-11 | **Added: Email Processing Rules (thread context, language, attachments)** |
| 2026-01-11 | **Added: History ID tracking requirement** |
| 2026-01-11 | **Added: No-reply/auto-reply detection patterns** |
| 2026-01-11 | **Rule: Must read FULL email thread before responding** |
| 2026-01-11 | **Rule: Reply in same language as incoming email** |
| 2026-01-11 | **Rule: Ignore attachments completely** |
| 2026-01-11 | **Decided: config.yaml for user preferences (not .env)** |
| 2026-01-11 | **Phase 5 Completed: Testing Setup (24 tests, 100% coverage)** |
