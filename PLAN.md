# Gmail AI Agent - Project Plan

## Overview

A **true AI agent** for Gmail that autonomously handles email replies with memory, tool use, planning, and continuous learning. The agent:

- **Watches** for emails you label "Agent Respond"
- **Decides** if it can auto-reply or needs your input
- **Remembers** your writing style and preferences
- **Uses tools** to check calendar, search past emails, lookup contacts
- **Notifies you** when a decision is required before responding
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
│       │                     │  → Notify user, wait         │            │
│       ▼                     └──────────────────────────────┘            │
│  Gmail sends push                         │                             │
│  notification instantly                   ▼                             │
│  (~1-5 seconds)             ┌──────────────────────────────┐            │
│                             │  NOTIFICATION SYSTEM          │            │
│                             │  (Telegram / Email / Slack)   │            │
│                             └──────────────────────────────┘            │
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
│  │  └── OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, etc.                   │    │
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
           │  Execute      │          │  Notify User  │
           │  Tools        │          │  (Telegram)   │
           │  (calendar,   │          │               │
           │   search)     │          │  "Sarah asks: │
           └───────┬───────┘          │   Option A    │
                   │                  │   or B?"      │
                   ▼                  └───────┬───────┘
           ┌───────────────┐                  │
           │  Generate     │                  ▼
           │  Draft        │          ┌───────────────┐
           └───────┬───────┘          │  Wait for     │
                   │                  │  User Input   │
                   ▼                  └───────┬───────┘
           ┌───────────────┐                  │
           │  SEND EMAIL   │                  ▼
           │  via Gmail    │          ┌───────────────┐
           │  API          │          │  User sends   │
           └───────┬───────┘          │  "Option A"   │
                   │                  └───────┬───────┘
                   ▼                          │
           ┌───────────────┐                  ▼
           │  Add label:   │          ┌───────────────┐
           │  "Agent Done" │          │  Generate     │
           └───────────────┘          │  Response     │
                                      │  with decision│
                                      └───────┬───────┘
                                              │
                                              ▼
                                      ┌───────────────┐
                                      │  SEND EMAIL   │
                                      └───────────────┘
```

---

## Decision Classification

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
| **Vector Store** | **ChromaDB** | Memory: style learning |
| **Event Trigger** | **Cloud Pub/Sub** | Gmail push notifications |
| **Hosting** | **Cloud Run** | Serverless container |
| **Notifications** | **Telegram Bot** | Decision requests to user |
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
│       ├── notifications/          # NEW: Notification system
│       │   ├── __init__.py
│       │   ├── telegram.py         # Telegram bot
│       │   ├── email_notify.py     # Email notifications
│       │   └── handler.py          # User response handler
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

### Webhook: POST /webhook/telegram

Receives user decisions from Telegram.

**Request:**
```json
{
  "update_id": 123456789,
  "message": {
    "text": "Option A",
    "chat": { "id": 123456 },
    "reply_to_message": {
      "text": "Sarah asks: Option A or B for the budget?"
    }
  }
}
```

**Agent then:**
1. Matches to pending decision
2. Generates response with user's choice
3. Sends email via Gmail API

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

### Phase 5: GCP Deployment Setup
**Goal:** Deploy to Cloud Run with proper infrastructure

**Tasks:**
- [ ] Create Dockerfile optimized for Cloud Run
- [ ] Set up Artifact Registry for container images
- [ ] Create Cloud Run service
- [ ] Configure Secret Manager for API keys
- [ ] Set up custom domain (optional)

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
  people.googleapis.com
```

---

### Phase 6: Gmail Push Notifications
**Goal:** Event-driven email processing via Pub/Sub

**Tasks:**
- [ ] Create Pub/Sub topic for Gmail notifications
- [ ] Grant Gmail API publish permissions
- [ ] Create push subscription to Cloud Run
- [ ] Implement `/webhook/gmail` endpoint
- [ ] Set up Gmail watch on "Agent Respond" label
- [ ] Create watch renewal job (every 7 days)

**New Files:**
- `src/email_agent/api/webhook.py`
- `src/email_agent/gmail/watch.py`
- `src/email_agent/gmail/client.py`
- `scripts/setup_pubsub.sh`

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
```

---

### Phase 7: Decision Classification
**Goal:** Detect when user decision is required

**Tasks:**
- [ ] Create decision classifier module
- [ ] Define decision-required patterns
- [ ] Implement classification logic
- [ ] Add CLASSIFY node to agent graph
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

### Phase 8: Notification System (Telegram)
**Goal:** Notify user and receive decisions via Telegram

**Tasks:**
- [ ] Create Telegram bot via BotFather
- [ ] Implement Telegram notification sender
- [ ] Implement `/webhook/telegram` endpoint
- [ ] Create decision queue (pending decisions)
- [ ] Match user replies to pending decisions
- [ ] Test full notification flow

**New Files:**
- `src/email_agent/notifications/telegram.py`
- `src/email_agent/notifications/handler.py`

**Telegram Flow:**
```
Agent → Telegram Bot → User's Phone
                            ↓
                      User replies
                            ↓
Telegram → Webhook → Agent → Send Email
```

---

### Phase 9: Gmail Send & Label Management
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

### Phase 10: Memory System
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

### Phase 11: Agent Tools
**Goal:** Calendar, contacts, email search tools

**Tasks:**
- [ ] Implement calendar_check tool
- [ ] Implement search_emails tool
- [ ] Implement lookup_contact tool
- [ ] Create tool registry
- [ ] Integrate with agent graph

---

### Phase 12: LangGraph Agent
**Goal:** Full agent with planning and routing

**Tasks:**
- [ ] Define complete agent state
- [ ] Implement all nodes
- [ ] Add conditional routing
- [ ] Test complex scenarios

---

### Phase 13: Feedback Loop
**Goal:** Learn from user corrections

**Tasks:**
- [ ] Track when user edits before sending
- [ ] Store correction patterns
- [ ] Update style model

---

### Phase 14: Advanced Features
**Goal:** Polish and enhance

**Tasks:**
- [ ] Multiple draft options
- [ ] Quick action buttons
- [ ] Dashboard for stats
- [ ] Multi-language support

---

## Current Status

```
Phase 1: Project Setup        [████████████] 100% ✅
Phase 2: Core Backend         [████████████] 100% ✅
Phase 3: Basic LLM            [████████████] 100% ✅
Phase 4: Google Add-on        [████████████] 100% ✅
Phase 5: GCP Deployment       [░░░░░░░░░░░░]   0%  ← NEXT
Phase 6: Gmail Push           [░░░░░░░░░░░░]   0%
Phase 7: Decision Classifier  [░░░░░░░░░░░░]   0%
Phase 8: Telegram Notify      [░░░░░░░░░░░░]   0%
Phase 9: Gmail Send/Labels    [░░░░░░░░░░░░]   0%
Phase 10: Memory System       [░░░░░░░░░░░░]   0%
Phase 11: Agent Tools         [░░░░░░░░░░░░]   0%
Phase 12: LangGraph Agent     [░░░░░░░░░░░░]   0%
Phase 13: Feedback Loop       [░░░░░░░░░░░░]   0%
Phase 14: Advanced Features   [░░░░░░░░░░░░]   0%
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

### Scenario 2: Decision Required (Notify User)

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
[NOTIFY] Send Telegram message:
         "📧 Sarah asks about marketing budget:
          A) $10,000 social media
          B) $15,000 mixed media

          Reply A or B"
[LABEL] Add "Agent Pending"
[WAIT] ...

USER RESPONDS (via Telegram): "B"

AGENT RESUMES:
[EXECUTE] No tools needed
[WRITE] Generate response with choice B
[SEND] "Hi Sarah, let's go with Option B - the $15,000 mixed media
        campaign. The broader reach will be valuable. Please proceed
        with that budget. Thanks!"
[LABEL] Add "Agent Done", remove "Agent Pending"
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
| Telegram Bot | Free |
| **Total** | **~$5-30/month** |

---

## Security Considerations

- API keys in Secret Manager (never in code)
- Service account with minimal permissions
- Gmail watch only on specific label (not all emails)
- No email content stored long-term
- Telegram bot only responds to your chat ID
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
| 2025-01-11 | **Added event-driven architecture with Gmail Push + Pub/Sub** |
| 2025-01-11 | **Added label-based control ("Agent Respond")** |
| 2025-01-11 | **Added decision classification and Telegram notifications** |
