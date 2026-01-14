"""
Prompts for the LangGraph agent.

Contains prompt templates used by agent nodes for LLM interactions.
"""

# =============================================================================
# TOOL PLANNING PROMPT
# =============================================================================
# Used by the PLAN node to determine which tools to call.
# The LLM analyzes the email and returns a JSON response with tool calls.

TOOL_PLANNING_PROMPT = """You are an email assistant analyzing an incoming email to decide if any tools are needed to respond effectively.

=== EMAIL TO RESPOND TO ===
From: {sender_email}
Subject: {subject}

Body:
{body}

=== THREAD CONTEXT (previous emails in this thread) ===
{thread_context}

=== AVAILABLE TOOLS ===
{tools_description}

=== YOUR TASK ===
Analyze this email and decide which tools (if any) would help craft a better response.

Guidelines:
- If the email mentions scheduling, meeting times, or availability -> use "calendar_check" with appropriate start_date
- If the email references a previous conversation, proposal, document, or asks "did you see/get my email" -> use "search_emails" with a relevant query
- If you need contact details to personalize the response -> use "lookup_contact"
- Many simple emails need NO tools (acknowledgments, thank yous, confirmations)
- Only call tools that will provide genuinely useful information

For calendar_check:
- start_date can be: "tomorrow", "next Monday", "2024-01-15", etc.
- end_date is optional, defaults to same day

For search_emails:
- query uses Gmail search syntax: "from:email", "subject:text", free text, etc.
- max_results defaults to 5

For lookup_contact:
- query can be email address or name

=== RESPONSE FORMAT ===
Respond with ONLY a JSON object (no other text):
{{
    "reasoning": "Brief explanation of your analysis",
    "tools": [
        {{"name": "tool_name", "args": {{"param": "value"}}}}
    ]
}}

If no tools are needed, return an empty tools array:
{{
    "reasoning": "This is a simple acknowledgment email, no additional information needed",
    "tools": []
}}

=== EXAMPLES ===

Email: "Can we meet next Thursday afternoon?"
Response:
{{
    "reasoning": "Email asks about meeting availability for next Thursday",
    "tools": [{{"name": "calendar_check", "args": {{"start_date": "next Thursday"}}}}]
}}

Email: "Did you review the proposal I sent last week?"
Response:
{{
    "reasoning": "Email references a previous proposal, need to find it",
    "tools": [{{"name": "search_emails", "args": {{"query": "from:{sender_email} proposal"}}}}]
}}

Email: "Thanks for the update, sounds good!"
Response:
{{
    "reasoning": "Simple acknowledgment, no additional information needed",
    "tools": []
}}

Email: "Can we reschedule our Friday meeting to next week? Also, did you get my budget document?"
Response:
{{
    "reasoning": "Email asks about rescheduling (need calendar) and references a budget document (need email search)",
    "tools": [
        {{"name": "calendar_check", "args": {{"start_date": "next Monday", "end_date": "next Friday"}}}},
        {{"name": "search_emails", "args": {{"query": "from:{sender_email} budget"}}}}
    ]
}}

JSON Response:"""


# =============================================================================
# DRAFT GENERATION WITH TOOLS PROMPT (Future enhancement)
# =============================================================================
# Could be used for more sophisticated tool-aware draft generation.
# Currently, tool context is injected into the email body for the standard prompt.

DRAFT_GENERATION_PROMPT_WITH_TOOLS = """You are an AI assistant that drafts email replies.

=== USER INFO ===
User's email: {user_email}

=== TOOL RESULTS (use this information in your response) ===
{tool_context}

=== EMAIL THREAD (oldest to newest) ===
{thread_text}

Write a reply that:
1. Uses the tool results to provide accurate, helpful information
2. Matches the {tone} tone of the conversation
3. Is concise and natural-sounding
4. Does NOT include a signature (added automatically)
5. Does NOT mention that you used tools or are an AI

Draft Reply:"""
