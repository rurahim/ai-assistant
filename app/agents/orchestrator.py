"""
Orchestrator Agent - Main coordinator for the AI Assistant.

Responsibilities:
- Intent classification
- Context retrieval coordination
- Delegation to specialist agents
- User clarification handling
- Action confirmation
"""

import json
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent, AgentState, AgentResponse, Tool, ToolResult
from app.services.context_service import ContextService
from app.services.entity_service import EntityService
from app.services.preference_service import PreferenceService
from app.core.memory import WorkingMemory
from app.config import get_settings

settings = get_settings()

ORCHESTRATOR_SYSTEM_PROMPT = """You are an intelligent AI assistant that helps users manage their work across email, documents, tasks, and calendar.

You are the orchestrator - your job is to:
1. Understand user intent
2. Retrieve relevant context using the retrieve_context tool (searches internal knowledge base)
3. Delegate complex tasks to specialist agents
4. Ask clarifying questions when needed
5. Prepare and confirm actions before execution

## Tools Available:
- retrieve_context: Search for relevant emails, documents, tasks, and events from the internal knowledge base
- delegate_to_specialist: Hand off tasks to Email, Document, or Task specialists
- ask_user: Ask the user for clarification or additional information
- prepare_action: Prepare an action for user confirmation
- get_recent_conversations: Retrieve recent conversation history for context
- find_entity: Look up information about people, projects, or topics

## CRITICAL: Using the ask_user Tool for Clarification
NEVER make assumptions. NEVER write clarification questions directly in your response text.
You MUST ALWAYS use the ask_user TOOL when you need ANY information from the user.

**WRONG approach (DO NOT DO THIS):**
Writing "What project should I use?" or "Please provide the assignee" in your response text.

**CORRECT approach:**
Call the ask_user tool with the question parameter set to your question.

Use the ask_user tool when:

1. **Creating Tasks/Tickets:**
   - Project key is not specified → Use ask_user tool
   - Assignee is not specified → Use ask_user tool
   - Specific tasks are not clear → Use ask_user tool
   - Priority is not specified → Use ask_user tool

2. **Sending Emails:**
   - Recipients are not clear → Use ask_user tool
   - Subject is not specified → Use ask_user tool

3. **Scheduling Events:**
   - Date/time is not specified → Use ask_user tool
   - Attendees are not specified → Use ask_user tool

4. **Any Missing Information:**
   - Do NOT invent email addresses, project keys, or assignees
   - Do NOT assume priorities, deadlines, or task details
   - Do NOT write questions in your response - USE THE ask_user TOOL

## Guidelines:
- Always retrieve context before answering questions about the user's data
- Use retrieve_context to search the internal knowledge base (emails, docs, tasks stored locally)
- When creating content (emails, documents, tasks), delegate to the appropriate specialist
- For destructive or important actions, always ask for confirmation
- Be concise but thorough in your responses
- Reference specific context items when relevant
- If information is missing, ask for clarification BEFORE taking action
- Consider recent conversations for context continuity
- When user says "last email" or similar, first retrieve context, then ask what specific actions to take

## Response Format:
- Provide clear, structured responses
- Use markdown for formatting
- List pending actions clearly
- Indicate when you need more information"""


class OrchestratorAgent(BaseAgent):
    """
    Main orchestrator agent that coordinates all interactions.
    """

    def __init__(
        self,
        db: AsyncSession,
        context_service: Optional[ContextService] = None,
        entity_service: Optional[EntityService] = None,
        preference_service: Optional[PreferenceService] = None,
        working_memory: Optional[WorkingMemory] = None,
    ):
        super().__init__(
            name="orchestrator",
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        )
        self.db = db
        self.context_service = context_service or ContextService()
        self.entity_service = entity_service or EntityService()
        self.preference_service = preference_service or PreferenceService(working_memory)
        self.working_memory = working_memory

        # Register tools
        self._register_tools()

    def _register_tools(self) -> None:
        """Register orchestrator tools."""

        # Retrieve Context Tool
        self.register_tool(Tool(
            name="retrieve_context",
            description="Search for relevant context from emails, documents, tasks, and calendar events",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query describing what to find",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["gmail", "gdrive", "jira", "calendar", "outlook", "onedrive"]},
                        "description": "Optional: specific sources to search",
                    },
                    "time_filter": {
                        "type": "string",
                        "enum": ["today", "yesterday", "last_week", "last_month", "last_3_months"],
                        "description": "Optional: time range filter",
                    },
                    "entity_filter": {
                        "type": "string",
                        "description": "Optional: filter by entity name (person, project)",
                    },
                },
                "required": ["query"],
            },
            handler=self._handle_retrieve_context,
        ))

        # Delegate to Specialist Tool
        self.register_tool(Tool(
            name="delegate_to_specialist",
            description="Delegate a task to a specialist agent (email, document, or task)",
            parameters={
                "type": "object",
                "properties": {
                    "specialist": {
                        "type": "string",
                        "enum": ["email", "document", "task"],
                        "description": "Which specialist to delegate to",
                    },
                    "task": {
                        "type": "string",
                        "description": "Description of the task for the specialist",
                    },
                    "context_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of context items to pass to specialist",
                    },
                },
                "required": ["specialist", "task"],
            },
            handler=self._handle_delegate,
        ))

        # Ask User Tool
        self.register_tool(Tool(
            name="ask_user",
            description="Ask the user for clarification or additional information",
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: multiple choice options",
                    },
                    "required_for": {
                        "type": "string",
                        "description": "What this information is needed for",
                    },
                },
                "required": ["question"],
            },
            handler=self._handle_ask_user,
        ))

        # Prepare Action Tool
        self.register_tool(Tool(
            name="prepare_action",
            description="Prepare an action for user confirmation before execution",
            parameters={
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["send_email", "create_task", "create_event", "create_document", "update_task"],
                        "description": "Type of action to prepare",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the action",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of the action",
                    },
                },
                "required": ["action_type", "params", "description"],
            },
            handler=self._handle_prepare_action,
        ))

        # Find Entity Tool
        self.register_tool(Tool(
            name="find_entity",
            description="Find a person, project, or company by name",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to search for",
                    },
                },
                "required": ["name"],
            },
            handler=self._handle_find_entity,
        ))

        # Get Recent Conversations Tool
        self.register_tool(Tool(
            name="get_recent_conversations",
            description="Get recent conversation history for context and continuity",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent messages to retrieve (default 10)",
                    },
                    "include_context": {
                        "type": "boolean",
                        "description": "Include context items from previous messages",
                    },
                },
                "required": [],
            },
            handler=self._handle_get_recent_conversations,
        ))

    async def _handle_retrieve_context(
        self,
        state: AgentState,
        query: str,
        sources: Optional[list[str]] = None,
        time_filter: Optional[str] = None,
        entity_filter: Optional[str] = None,
    ) -> dict:
        """
        Handle context retrieval tool call.

        Uses internal DB when EXTERNAL_DATA_ENABLED=False.
        Retrieves from all memory types:
        - Semantic Memory (embeddings)
        - Episodic Memory (past conversations)
        - Entity Memory (people, projects, topics)
        """
        # Use enhanced retrieve with episodic memory
        result = await self.context_service.retrieve_with_memory(
            db=self.db,
            user_id=state.user_id,
            query=query,
            session_id=state.session_id,
            sources=sources,
            time_filter=time_filter,
            entity_filter=entity_filter,
            include_episodic=True,  # Include past conversations
            limit=10,
        )

        # Update state with retrieved context
        state.context_items.extend(result["items"])
        state.entities.extend(result["entities"])

        # Separate items by type for clarity
        semantic_items = [i for i in result["items"] if i.get("retrieval_method") != "episodic"]
        episodic_items = [i for i in result["items"] if i.get("retrieval_method") == "episodic"]

        return {
            "found": result["total"],
            "data_source": "internal_db" if not settings.external_data_enabled else "external_api",
            "items": [
                {
                    "id": item["id"],
                    "source": item["source"],
                    "title": item["title"],
                    "summary": item.get("summary") or item.get("content", "")[:200],
                    "relevance": item.get("relevance_score", 0),
                    "type": "semantic" if item.get("retrieval_method") != "episodic" else "episodic",
                }
                for item in result["items"][:5]
            ],
            "entities": result["entities"],
            "memory_breakdown": {
                "semantic_count": len(semantic_items),
                "episodic_count": len(episodic_items),
            },
        }

    async def _handle_delegate(
        self,
        state: AgentState,
        specialist: str,
        task: str,
        context_ids: Optional[list[str]] = None,
    ) -> dict:
        """Handle delegation to specialist agent."""
        # Import here to avoid circular imports
        from app.agents.email_agent import EmailAgent
        from app.agents.document_agent import DocumentAgent
        from app.agents.task_agent import TaskAgent

        # Get relevant context items
        relevant_context = []
        if context_ids:
            relevant_context = [
                item for item in state.context_items
                if item.get("id") in context_ids
            ]
        else:
            # Use all context if no specific IDs
            relevant_context = state.context_items[:5]

        # Create specialist state
        specialist_state = AgentState(
            user_id=state.user_id,
            session_id=state.session_id,
            message=task,
            context_items=relevant_context,
            entities=state.entities,
            preferences=state.preferences,
        )

        # Get the appropriate specialist
        if specialist == "email":
            agent = EmailAgent(db=self.db)
        elif specialist == "document":
            agent = DocumentAgent(db=self.db)
        elif specialist == "task":
            agent = TaskAgent(db=self.db)
        else:
            return {"error": f"Unknown specialist: {specialist}"}

        # Run specialist
        response = await agent.run(specialist_state)

        # Merge pending actions
        state.pending_actions.extend(response.pending_actions)

        return {
            "specialist": specialist,
            "result": response.message,
            "pending_actions": len(response.pending_actions),
        }

    async def _handle_ask_user(
        self,
        state: AgentState,
        question: str,
        options: Optional[list[str]] = None,
        required_for: Optional[str] = None,
    ) -> dict:
        """Handle ask user tool call."""
        # Store clarification request in state
        state.metadata["needs_clarification"] = True
        state.metadata["clarification_question"] = question
        state.metadata["clarification_options"] = options
        state.metadata["clarification_required_for"] = required_for

        return {
            "status": "question_prepared",
            "question": question,
            "options": options,
        }

    async def _handle_prepare_action(
        self,
        state: AgentState,
        action_type: str,
        params: dict,
        description: str,
    ) -> dict:
        """Handle action preparation."""
        action_id = str(uuid.uuid4())[:8]

        action = {
            "id": f"act_{action_id}",
            "type": action_type,
            "params": params,
            "description": description,
            "status": "pending_confirmation",
        }

        state.pending_actions.append(action)

        return {
            "action_id": action["id"],
            "type": action_type,
            "description": description,
            "status": "prepared_for_confirmation",
        }

    async def _handle_find_entity(
        self,
        state: AgentState,
        name: str,
    ) -> dict:
        """Handle entity lookup."""
        entity = await self.entity_service.find_entity(
            self.db, state.user_id, name
        )

        if entity:
            entity_data = {
                "id": str(entity.id),
                "name": entity.name,
                "type": entity.entity_type,
                "metadata": entity.entity_metadata,
            }
            state.entities.append(entity_data)
            return {"found": True, "entity": entity_data}
        else:
            return {"found": False, "name": name}

    async def _handle_get_recent_conversations(
        self,
        state: AgentState,
        limit: int = 10,
        include_context: bool = True,
    ) -> dict:
        """Handle recent conversations retrieval."""
        from app.models import ChatSession, ChatMessage
        from sqlalchemy import select

        # Get recent sessions for this user
        sessions_stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == state.user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(5)
        )
        sessions_result = await self.db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()

        conversations = []
        for session in sessions:
            # Get recent messages from each session
            messages_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            messages_result = await self.db.execute(messages_stmt)
            messages = list(reversed(messages_result.scalars().all()))

            session_data = {
                "session_id": str(session.id),
                "title": session.title,
                "session_type": session.session_type,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content[:500],  # Truncate for context
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in messages
                ],
            }

            if include_context and messages:
                # Get context items from the most recent assistant message
                for m in reversed(messages):
                    if m.role == "assistant" and m.context_items:
                        session_data["context_items"] = m.context_items[:3]
                        break

            conversations.append(session_data)

        return {
            "recent_conversations": conversations,
            "total_sessions": len(sessions),
        }

    async def run(self, state: AgentState) -> AgentResponse:
        """
        Run the orchestrator agent.

        Handles:
        - Initial context retrieval based on intent
        - Tool-based interaction
        - Delegation to specialists
        - Final response generation
        """
        # Load user preferences
        state.preferences = await self.preference_service.get_preferences(
            self.db, state.user_id
        )

        # Run with tools
        response = await self.run_with_tools(state)

        # Check if we need clarification
        if state.metadata.get("needs_clarification"):
            response.needs_clarification = True
            response.clarification_question = state.metadata.get("clarification_question")
            response.clarification_options = state.metadata.get("clarification_options")

        # Add pending actions to response
        response.pending_actions = state.pending_actions

        return response
