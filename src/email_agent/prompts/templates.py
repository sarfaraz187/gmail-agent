"""Prompt templates for email draft generation."""

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
6. Does NOT include a signature or sign-off (this will be added automatically)

User's email: {user_email}

Email Thread (oldest to newest):
{thread_text}

Write a reply to the most recent email. The reply should:
- Start with an appropriate greeting (e.g., "Hi John," or "Dear John,")
- Address the content naturally
- Be written in {tone} tone
- Be concise (2-4 sentences for simple emails, more if needed for complex topics)
- Do NOT end with a sign-off like "Best regards" or "Thanks" - the signature is added separately

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
