"""
Email Agent - Email drafting, summarization, and action extraction.

Handles:
- Drafting emails and replies
- Summarizing email threads
- Extracting action items from emails
- Suggesting appropriate responses
"""

import json
import uuid
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


EMAIL_SYSTEM_PROMPT = """You are an expert email specialist agent. Your job is to:
1. Draft professional, well-structured emails
2. Summarize email threads
3. Extract action items from emails
4. Suggest appropriate responses

## Available Context
You will receive:
- User's request
- Relevant emails from memory (or ad-hoc email in attachments)
- Entity information (names → emails)
- User preferences (signature, tone, etc.)

## Output Format
Return a JSON object with:
{{
    "action": "draft_email" | "summarize" | "extract_actions" | "answer",
    "email_details": {{
        "to": ["email@domain.com"],
        "cc": ["cc@domain.com"],
        "subject": "Email subject",
        "body": "Email body content",
        "reply_to_id": "optional_message_id"
    }},
    "summary": "Thread summary if summarizing",
    "action_items": [
        {{"task": "description", "assignee": "person", "due": "date"}}
    ],
    "message": "Human-readable response",
    "needs_clarification": true/false,
    "clarification_questions": [
        {{"field": "recipient", "question": "Who should I send this to?"}}
    ]
}}

## Email Guidelines
1. Match the user's preferred tone (professional/casual/formal)
2. Keep emails concise but complete
3. Include appropriate greetings and sign-offs
4. Use the user's signature if provided
5. When replying, reference the original email context
6. For summaries, highlight key points and action items

## User Preferences
{preferences}

Only output valid JSON."""


class EmailAgent:
    """Email drafting and analysis agent."""

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
        Process an email-related request.

        Args:
            message: User's message
            context: Retrieved context from Memory Agent
            user_id: User ID

        Returns:
            AgentOutput with action or answer
        """
        # Build context
        email_context = self._build_email_context(context)
        entities_text = self._build_entities_text(context.entities)
        preferences = self._extract_email_preferences(context.user_preferences)

        user_prompt = f"""User Request: "{message}"

## Email Context
{email_context}

## Known Entities (Name → Email)
{entities_text}

Process this request and return JSON:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EMAIL_SYSTEM_PROMPT.format(
                        preferences=json.dumps(preferences, indent=2)
                    )},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=2000
            )

            result = json.loads(response.choices[0].message.content)
            return self._process_result(result, user_id, preferences)

        except Exception as e:
            return AgentOutput(
                agent_name="email",
                success=False,
                message=f"Failed to process email request: {str(e)}",
            )

    def _process_result(
        self,
        result: dict,
        user_id: str,
        preferences: dict
    ) -> AgentOutput:
        """Process LLM result into AgentOutput."""
        action_type = result.get("action", "answer")
        message = result.get("message", "")
        needs_clarification = result.get("needs_clarification", False)

        # Handle clarification
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
                agent_name="email",
                success=True,
                message=message,
                clarifications=clarifications,
            )

        # Handle email drafting
        if action_type == "draft_email":
            email = result.get("email_details", {})

            # Apply signature if not present
            body = email.get("body", "")
            signature = preferences.get("signature", "Best regards")
            if signature and signature not in body:
                body = f"{body}\n\n{signature}"

            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action = Action(
                id=action_id,
                type="send_email",
                status="needs_confirmation",
                payload={
                    "to": email.get("to", []),
                    "cc": email.get("cc", []),
                    "bcc": email.get("bcc", []),
                    "subject": email.get("subject", ""),
                    "body": body,
                    "reply_to_id": email.get("reply_to_id"),
                    "attachments": [],
                },
                preview=self._generate_preview(email, body),
                missing_fields=[],
            )

            return AgentOutput(
                agent_name="email",
                success=True,
                message=message,
                action=action,
            )

        # Handle summarization
        if action_type == "summarize":
            return AgentOutput(
                agent_name="email",
                success=True,
                message=message,
                data={
                    "summary": result.get("summary"),
                    "action_items": result.get("action_items", []),
                }
            )

        # Handle action extraction
        if action_type == "extract_actions":
            return AgentOutput(
                agent_name="email",
                success=True,
                message=message,
                data={
                    "action_items": result.get("action_items", []),
                }
            )

        # Default answer
        return AgentOutput(
            agent_name="email",
            success=True,
            message=message,
        )

    def _build_email_context(self, context: MemoryContext) -> str:
        """Build email context from memory items."""
        # First check for attachments (ad-hoc content)
        attachment_emails = [
            item for item in context.items
            if item.get("source") == "attachment" and item.get("content_type") == "email"
        ]

        # Then get emails from DB
        db_emails = [
            item for item in context.items
            if item.get("source") in ("gmail", "outlook")
        ]

        emails = attachment_emails + db_emails

        if not emails:
            return "No relevant emails found."

        lines = []
        for item in emails[:10]:
            title = item.get("title", "Untitled")
            metadata = item.get("metadata", {})
            from_addr = metadata.get("from", "Unknown")
            content = item.get("content", item.get("summary", ""))[:500]

            lines.append(f"---")
            lines.append(f"From: {from_addr}")
            lines.append(f"Subject: {title}")
            lines.append(f"Content: {content}")

        return "\n".join(lines)

    def _build_entities_text(self, entities: dict[str, dict]) -> str:
        """Build entities text."""
        if not entities:
            return "No known entities."

        lines = []
        for name, details in entities.items():
            email = details.get("email", "")
            if email:
                lines.append(f"- {name}: {email}")

        return "\n".join(lines) if lines else "No known entities."

    def _extract_email_preferences(self, preferences: dict) -> dict:
        """Extract email-specific preferences."""
        email_prefs = preferences.get("email", {})
        return {
            "tone": email_prefs.get("tone", {}).get("value", "professional"),
            "signature": email_prefs.get("signature", {}).get("value", "Best regards"),
        }

    def _generate_preview(self, email: dict, body: str) -> str:
        """Generate human-readable email preview."""
        to = email.get("to", [])
        cc = email.get("cc", [])
        subject = email.get("subject", "No Subject")

        lines = [
            f"To: {', '.join(to)}",
        ]

        if cc:
            lines.append(f"CC: {', '.join(cc)}")

        lines.append(f"Subject: {subject}")
        lines.append("")
        lines.append(body[:500] + ("..." if len(body) > 500 else ""))

        return "\n".join(lines)
