"""
Email Agent - Specialist for email drafting and analysis.
"""

import json
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent, AgentState, AgentResponse, Tool

EMAIL_AGENT_SYSTEM_PROMPT = """You are an expert email specialist. Your job is to:
1. Draft professional, well-structured emails
2. Summarize email threads
3. Extract action items from emails
4. Suggest appropriate responses

## Guidelines:
- Match the user's preferred tone (professional, casual, formal)
- Keep emails concise but complete
- Include all necessary context
- Use appropriate greetings and sign-offs
- Structure longer emails with clear sections

## Available Context:
You may receive context including:
- Previous emails in the thread
- Related documents or tasks
- Entity information (people's emails, roles)
- User preferences for email style

## Output Format:
When drafting emails, structure them clearly with:
- To/CC/BCC (if applicable)
- Subject line
- Email body
- Sign-off"""


class EmailAgent(BaseAgent):
    """Email specialist agent for drafting and analyzing emails."""

    def __init__(self, db: AsyncSession):
        super().__init__(
            name="email_agent",
            system_prompt=EMAIL_AGENT_SYSTEM_PROMPT,
        )
        self.db = db
        self._register_tools()

    def _register_tools(self) -> None:
        """Register email-specific tools."""

        # Draft Email Tool
        self.register_tool(Tool(
            name="draft_email",
            description="Draft an email with given parameters",
            parameters={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of recipient email addresses",
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional CC recipients",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content",
                    },
                    "reply_to_id": {
                        "type": "string",
                        "description": "ID of email to reply to (if replying)",
                    },
                    "tone": {
                        "type": "string",
                        "enum": ["professional", "casual", "formal"],
                        "description": "Desired tone of the email",
                    },
                },
                "required": ["to", "subject", "body"],
            },
            handler=self._handle_draft_email,
        ))

        # Summarize Thread Tool
        self.register_tool(Tool(
            name="summarize_email_thread",
            description="Summarize an email thread",
            parameters={
                "type": "object",
                "properties": {
                    "include_action_items": {
                        "type": "boolean",
                        "description": "Whether to extract action items",
                    },
                    "include_decisions": {
                        "type": "boolean",
                        "description": "Whether to highlight decisions made",
                    },
                },
                "required": [],
            },
            handler=self._handle_summarize_thread,
        ))

        # Extract Action Items Tool
        self.register_tool(Tool(
            name="extract_action_items",
            description="Extract action items from email content",
            parameters={
                "type": "object",
                "properties": {
                    "assign_to_entities": {
                        "type": "boolean",
                        "description": "Try to assign action items to mentioned people",
                    },
                },
                "required": [],
            },
            handler=self._handle_extract_action_items,
        ))

    async def _handle_draft_email(
        self,
        state: AgentState,
        to: list[str],
        subject: str,
        body: str,
        cc: Optional[list[str]] = None,
        reply_to_id: Optional[str] = None,
        tone: str = "professional",
    ) -> dict:
        """Handle email drafting."""
        # Get user's email preferences
        email_prefs = state.preferences.get("email", {})
        signature = email_prefs.get("signature", {}).get("value", "Best regards")

        # Apply tone adjustments
        if tone == "casual" and body.startswith("Dear "):
            body = body.replace("Dear ", "Hi ")

        # Add signature if not already present
        if signature and signature not in body:
            body = f"{body}\n\n{signature}"

        # Create pending action
        action_id = str(uuid.uuid4())[:8]
        action = {
            "id": f"act_{action_id}",
            "type": "send_email",
            "params": {
                "to": to,
                "cc": cc,
                "subject": subject,
                "body": body,
                "reply_to_id": reply_to_id,
            },
            "description": f"Send email to {', '.join(to)}: {subject}",
            "status": "pending_confirmation",
        }

        state.pending_actions.append(action)

        return {
            "draft": {
                "to": to,
                "cc": cc,
                "subject": subject,
                "body": body,
            },
            "action_id": action["id"],
            "status": "draft_ready",
        }

    async def _handle_summarize_thread(
        self,
        state: AgentState,
        include_action_items: bool = True,
        include_decisions: bool = True,
    ) -> dict:
        """Handle email thread summarization."""
        # Get email context
        emails = [
            item for item in state.context_items
            if item.get("source") in ("gmail", "outlook")
        ]

        if not emails:
            return {"error": "No email context available"}

        # Build summary using context
        summary_parts = []
        participants = set()
        action_items = []
        decisions = []

        for email in emails:
            # Collect participants
            metadata = email.get("metadata", {})
            if metadata.get("from"):
                participants.add(metadata["from"])
            for to in metadata.get("to", []):
                participants.add(to)

        return {
            "summary": "Thread summary based on context",
            "participants": list(participants),
            "email_count": len(emails),
            "action_items": action_items if include_action_items else None,
            "decisions": decisions if include_decisions else None,
        }

    async def _handle_extract_action_items(
        self,
        state: AgentState,
        assign_to_entities: bool = True,
    ) -> dict:
        """Handle action item extraction."""
        # This would use LLM to extract action items from context
        action_items = []

        for item in state.context_items:
            content = item.get("summary") or item.get("content", "")
            # Action items would be extracted here
            # For now, return placeholder structure

        return {
            "action_items": action_items,
            "total": len(action_items),
        }

    async def run(self, state: AgentState) -> AgentResponse:
        """Run the email agent."""
        # Add email-specific context to system prompt
        email_prefs = state.preferences.get("email", {})
        tone = email_prefs.get("tone", {}).get("value", "professional")

        additional_context = f"\n## User Preferences:\n- Preferred tone: {tone}"

        # Run with tools
        response = await self.run_with_tools(state)
        response.pending_actions = state.pending_actions

        return response
