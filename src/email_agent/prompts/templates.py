"""Prompt templates for email draft generation."""

# =============================================================================
# Style Analysis Prompt (for learning from sent emails)
# =============================================================================

STYLE_ANALYSIS_PROMPT = """Analyze this sent email to extract the writer's style preferences.

Email sent to: {recipient_email}
Recipient name: {recipient_name}

Email body:
{sent_body}

Previous thread context (if any):
{thread_context}

Extract and return as JSON:
{{
    "tone": "formal" or "casual",
    "greeting_used": "the exact greeting used, e.g., 'Hi John,' or 'Dear Mr. Smith,' or empty if none",
    "formality_score": 0.0 to 1.0 (0 = very casual, 1 = very formal),
    "response_length": "short" (1-2 sentences), "medium" (3-5 sentences), or "long" (6+ sentences),
    "topics_discussed": ["list", "of", "main", "topics", "max 3"]
}}

JSON Response:"""


# =============================================================================
# Memory-Enhanced Draft Generation Prompt
# =============================================================================

DRAFT_GENERATION_PROMPT_WITH_MEMORY = """You are an AI assistant that drafts email replies. Your task is to write a reply that matches the user's established communication style with this specific contact.

=== USER INFO ===
User's email: {user_email}

=== RECIPIENT INFO ===
Recipient: {recipient_name} ({recipient_email})

=== CONTACT MEMORY (learned from past emails) ===
Preferred tone with this contact: {tone}
Formality level: {formality_score}/1.0
Typical greeting: {greeting_preference}
Response length preference: {response_length}
Recent topics discussed: {recent_topics}

=== EMAIL THREAD (oldest to newest) ===
{thread_text}

Write a reply to the most recent email. The reply should:
- Use greeting style similar to: {greeting_preference} (or appropriate variation)
- Match the {tone} tone (formality: {formality_score}/1.0)
- Target {response_length} length
- Reference relevant prior topics if naturally applicable
- Address all points in the latest email
- IMPORTANT: End with the last sentence of your message. Do NOT add any closing like "Kind regards", "Best regards", "Thanks", "Cheers", "Sincerely", etc. The signature is added separately.

Draft Reply:"""


# =============================================================================
# Tone Detection Prompt
# =============================================================================

TONE_DETECTION_PROMPT = """Analyze the following email messages and determine the overall tone of the conversation.

Email Thread:
{thread_text}

Based on the sender's writing style, classify the tone as one of:
- "formal" (professional, business-like, uses full sentences, proper greetings)
- "casual" (friendly, relaxed, may use contractions, informal greetings)

Respond with ONLY a JSON object in this exact format:
{{"tone": "formal" or "casual", "confidence": 0.0 to 1.0}}

JSON Response:"""

DRAFT_GENERATION_PROMPT = """You are an AI assistant that drafts email replies. Your task is to write a reply that:
1. Matches the tone of the conversation ({tone})
2. Addresses all points/questions in the most recent email
3. Is concise and natural-sounding
4. Does NOT include a subject line
5. Does NOT include email headers (To, From, etc.)
6. Does NOT include any signature, sign-off, or closing (this will be added automatically)

User's email: {user_email}

Email Thread (oldest to newest):
{thread_text}

Write a reply to the most recent email. The reply should:
- Start with an appropriate greeting (e.g., "Hi John," or "Dear John,")
- Address the content naturally
- Be written in {tone} tone
- Be concise (2-4 sentences for simple emails, more if needed for complex topics)
- IMPORTANT: End with the last sentence of your message. Do NOT add any closing like "Kind regards", "Best regards", "Thanks", "Cheers", "Sincerely", etc. The signature is added separately.

Draft Reply:"""


def format_thread_for_prompt(thread: list[dict]) -> str:
    """Format email thread into readable text for prompts."""
    formatted_messages = []

    for i, msg in enumerate(thread, 1):
        from_addr = msg.get("from_") or msg.get("from", "Unknown")
        formatted = f"""--- Email {i} ---
                    From: {from_addr}
                    To: {msg.get("to", "Unknown")}
                    Date: {msg.get("date", "Unknown")}
                    Subject: {msg.get("subject", "No Subject")}

                    {msg.get("body", "")}
                    """
        formatted_messages.append(formatted)

    return "\n".join(formatted_messages)
