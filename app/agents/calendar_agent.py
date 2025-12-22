"""
Calendar Agent - Meeting scheduling and calendar management.

Handles:
- Creating meetings
- Finding available time slots
- Checking for conflicts
- Getting upcoming events
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.agent_schemas import (
    Action,
    AgentOutput,
    ClarificationQuestion,
    MemoryContext,
)

settings = get_settings()


CALENDAR_SYSTEM_PROMPT = """You are a calendar and meeting specialist agent. Your job is to:
1. Schedule meetings based on user requests
2. Find appropriate time slots
3. Resolve attendee names to email addresses
4. Generate professional meeting details

## Available Context
You will receive:
- User's message
- Relevant calendar events from memory
- Entity information (names → emails)
- User preferences

## Output Format
Return a JSON object with:
{{
    "action": "create_meeting" | "find_slots" | "check_conflicts" | "answer",
    "meeting_details": {{
        "title": "Meeting title",
        "description": "Meeting description",
        "start_time": "ISO datetime string",
        "duration_minutes": 30,
        "attendees": ["email1@domain.com", "email2@domain.com"],
        "location": "optional location",
        "video_conference": true
    }},
    "missing_fields": ["field1", "field2"],
    "message": "Human-readable response",
    "needs_clarification": true/false,
    "clarification_questions": [
        {{"field": "datetime", "question": "When should I schedule this?", "options": ["Tomorrow 3pm", "This week"]}}
    ]
}}

## Action Selection Rules
- Use "create_meeting" when user wants to SCHEDULE/CREATE a meeting (even if you pick the time)
- Use "find_slots" ONLY when user explicitly asks for availability without wanting to book
- Use "check_conflicts" when user asks if a specific time is free
- Use "answer" for queries about existing meetings (list, when, etc.)

## Rules
1. **CRITICAL: Email addresses in the message should be used directly as attendees** - If the user provides "john@example.com" or any email in the message, use it as an attendee email directly!
2. Try to resolve names (like "John", "Sarah") to email addresses using the entities provided
3. If datetime is ambiguous ("tomorrow", "next week"), pick a reasonable time (e.g., 9 AM or 3 PM)
4. Default meeting duration is 30 minutes unless specified
5. ALWAYS populate meeting_details with start_time when creating a meeting
6. For "upcoming meetings" queries, just return the answer with meeting list
7. **If the user's message IS an email address (like "farhan@gmail.com"), that is the attendee email - DO NOT ask for it again!**

## Current DateTime
{current_time}

## Example: Recognizing email in message
User Request: "Schedule meeting with Farhan tomorrow at 3pm for succession planning farhan@gmail.com"
→ The email "farhan@gmail.com" is RIGHT THERE in the message! Use it directly:
  "attendees": ["farhan@gmail.com"]
→ DO NOT ask for the email again!

Only output valid JSON."""


class CalendarAgent:
    """Calendar and meeting management agent."""

    def __init__(self, db: AsyncSession, openai_client: Optional[AsyncOpenAI] = None):
        self.db = db
        self.client = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.chat_model

    async def process(
        self,
        message: str,
        context: MemoryContext,
        user_id: str,
    ) -> AgentOutput:
        """
        Process a calendar-related request.

        Args:
            message: User's message
            context: Retrieved context from Memory Agent
            user_id: User ID

        Returns:
            AgentOutput with action or answer
        """
        # Extract email addresses directly from the message and add to entities
        import re
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails_in_message = re.findall(email_pattern, message)

        # Add extracted emails to entities so LLM sees them clearly
        entities_copy = dict(context.entities)
        for email in emails_in_message:
            # Use email as both key and value to make it obvious
            name_from_email = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
            entities_copy[name_from_email] = {"email": email}
            entities_copy[email] = {"email": email}  # Also add the email itself

        # Build context for LLM
        context_text = self._build_context_text(context)
        entities_text = self._build_entities_text(entities_copy)

        # If we found emails in the message, add explicit note
        emails_note = ""
        if emails_in_message:
            emails_note = f"\n\n**IMPORTANT: These email addresses were found in the user's message and should be used as attendees: {', '.join(emails_in_message)}**\n"

        current_time = datetime.now(timezone.utc)

        user_prompt = f"""User Request: "{message}"
{emails_note}
## Context (Calendar Events & Meetings)
{context_text}

## Known Entities (Name → Email)
{entities_text}

## Current Date/Time
{current_time.strftime("%Y-%m-%d %H:%M:%S %Z")} (UTC)
Local timezone hint: User seems to be in PKT (UTC+5)

Process this request and return JSON:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CALENDAR_SYSTEM_PROMPT.format(
                        current_time=current_time.isoformat()
                    )},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1500
            )

            content = response.choices[0].message.content or ""
            content = content.strip()

            # Try to extract JSON if wrapped in markdown
            if "```" in content:
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
                if json_match:
                    content = json_match.group(1).strip()

            result = json.loads(content)
            return self._process_result(result, user_id)

        except json.JSONDecodeError as e:
            raw_content = response.choices[0].message.content if response else "No response"
            print(f"Calendar agent JSON parse error: {e}")
            print(f"Raw content: {raw_content[:500] if raw_content else 'None'}")
            return AgentOutput(
                agent_name="calendar",
                success=False,
                message="I had trouble processing the calendar request. Could you try again?",
            )
        except Exception as e:
            import traceback
            print(f"Calendar agent error: {type(e).__name__}: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return AgentOutput(
                agent_name="calendar",
                success=False,
                message=f"Failed to process calendar request: {str(e)}",
            )

    def _process_result(self, result: dict, user_id: str) -> AgentOutput:
        """Process LLM result into AgentOutput."""
        action_type = result.get("action", "answer")
        message = result.get("message", "")
        needs_clarification = result.get("needs_clarification", False)

        # Handle clarification needed
        if needs_clarification:
            clarifications = [
                ClarificationQuestion(
                    field=q.get("field", "unknown"),
                    question=q.get("question", ""),
                    options=q.get("options"),
                    required=True
                )
                for q in result.get("clarification_questions", [])
            ]

            return AgentOutput(
                agent_name="calendar",
                success=True,
                message=message,
                clarifications=clarifications,
            )

        # Handle meeting creation or slot finding (both should create a meeting action)
        if action_type in ("create_meeting", "find_slots"):
            meeting = result.get("meeting_details", {})
            missing = result.get("missing_fields", [])

            # If we found a slot but have meeting details, treat it as create_meeting
            if action_type == "find_slots" and meeting.get("start_time"):
                action_type = "create_meeting"

            if missing:
                # Still missing required fields
                clarifications = [
                    ClarificationQuestion(
                        field=field,
                        question=self._get_clarification_question(field),
                        required=True
                    )
                    for field in missing
                ]
                return AgentOutput(
                    agent_name="calendar",
                    success=True,
                    message=message,
                    clarifications=clarifications,
                )

            # Create the action
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action = Action(
                id=action_id,
                type="create_meeting",
                status="needs_confirmation",
                payload={
                    "title": meeting.get("title", "Meeting"),
                    "description": meeting.get("description", ""),
                    "start_time": meeting.get("start_time"),
                    "end_time": meeting.get("end_time"),
                    "duration_minutes": meeting.get("duration_minutes", 30),
                    "attendees": meeting.get("attendees", []),
                    "location": meeting.get("location", ""),
                    "video_conference": meeting.get("video_conference", True),
                    "reminder_minutes": 15,
                },
                preview=self._generate_preview(meeting),
                missing_fields=[],
            )

            # Generate proper confirmation message (NOT "I have scheduled" - it's not done yet!)
            confirmation_message = self._generate_confirmation_message(meeting)

            return AgentOutput(
                agent_name="calendar",
                success=True,
                message=confirmation_message,
                action=action,
            )

        # Handle simple answer (e.g., listing upcoming meetings)
        return AgentOutput(
            agent_name="calendar",
            success=True,
            message=message,
            data=result.get("data"),
        )

    def _build_context_text(self, context: MemoryContext) -> str:
        """Build context text from memory items."""
        calendar_items = [
            item for item in context.items
            if item.get("source") in ("calendar", "meeting")
        ]

        if not calendar_items:
            return "No relevant calendar events found."

        lines = []
        for item in calendar_items[:10]:
            title = item.get("title", "Untitled")
            date = item.get("source_created_at", "")
            metadata = item.get("metadata", {})
            attendees = metadata.get("attendees", [])

            lines.append(f"- {title}")
            if date:
                lines.append(f"  Date: {date}")
            if attendees:
                lines.append(f"  Attendees: {', '.join(attendees[:5])}")

        return "\n".join(lines)

    def _build_entities_text(self, entities: dict[str, dict]) -> str:
        """Build entities text for LLM context."""
        if not entities:
            return "No known entities."

        lines = []
        for name, details in entities.items():
            email = details.get("email", "")
            if email:
                lines.append(f"- {name}: {email}")
            else:
                lines.append(f"- {name}")

        return "\n".join(lines)

    def _get_clarification_question(self, field: str) -> str:
        """Get clarification question for a field."""
        questions = {
            "datetime": "When should I schedule this meeting?",
            "start_time": "What time should the meeting start?",
            "attendees": "Who should I invite to this meeting?",
            "duration": "How long should the meeting be?",
            "title": "What should the meeting be about?",
            "topic": "What's the topic of the meeting?",
        }
        return questions.get(field, f"What should the {field} be?")

    def _generate_confirmation_message(self, meeting: dict) -> str:
        """Generate a message asking for confirmation (action is NOT done yet)."""
        title = meeting.get("title", "Meeting")
        start = meeting.get("start_time", "TBD")
        duration = meeting.get("duration_minutes", 30)
        attendees = meeting.get("attendees", [])

        # Parse and format datetime
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%b %d, %Y at %I:%M %p")
        except:
            formatted_time = start

        attendee_str = ", ".join(attendees) if attendees else "no attendees specified"

        return (
            f"I'm ready to schedule the following meeting:\n\n"
            f"**{title}**\n"
            f"📅 {formatted_time}\n"
            f"⏱️ {duration} minutes\n"
            f"👥 {attendee_str}\n\n"
            f"Would you like me to create this meeting?"
        )

    def _generate_preview(self, meeting: dict) -> str:
        """Generate human-readable preview of the meeting."""
        title = meeting.get("title", "Meeting")
        start = meeting.get("start_time", "TBD")
        duration = meeting.get("duration_minutes", 30)
        attendees = meeting.get("attendees", [])
        video = meeting.get("video_conference", True)

        # Parse and format datetime
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%b %d, %Y at %I:%M %p")
        except:
            formatted_time = start

        lines = [
            f"Meeting: {title}",
            f"Date: {formatted_time}",
            f"Duration: {duration} minutes",
        ]

        if attendees:
            lines.append(f"Attendees: {', '.join(attendees)}")

        if video:
            lines.append("Video conference will be added")

        return "\n".join(lines)
