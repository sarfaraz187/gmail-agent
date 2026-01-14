# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn src.email_agent.main:app --reload --port 8000

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/email_agent --cov-report=html

# Run a specific test file
uv run pytest tests/unit/test_classifier.py -v

# Run a single test by name
uv run pytest tests/unit/test_classifier.py::test_detects_budget_approval -v
```

## Architecture Overview

This is an autonomous Gmail AI agent that processes emails via Gmail push notifications, using a LangGraph state machine for processing.

### Core Processing Flow

```
Gmail Label Applied ("Agent Respond")
    ↓
Pub/Sub Push Notification → /webhook/gmail endpoint
    ↓
LangGraph Agent (see graph below)
    ↓
AUTO_RESPOND: Send reply → Mark "Agent Done"
NEEDS_INPUT: Mark "Agent Pending" for user review
```

### LangGraph Agent Graph

The agent uses a state machine defined in `agent/graph.py`:

```
CLASSIFY → (AUTO_RESPOND) → PLAN → (has tools) → EXECUTE → WRITE → SEND → END
                                 → (no tools)  → WRITE → SEND → END
         → (NEEDS_INPUT)  → NOTIFY → END
```

**Nodes (`agent/nodes/`):**
- `classify` - Runs pattern-based classifier to determine AUTO_RESPOND vs NEEDS_INPUT
- `plan` - LLM decides which tools (calendar, contacts, email_search) to invoke
- `execute` - Runs the planned tools via `ToolRegistry`
- `write` - LLM generates draft response using tool results and contact memory
- `send` - Sends email via Gmail API, applies "Done" label
- `notify` - Applies "Pending" label for user review

**State (`agent/state.py`):**
`AgentState` TypedDict flows through nodes, accumulating: `classification` → `tools_to_call` → `tool_results` → `draft_body` → `outcome`

### Key Modules

- **`api/webhook.py`**: Entry point for Gmail notifications. Creates `AgentState` and invokes the graph.
- **`agent/graph.py`**: LangGraph state machine definition with routing functions.
- **`agent/classifier.py`**: Pattern-based classification using `DECISION_REQUIRED_PATTERNS` and `AUTO_RESPOND_PATTERNS`.
- **`tools/`**: Agent tools (calendar, email_search, contacts) with `ToolRegistry` for LLM function calling. Tools extend `BaseTool` abstract class.
- **`services/draft_generator.py`**: LLM-based draft generation with memory integration.
- **`gmail/client.py`**: Gmail API wrapper for thread fetching, sending, and label management.
- **`storage/contact_memory.py`**: Firestore-backed contact memory for style learning.

### Classification Logic

The classifier in `agent/classifier.py` uses two pattern sets:
1. **DECISION_REQUIRED_PATTERNS** - Triggers user review: money, choices, commitments, sensitive topics
2. **AUTO_RESPOND_PATTERNS** - Safe for auto-reply: meeting requests, acknowledgments, scheduling

Priority: `always_notify_senders` (config) > decision patterns > auto-respond patterns > default to pending

### Configuration

- **`.env`**: Secrets (OPENAI_API_KEY, GCP_PROJECT)
- **`config.yaml`**: User preferences (signature, always_notify_senders, auto_respond_types)
- **`src/email_agent/config.py`**: Pydantic settings loaded from environment

## Testing Strategy

### Must Test (Critical for Safety)
- No-reply detection patterns (`should_skip_sender`)
- Decision classifier patterns (prevents unauthorized auto-replies)
- Idempotency via label checking (prevents duplicate sends)
- Pub/Sub webhook payload parsing
- Agent node functions (each node in `agent/nodes/`)
- Tool execution and registry

### Skip Testing
- LLM output quality (can't reliably test)
- Gmail/OpenAI API internals (mock these)
- Framework behavior (FastAPI routing, Pydantic validation)

### Mocking Rules
Always mock: Gmail API, OpenAI calls, Firestore
Never mock: Pattern matching, business logic functions, data transformations

## Code Conventions

- Type hints on all function signatures
- `pathlib.Path` for file paths
- `logging` module instead of `print`
- Constants in UPPER_SNAKE_CASE
- Singleton pattern for services (e.g., `email_classifier`, `tool_registry`, `graph`)
- Tools extend `BaseTool` with `name`, `description`, `parameters_schema`, and `execute()` method
