# Project Rules - Gmail AI Agent

## Testing Strategy

### Critical Tests (MUST Have)

These components can cause **real damage** if they fail:

| Component | Why Critical | Test Focus |
|-----------|--------------|------------|
| **No-Reply Detection** | Responding to noreply@ creates bounce loops | All `NEVER_RESPOND_PATTERNS` match correctly |
| **Decision Classifier** | Wrong classification = unauthorized auto-reply | `DECISION_REQUIRED_PATTERNS` detect money, choices, commitments |
| **Always-Notify Senders** | CEO/legal emails must never auto-reply | Sender matching works regardless of case/format |
| **Idempotency Check** | Double-processing = duplicate emails sent | Label check prevents reprocessing |
| **Webhook Payload Parsing** | Bad parsing = missed emails | Base64 decoding, historyId extraction |

### Important Tests (Should Have)

These affect functionality but won't cause damage:

| Component | Test Focus |
|-----------|------------|
| **Tone Detection Fallback** | Invalid LLM response defaults to "formal" |
| **Thread Formatting** | Missing fields handled gracefully |
| **History ID Logic** | New emails fetched correctly, none missed |
| **Reply Threading** | threadId, In-Reply-To, References headers set |
| **Signature Appending** | Config signature added to drafts |

### Skip These Tests (DO NOT Write)

| Component | Why Skip |
|-----------|----------|
| **LLM Output Quality** | Can't reliably test "good" drafts - that's prompt engineering |
| **Gmail API Calls** | Mock the SDK, don't test Google's code |
| **OpenAI API Calls** | Mock responses, don't test LangChain internals |
| **Pydantic Validation** | Framework already tested - just verify schema exists |
| **FastAPI Routing** | Don't test that routes register - test the handler logic |
| **Config Loading** | Don't test that .env loads - test what happens with values |
| **Logging Statements** | No value in testing log output |

### Test Examples

**GOOD Test (Decision Classifier):**
```python
def test_detects_budget_approval_request():
    """Budget emails must trigger user notification."""
    email = "Can you approve the $5000 marketing budget?"
    assert classifier.needs_decision(email) == True

def test_skips_noreply_sender():
    """Never respond to automated senders."""
    assert should_skip_sender("noreply@company.com") == True
    assert should_skip_sender("no-reply@newsletter.io") == True
    assert should_skip_sender("mailer-daemon@gmail.com") == True
```

**BAD Test (Don't Write):**
```python
def test_openai_returns_response():
    """Tests that OpenAI SDK works - NOT OUR CODE."""
    response = openai.chat.completions.create(...)
    assert response is not None  # Useless

def test_fastapi_route_exists():
    """Tests framework behavior - NOT OUR LOGIC."""
    assert "/health" in app.routes  # Useless
```

### When to Add Tests

| Scenario | Add Test? |
|----------|-----------|
| New pattern in `DECISION_REQUIRED_PATTERNS` | YES - verify it matches |
| New sender in `ALWAYS_NOTIFY_SENDERS` | NO - just config data |
| New webhook endpoint | YES - test payload parsing |
| Change LLM prompt | NO - can't test output quality |
| New Gmail label | NO - just a string constant |
| New error handling path | YES - verify graceful recovery |

### Mocking Rules

```python
# ALWAYS mock these:
- Gmail API client (google-api-python-client)
- OpenAI/LangChain LLM calls
- Firestore/database calls
- External HTTP requests

# NEVER mock these:
- Your own business logic functions
- Pattern matching (regex)
- Data transformations
```

---

## Code Style

- Type hints on all function signatures
- Use `pathlib.Path` for file paths
- Use `logging` module, not `print`
- Constants in UPPER_SNAKE_CASE

---

## Architecture

All decisions documented in `PLAN.md` → "Critical Design Decisions" section.
