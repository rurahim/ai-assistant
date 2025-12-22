"""
Agent Orchestrator - Coordinates the multi-agent system.

This is the main entry point for the agent system. It:
1. Receives chat requests
2. Uses Triage Agent to classify intent
3. Invokes Memory Agent for context
4. Routes to specialist agents
5. Formats the final response
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.agent_schemas import (
    ChatRequest,
    ChatResponse,
    Action,
    ClarificationQuestion,
    SourceReference,
    ResponseMetadata,
    MemoryContext,
    PendingAction,
)
from app.agents.triage_agent import TriageAgent, get_triage_agent
from app.agents.memory_agent import MemoryAgent
from app.agents.email_agent import EmailAgent
from app.agents.calendar_agent import CalendarAgent
from app.agents.jira_agent import JiraAgent
from app.agents.document_agent import DocumentAgent
from app.models import ChatSession, ChatMessage


class AgentOrchestrator:
    """
    Main orchestrator for the multi-agent system.

    Coordinates:
    - Triage Agent: Intent classification and routing
    - Memory Agent: Context retrieval (RAG)
    - Specialist Agents: Email, Calendar, Jira, Document
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.triage = get_triage_agent()
        self.memory = MemoryAgent(db)

        # Specialist agents
        self.agents = {
            "email": EmailAgent(db),
            "calendar": CalendarAgent(db),
            "jira": JiraAgent(db),
            "document": DocumentAgent(db),
        }

    def _looks_like_clarification_response(self, message: str) -> bool:
        """Check if message looks like a clarification response (short answer)."""
        message = message.strip()
        # Short messages (less than 50 chars) that contain:
        if len(message) > 100:
            return False
        # Email pattern
        if "@" in message and "." in message:
            return True
        # Time patterns
        time_words = ["am", "pm", "tomorrow", "today", "monday", "tuesday",
                      "wednesday", "thursday", "friday", "saturday", "sunday",
                      "next week", "hour", "minutes", "noon", "morning", "afternoon"]
        if any(tw in message.lower() for tw in time_words):
            return True
        # Very short (likely a name, number, or single-word answer)
        if len(message.split()) <= 3:
            return True
        return False

    def _get_last_assistant_intent(self, conversation_history: list[dict]) -> Optional[str]:
        """Extract the intent from the last assistant message if it was asking for clarification."""
        if not conversation_history:
            return None

        # Look for the last assistant message
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()

                # Check if it was asking for information (includes our standard clarification message)
                clarification_phrases = [
                    "who should", "when would", "what time", "what is the",
                    "could you provide", "i need", "please provide",
                    "which project", "what should", "who to",
                    "need a bit more information",  # Our standard clarification message
                    "invited to this meeting",
                    "should be invited",
                ]
                if any(phrase in content for phrase in clarification_phrases):
                    # Try to determine what action was being clarified
                    if any(w in content for w in ["meeting", "schedule", "calendar", "invite", "invited"]):
                        return "action_meeting"
                    if any(w in content for w in ["email", "send", "draft", "reply"]):
                        return "action_email"
                    if any(w in content for w in ["task", "jira", "ticket", "issue"]):
                        return "action_jira"
                    if any(w in content for w in ["document", "proposal", "report"]):
                        return "action_document"
                break

        # Also check the user's earlier message for intent clues if assistant was clarifying
        for msg in conversation_history:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                if any(w in content for w in ["meeting", "schedule", "calendar"]):
                    return "action_meeting"
                if any(w in content for w in ["email", "send", "draft", "reply"]):
                    return "action_email"
                if any(w in content for w in ["task", "jira", "ticket", "issue", "create a task"]):
                    return "action_jira"
                if any(w in content for w in ["document", "proposal", "report"]):
                    return "action_document"
                break

        return None

    async def _get_session_from_redis(self, session_id: str) -> dict:
        """Get session data from Redis."""
        try:
            from app.core.redis_client import get_redis
            import json
            redis = await get_redis()
            data = await redis.client.get(f"session:{session_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Redis get error: {e}")
        return {"id": session_id, "pending_actions": []}

    async def _save_session_to_redis(self, session_id: str, session: dict) -> None:
        """Save session data to Redis."""
        try:
            from app.core.redis_client import get_redis
            import json
            redis = await get_redis()
            await redis.client.set(
                f"session:{session_id}",
                json.dumps(session),
                ex=3600  # 1 hour expiry
            )
        except Exception as e:
            print(f"Redis save error: {e}")

    async def process(self, request: ChatRequest) -> ChatResponse:
        """
        Main entry point for processing chat requests.

        Args:
            request: The chat request

        Returns:
            ChatResponse with the result
        """
        start_time = time.time()
        agents_used = ["triage"]

        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        session = await self._get_or_create_session(request.user_id, session_id)

        # Get conversation history
        conversation_history = await self.memory.get_recent_session_context(
            request.user_id, session_id, limit=10
        )

        # Check for action confirmation
        if request.confirm_action:
            return await self._handle_confirmation(
                request, session, session_id, start_time
            )

        # Step 1: Triage - Classify intent
        triage_result = await self.triage.classify(
            request,
            conversation_history=conversation_history,
            pending_actions=session.get("pending_actions", []),
        )

        # Fallback: Override if triage misclassified a clarification response
        # This handles cases where the LLM returns qa_simple, qa_search, or even clarification_needed
        # when the user is actually answering a previous clarification request
        if triage_result.intent in ("qa_simple", "qa_search", "clarification_needed"):
            if self._looks_like_clarification_response(request.message):
                original_intent = self._get_last_assistant_intent(conversation_history)
                if original_intent:
                    # Build synthesized request from conversation
                    all_user_messages = [
                        msg.get("content", "") for msg in conversation_history
                        if msg.get("role") == "user"
                    ] + [request.message]
                    synthesized = " ".join(all_user_messages)

                    # Override triage result
                    triage_result.intent = original_intent
                    triage_result.requires_clarification = False
                    triage_result.synthesized_request = synthesized
                    # Set appropriate agents
                    agent_map = {
                        "action_meeting": ["memory", "calendar"],
                        "action_email": ["memory", "email"],
                        "action_jira": ["memory", "jira"],
                        "action_document": ["memory", "document"],
                    }
                    triage_result.agents_needed = agent_map.get(original_intent, ["memory"])

        # Handle confirmation/rejection intents
        if triage_result.intent == "confirmation":
            pending = session.get("pending_actions", [])
            if pending:
                # Auto-confirm the most recent pending action
                request.confirm_action = pending[-1].get("id")
                return await self._handle_confirmation(
                    request, session, session_id, start_time
                )

        if triage_result.intent == "rejection":
            # Clear pending actions
            session["pending_actions"] = []
            return ChatResponse(
                response_type="answer",
                message="No problem, I've cancelled the pending action. What else can I help you with?",
                session_id=session_id,
                metadata=ResponseMetadata(
                    agents_used=agents_used,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    intent=triage_result.intent,
                    confidence=triage_result.confidence,
                ),
            )

        if triage_result.intent == "chitchat":
            return await self._handle_chitchat(
                request, session_id, start_time
            )

        # Step 2: Memory Agent - Get context (if needed)
        context = MemoryContext()
        if triage_result.requires_context:
            agents_used.append("memory")
            context = await self.memory.retrieve_context(
                request,
                session_id=session_id,
                include_episodic=True,
                limit=10,
            )

        # Step 3: Check if clarification needed before routing
        if triage_result.requires_clarification:
            clarifications = [
                ClarificationQuestion(
                    field=field,
                    question=self._get_default_clarification(field),
                    required=True
                )
                for field in triage_result.clarification_fields
            ]

            return ChatResponse(
                response_type="clarification",
                message="I'd like to help, but I need a bit more information:",
                session_id=session_id,
                clarifications=clarifications,
                metadata=ResponseMetadata(
                    agents_used=agents_used,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    intent=triage_result.intent,
                    confidence=triage_result.confidence,
                ),
            )

        # Step 4: Route to specialist agents
        # Use synthesized request if available (combines multi-turn conversation)
        message_for_agents = triage_result.synthesized_request or request.message

        agent_outputs = []
        for agent_name in triage_result.agents_needed:
            if agent_name == "memory":
                continue  # Already handled

            if agent_name in self.agents:
                agents_used.append(agent_name)
                agent = self.agents[agent_name]
                output = await agent.process(
                    message_for_agents,
                    context,
                    request.user_id,
                )
                agent_outputs.append(output)

        # Step 5: Build response
        return await self._build_response(
            agent_outputs=agent_outputs,
            context=context,
            session=session,
            session_id=session_id,
            triage_result=triage_result,
            agents_used=agents_used,
            start_time=start_time,
        )

    async def _handle_confirmation(
        self,
        request: ChatRequest,
        session: dict,
        session_id: str,
        start_time: float,
    ) -> ChatResponse:
        """Handle action confirmation, including any modifications."""
        action_id = request.confirm_action
        pending_actions = session.get("pending_actions", [])

        # Find the action
        action = None
        for pa in pending_actions:
            if pa.get("id") == action_id:
                action = pa
                break

        if not action:
            return ChatResponse(
                response_type="answer",
                message=f"I couldn't find the action '{action_id}'. It may have expired.",
                session_id=session_id,
                metadata=ResponseMetadata(
                    agents_used=["orchestrator"],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                ),
            )

        # Check for modifications in the confirmation message
        modifications = self._extract_modifications(request.message, action)
        if modifications:
            # Apply modifications to the action payload
            for field, value in modifications.items():
                action["payload"][field] = value
            # Regenerate preview if possible
            action["preview"] = self._regenerate_preview(action)

        # Update action status to ready
        action["status"] = "ready"

        # Remove from pending
        session["pending_actions"] = [
            pa for pa in pending_actions if pa.get("id") != action_id
        ]

        # Save updated session to Redis
        await self._save_session_to_redis(session_id, session)

        # Generate appropriate message based on modifications
        if modifications:
            mod_desc = ", ".join([f"{k}={v}" for k, v in modifications.items()])
            message = f"Done! I've updated the action with your changes ({mod_desc}) and it's ready to execute."
        else:
            message = "Action confirmed and ready to execute."

        return ChatResponse(
            response_type="action",
            message=message,
            session_id=session_id,
            action=Action(
                id=action["id"],
                type=action["type"],
                status="ready",
                payload=action["payload"],
                preview=action.get("preview", ""),
            ),
            metadata=ResponseMetadata(
                agents_used=["orchestrator"],
                processing_time_ms=int((time.time() - start_time) * 1000),
            ),
        )

    async def _handle_chitchat(
        self,
        request: ChatRequest,
        session_id: str,
        start_time: float,
    ) -> ChatResponse:
        """Handle chitchat/greeting messages."""
        message = request.message.lower()

        if any(g in message for g in ["hi", "hello", "hey"]):
            response = "Hello! I'm your AI assistant. I can help you with emails, meetings, tasks, and documents. What would you like to do?"
        elif any(g in message for g in ["thank", "thanks"]):
            response = "You're welcome! Let me know if you need anything else."
        elif any(g in message for g in ["bye", "goodbye"]):
            response = "Goodbye! Have a great day!"
        else:
            response = "I'm here to help! You can ask me about your emails, schedule meetings, create tasks, or generate documents."

        return ChatResponse(
            response_type="answer",
            message=response,
            session_id=session_id,
            metadata=ResponseMetadata(
                agents_used=["triage"],
                processing_time_ms=int((time.time() - start_time) * 1000),
                intent="chitchat",
                confidence=0.9,
            ),
        )

    async def _build_response(
        self,
        agent_outputs: list,
        context: MemoryContext,
        session: dict,
        session_id: str,
        triage_result,
        agents_used: list[str],
        start_time: float,
    ) -> ChatResponse:
        """Build the final response from agent outputs."""
        # Combine messages from all agents
        messages = []
        action = None
        clarifications = []
        sources = []

        for output in agent_outputs:
            if output.message:
                messages.append(output.message)

            if output.action:
                action = output.action
                # Store in session pending actions
                session.setdefault("pending_actions", []).append({
                    "id": action.id,
                    "type": action.type,
                    "status": action.status,
                    "payload": action.payload,
                    "preview": action.preview,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                # Save to Redis for cross-worker persistence
                await self._save_session_to_redis(session_id, session)

            if output.clarifications:
                clarifications.extend(output.clarifications)

        # Build sources from context
        for item in context.items[:5]:
            sources.append(SourceReference(
                id=item.get("id", "unknown"),
                type=item.get("source", "unknown"),
                title=item.get("title", ""),
                date=item.get("source_created_at"),
                relevance=item.get("relevance_score"),
            ))

        # Determine response type
        if clarifications:
            response_type = "clarification"
        elif action:
            response_type = "action"
        else:
            response_type = "answer"

        # Combine messages
        combined_message = "\n\n".join(messages) if messages else "I processed your request."

        return ChatResponse(
            response_type=response_type,
            message=combined_message,
            session_id=session_id,
            action=action,
            clarifications=clarifications if clarifications else None,
            sources=sources,
            metadata=ResponseMetadata(
                agents_used=agents_used,
                processing_time_ms=int((time.time() - start_time) * 1000),
                intent=triage_result.intent,
                confidence=triage_result.confidence,
                query_analysis=context.query_analysis,
            ),
        )

    async def _get_or_create_session(
        self,
        user_id: str,
        session_id: str,
    ) -> dict:
        """Get or create a session using Redis for pending actions."""
        # Try to get from Redis first (has pending actions)
        session = await self._get_session_from_redis(session_id)
        if session.get("pending_actions"):
            return session

        # Check if session exists in DB
        try:
            stmt = select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
            result = await self.db.execute(stmt)
            db_session = result.scalar_one_or_none()

            if db_session:
                session = {
                    "id": session_id,
                    "user_id": user_id,
                    "pending_actions": session.get("pending_actions", []),
                }
                return session
        except Exception:
            pass

        # Create new session
        new_session = {
            "id": session_id,
            "user_id": user_id,
            "pending_actions": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save to DB
        try:
            db_session = ChatSession(
                id=uuid.UUID(session_id) if len(session_id) == 36 else uuid.uuid4(),
                user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
                title="New Conversation",
            )
            self.db.add(db_session)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            print(f"Failed to save session to DB: {e}")

        return new_session

    def _extract_modifications(self, message: str, action: dict) -> dict:
        """Extract any modifications from the confirmation message."""
        message_lower = message.lower()
        modifications = {}

        # Priority modifications
        if "high priority" in message_lower or "priority high" in message_lower:
            modifications["priority"] = "High"
        elif "low priority" in message_lower or "priority low" in message_lower:
            modifications["priority"] = "Low"
        elif "medium priority" in message_lower or "priority medium" in message_lower:
            modifications["priority"] = "Medium"
        elif "urgent" in message_lower or "critical" in message_lower:
            modifications["priority"] = "High"

        # Duration modifications (for meetings)
        import re
        duration_match = re.search(r'(\d+)\s*(hour|hr|minute|min)', message_lower)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)
            if 'hour' in unit or 'hr' in unit:
                modifications["duration_minutes"] = amount * 60
            else:
                modifications["duration_minutes"] = amount

        # Title/summary modifications
        if "rename to" in message_lower or "title to" in message_lower or "call it" in message_lower:
            # Extract the new title (rough heuristic)
            for pattern in [r'rename to ["\']?([^"\']+)["\']?', r'title to ["\']?([^"\']+)["\']?', r'call it ["\']?([^"\']+)["\']?']:
                match = re.search(pattern, message_lower)
                if match:
                    if action.get("type") in ("create_jira_task", "update_jira_task"):
                        modifications["summary"] = match.group(1).strip()
                    elif action.get("type") == "create_meeting":
                        modifications["title"] = match.group(1).strip()
                    break

        return modifications

    def _regenerate_preview(self, action: dict) -> str:
        """Regenerate preview after modifications."""
        action_type = action.get("type", "")
        payload = action.get("payload", {})

        if action_type == "create_meeting":
            lines = [
                f"Meeting: {payload.get('title', 'Meeting')}",
                f"Date: {payload.get('start_time', 'TBD')}",
                f"Duration: {payload.get('duration_minutes', 30)} minutes",
            ]
            if payload.get("attendees"):
                lines.append(f"Attendees: {', '.join(payload.get('attendees', []))}")
            if payload.get("video_conference"):
                lines.append("Video conference will be added")
            return "\n".join(lines)

        elif action_type in ("create_jira_task", "update_jira_task"):
            lines = [
                f"Jira Task: {payload.get('summary', 'No title')}",
                f"Project: {payload.get('project_key', 'Unknown')}",
                f"Type: {payload.get('issue_type', 'Task')}",
                f"Priority: {payload.get('priority', 'Medium')}",
            ]
            if payload.get("assignee"):
                lines.append(f"Assignee: {payload.get('assignee')}")
            return "\n".join(lines)

        # Default: return existing preview
        return action.get("preview", "")

    def _get_default_clarification(self, field: str) -> str:
        """Get default clarification question for a field."""
        defaults = {
            # Calendar/Meeting fields
            "datetime": "When would you like to schedule this meeting?",
            "duration": "How long should the meeting be?",
            "attendees": "Who should be invited to this meeting?",
            "topic": "What is this meeting about?",

            # Email fields
            "recipient": "Who should I send this email to?",
            "subject": "What should the email subject be?",
            "body_topic": "What should the email be about?",

            # Jira/Task fields
            "project_key": "Which Jira project should this task be in?",
            "project": "Which project is this for?",
            "summary": "What should the task title be?",
            "assignee": "Who should this task be assigned to?",
            "priority": "What priority level? (High, Medium, Low)",
            "description": "Can you provide more details about the task?",

            # Document fields
            "title": "What should the document title be?",
            "format": "What format would you prefer? (PDF, Word, Google Doc)",
        }
        return defaults.get(field, f"Could you provide the {field}?")


# Factory function
def create_orchestrator(db: AsyncSession) -> AgentOrchestrator:
    """Create an agent orchestrator instance."""
    return AgentOrchestrator(db)
