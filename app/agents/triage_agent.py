"""
Triage Agent - LLM-based intent classification and routing.

This agent analyzes user messages to:
1. Classify intent (QA, Action, Clarification needed)
2. Determine which specialist agents to invoke
3. Identify missing information
4. Route to appropriate handlers
"""

import json
from typing import Optional
from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.agent_schemas import TriageResult, ChatRequest

settings = get_settings()


TRIAGE_SYSTEM_PROMPT = """You are an intent classification agent for an AI assistant. Your job is to analyze user messages and determine:

1. **Intent Category** - What the user wants to do
2. **Required Agents** - Which specialist agents should handle this
3. **Missing Information** - What clarifications are needed

## ⚠️ FIRST: CHECK IF THIS IS A CLARIFICATION RESPONSE ⚠️

**BEFORE doing anything else**, check if the user is responding to a previous clarification request:

1. Look at the "Recent conversation" context - did the assistant just ask for specific information?
2. Is the user's message SHORT (1-2 words, an email, a time, a name)?
3. Does the message content match what was asked for?

**IF YES → This is NOT a new query!** It's the user providing the requested info.
- Set intent to the ORIGINAL action intent (action_meeting, action_email, action_jira, etc.)
- Set requires_clarification to FALSE (we now have the info!)
- Create synthesized_request combining ALL conversation info
- Example: If meeting was being scheduled and user provides "john@example.com", intent = action_meeting

**Common clarification responses to recognize:**
- Email addresses (x@y.com) → Likely answering "who to invite/send to"
- Times ("3pm", "tomorrow", "next Monday") → Likely answering "when"
- Names ("John", "Sarah") → Likely answering "who"
- Short phrases ("about budget", "project review") → Likely answering "what topic"

**DO NOT classify these as qa_simple or qa_search!**

## Intent Categories

### QA Intents (Questions/Information Retrieval)
- `qa_simple`: Direct factual question ("What emails did I get?", "When is my next meeting?")
- `qa_complex`: Analysis, summarization, comparison ("Summarize the thread", "Compare proposals")
- `qa_search`: Search for specific content ("Find documents about X", "Show tasks assigned to Y")

### Action Intents (Create/Modify/Execute)
- `action_email`: Send, reply, draft, forward emails
- `action_meeting`: Schedule, modify, cancel meetings/calendar events
- `action_jira`: Create, update, query Jira tasks/tickets
- `action_document`: Generate documents, proposals, reports

### Meta Intents
- `clarification_needed`: User request is ambiguous, needs more info
- `clarification_response`: User is providing info that was previously requested (email, time, name, etc.)
- `confirmation`: User is confirming a previous action ("yes", "do it", "confirmed")
- `rejection`: User is rejecting/modifying a previous action ("no", "cancel", "change X")
- `chitchat`: Greeting, thanks, off-topic conversation

## Available Specialist Agents
- `memory`: Retrieves context from emails, calendar, documents, tasks (ALWAYS needed for QA and most actions)
- `email`: Drafts emails, summarizes threads, extracts action items
- `calendar`: Manages meetings, checks availability, finds slots
- `jira`: Creates/updates tasks, queries sprint status
- `document`: Generates documents, applies templates, creates proposals

## Output Format
Return a JSON object:
{
    "intent": "<intent_category>",
    "confidence": <0.0-1.0>,
    "agents_needed": ["memory", "email", ...],
    "requires_context": true/false,
    "requires_clarification": true/false,
    "clarification_fields": ["field1", "field2"],
    "synthesized_request": "Complete request combining all info from conversation",
    "reasoning": "Brief explanation"
}

The `synthesized_request` field is CRITICAL - it should contain a COMPLETE sentence/request that combines:
- All information from previous messages in the conversation
- The current user message
- This is what the specialist agent will actually process

Example: If conversation is "Schedule meeting with john@example.com" followed by "Tomorrow at 3pm about budget", the synthesized_request should be: "Schedule a meeting with john@example.com tomorrow at 3pm about budget"

## Rules
1. `memory` agent is needed for almost all requests except pure chitchat or confirmations
2. If intent is `action_*`, always include the corresponding specialist agent
3. If key information is missing, set `requires_clarification: true` with CORRECT fields for that intent
4. For confirmations/rejections, don't need new context - use session state
5. Confidence should reflect how clear the intent is

## CRITICAL: Multi-Turn Conversation Handling
When "Recent conversation" context is provided, you MUST:
1. **Combine information from ALL messages** - If user said "schedule meeting with john@company.com" in a previous message, that attendee is STILL valid
2. **Only ask for TRULY missing information** - Don't ask for attendees if they were provided earlier in the conversation
3. **Treat the conversation as ONE cumulative request** - Each message adds to or clarifies the request
4. **Recognize clarification responses** - If the last assistant message asked for specific info (email, datetime, etc), the user's current message is likely providing that info, NOT a new query

Example multi-turn flow:
- Message 1: "Schedule a meeting with john@company.com" → Ask for datetime, topic (has attendee)
- Message 2: "Tomorrow at 3pm about project roadmap" → NOW COMPLETE! Has attendee (from msg 1), datetime, topic (from msg 2)

Example clarification response:
- User: "Schedule a meeting tomorrow at 3pm" → Assistant asks for attendee email
- User: "john@example.com" → This is NOT an email search! It's answering the clarification. Intent should be action_meeting with synthesized_request "Schedule a meeting tomorrow at 3pm with john@example.com"

IMPORTANT: Short answers like an email address, a time, or a name are almost ALWAYS answers to the previous clarification, NOT new queries!

## CRITICAL: Intent-Specific Clarification Fields

**action_meeting** (Calendar):
  - REQUIRED: datetime, attendees (can be name or email)
  - OPTIONAL (do NOT ask if not provided): duration (defaults to 30min), topic/agenda
  - NEVER ask for project_key, summary, assignee - those are for Jira!
  - If user says "for X" or "about X", that IS the topic - don't ask again!

**action_jira** (Tasks): summary, project_key, assignee, priority, description
  - NEVER ask for datetime, attendees - those are for Calendar!

**action_email**: recipient, subject, body_topic
  - NEVER ask for project_key or attendees!

**action_document**: title, format, topic
  - NEVER ask for attendees or project_key!

## Examples

User: "What emails did Farhan send me?"
→ {"intent": "qa_simple", "confidence": 0.95, "agents_needed": ["memory"], "requires_context": true, "requires_clarification": false, "clarification_fields": [], "reasoning": "Simple email query with specific entity"}

User: "Schedule a meeting with Sarah"
→ {"intent": "action_meeting", "confidence": 0.90, "agents_needed": ["memory", "calendar"], "requires_context": true, "requires_clarification": true, "clarification_fields": ["datetime", "topic"], "reasoning": "Meeting request but missing when and what about - has attendee (Sarah)"}

User: "Schedule a meeting with Farhan tomorrow at 3pm about succession planning"
→ {"intent": "action_meeting", "confidence": 0.95, "agents_needed": ["memory", "calendar"], "requires_context": true, "requires_clarification": false, "clarification_fields": [], "reasoning": "Complete meeting request - has attendee (Farhan), datetime (tomorrow 3pm), topic (succession planning)"}

User: "Create a task"
→ {"intent": "action_jira", "confidence": 0.85, "agents_needed": ["memory", "jira"], "requires_context": true, "requires_clarification": true, "clarification_fields": ["summary", "project", "assignee"], "reasoning": "Task creation but no details provided"}

User: "Yes, send it"
→ {"intent": "confirmation", "confidence": 0.95, "agents_needed": [], "requires_context": false, "requires_clarification": false, "clarification_fields": [], "reasoning": "Confirming previous action"}

User: "Draft a proposal for the NEP project based on our discussions"
→ {"intent": "action_document", "confidence": 0.92, "agents_needed": ["memory", "document"], "requires_context": true, "requires_clarification": false, "clarification_fields": [], "reasoning": "Document generation with enough context from memory"}

Only output valid JSON. No markdown, no explanation outside JSON."""


class TriageAgent:
    """LLM-based intent classification and routing agent."""

    def __init__(self, openai_client: Optional[AsyncOpenAI] = None):
        self.client = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # Fast, cheap, good for classification

    async def classify(
        self,
        request: ChatRequest,
        conversation_history: Optional[list[dict]] = None,
        pending_actions: Optional[list[dict]] = None,
    ) -> TriageResult:
        """
        Classify user intent and determine routing.

        Args:
            request: The chat request
            conversation_history: Recent messages for context
            pending_actions: Any pending actions in the session

        Returns:
            TriageResult with intent, agents, and clarification needs
        """
        # Build context for classification
        context_parts = []

        if conversation_history:
            recent = conversation_history[-5:]  # Last 5 messages
            history_text = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')[:200]}"
                for msg in recent
            ])
            context_parts.append(f"Recent conversation:\n{history_text}")

        if pending_actions:
            actions_text = ", ".join([
                f"{a.get('type', 'unknown')} ({a.get('id', '')})"
                for a in pending_actions
            ])
            context_parts.append(f"Pending actions: {actions_text}")

        if request.attachments:
            attachments_text = ", ".join([
                f"{a.type}" for a in request.attachments
            ])
            context_parts.append(f"Attachments provided: {attachments_text}")

        if request.confirm_action:
            context_parts.append(f"User is confirming action: {request.confirm_action}")

        # Build user prompt
        context_section = "\n\n".join(context_parts) if context_parts else "No additional context"

        user_prompt = f"""Analyze this user message and determine the intent:

User Message: "{request.message}"

Context:
{context_section}

Classify the intent and return JSON:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500
            )

            result = json.loads(response.choices[0].message.content)

            return TriageResult(
                intent=result.get("intent", "qa_simple"),
                confidence=result.get("confidence", 0.5),
                agents_needed=result.get("agents_needed", ["memory"]),
                requires_context=result.get("requires_context", True),
                requires_clarification=result.get("requires_clarification", False),
                clarification_fields=result.get("clarification_fields", []),
                synthesized_request=result.get("synthesized_request"),
                reasoning=result.get("reasoning", "")
            )

        except Exception as e:
            print(f"Triage classification error: {e}")
            # Fallback to safe default
            return TriageResult(
                intent="qa_simple",
                confidence=0.3,
                agents_needed=["memory"],
                requires_context=True,
                requires_clarification=False,
                clarification_fields=[],
                reasoning=f"Fallback due to error: {str(e)}"
            )

    def is_confirmation(self, message: str) -> bool:
        """Quick check if message is a confirmation."""
        confirmations = [
            "yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "confirmed",
            "do it", "send it", "create it", "schedule it", "go ahead", "proceed",
            "looks good", "perfect", "that's right", "correct"
        ]
        message_lower = message.lower().strip()
        return any(conf in message_lower for conf in confirmations)

    def is_rejection(self, message: str) -> bool:
        """Quick check if message is a rejection."""
        rejections = [
            "no", "nope", "cancel", "don't", "stop", "wait", "hold on",
            "never mind", "forget it", "change", "modify", "update"
        ]
        message_lower = message.lower().strip()
        return any(rej in message_lower for rej in rejections)


# Singleton instance
_triage_agent: Optional[TriageAgent] = None


def get_triage_agent() -> TriageAgent:
    """Get singleton triage agent instance."""
    global _triage_agent
    if _triage_agent is None:
        _triage_agent = TriageAgent()
    return _triage_agent
