"""
Jira Agent - Task/ticket management.

Handles:
- Creating Jira tasks/tickets
- Updating task status
- Querying sprint status
- Searching tasks
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


JIRA_SYSTEM_PROMPT = """You are a Jira/task management specialist agent. Your job is to:
1. Create new tasks/tickets
2. Update existing tasks
3. Query task status and sprint info
4. Help organize work items

## Available Context
You will receive:
- User's request
- Relevant tasks/tickets from memory
- Entity information (team members)
- Project information

## Output Format
Return a JSON object with:
{{
    "action": "create_task" | "update_task" | "query" | "answer",
    "task_details": {{
        "project_key": "PROJECT",
        "issue_type": "Task" | "Bug" | "Story" | "Epic",
        "summary": "Task title",
        "description": "Detailed description",
        "assignee": "email@domain.com",
        "priority": "High" | "Medium" | "Low",
        "labels": ["label1", "label2"],
        "due_date": "YYYY-MM-DD"
    }},
    "update_details": {{
        "issue_key": "PROJECT-123",
        "status": "In Progress" | "Done" | "To Do",
        "fields_to_update": {{}}
    }},
    "missing_fields": ["field1", "field2"],
    "message": "Human-readable response",
    "needs_clarification": true/false,
    "clarification_questions": [
        {{"field": "project", "question": "Which project?", "options": ["Project A", "Project B"]}}
    ]
}}

## Known Projects
{projects}

## Rules
1. Always require a summary/title for new tasks
2. Project key is required for new tasks
3. Resolve assignee names to emails using entities
4. Default priority is Medium if not specified
5. Issue type defaults to "Task" if not specified

Only output valid JSON."""


class JiraAgent:
    """Jira task management agent."""

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
        Process a Jira-related request.

        Args:
            message: User's message
            context: Retrieved context from Memory Agent
            user_id: User ID

        Returns:
            AgentOutput with action or answer
        """
        # Build context
        jira_context = self._build_jira_context(context)
        entities_text = self._build_entities_text(context.entities)
        projects = self._extract_projects(context)

        user_prompt = f"""User Request: "{message}"

## Task/Ticket Context
{jira_context}

## Known Team Members
{entities_text}

Process this request and return JSON:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": JIRA_SYSTEM_PROMPT.format(
                        projects=json.dumps(projects, indent=2)
                    )},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1500
            )

            result = json.loads(response.choices[0].message.content)
            return self._process_result(result, user_id)

        except Exception as e:
            return AgentOutput(
                agent_name="jira",
                success=False,
                message=f"Failed to process Jira request: {str(e)}",
            )

    def _process_result(self, result: dict, user_id: str) -> AgentOutput:
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
                agent_name="jira",
                success=True,
                message=message,
                clarifications=clarifications,
            )

        # Handle task creation
        if action_type == "create_task":
            task = result.get("task_details", {})
            missing = result.get("missing_fields", [])

            if missing:
                clarifications = [
                    ClarificationQuestion(
                        field=field,
                        question=self._get_clarification_question(field),
                        required=field in ["summary", "project_key"]
                    )
                    for field in missing
                ]
                return AgentOutput(
                    agent_name="jira",
                    success=True,
                    message=message,
                    clarifications=clarifications,
                )

            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action = Action(
                id=action_id,
                type="create_jira_task",
                status="needs_confirmation",
                payload={
                    "project_key": task.get("project_key", ""),
                    "issue_type": task.get("issue_type", "Task"),
                    "summary": task.get("summary", ""),
                    "description": task.get("description", ""),
                    "assignee": task.get("assignee"),
                    "reporter": user_id,
                    "priority": task.get("priority", "Medium"),
                    "labels": task.get("labels", []),
                    "due_date": task.get("due_date"),
                },
                preview=self._generate_create_preview(task),
                missing_fields=[],
            )

            # Generate proper confirmation message (NOT "has been created" - it's not done yet!)
            confirmation_message = self._generate_confirmation_message(task)

            return AgentOutput(
                agent_name="jira",
                success=True,
                message=confirmation_message,
                action=action,
            )

        # Handle task update
        if action_type == "update_task":
            update = result.get("update_details", {})

            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action = Action(
                id=action_id,
                type="update_jira_task",
                status="needs_confirmation",
                payload={
                    "issue_key": update.get("issue_key", ""),
                    "status": update.get("status"),
                    "fields": update.get("fields_to_update", {}),
                },
                preview=self._generate_update_preview(update),
                missing_fields=[],
            )

            return AgentOutput(
                agent_name="jira",
                success=True,
                message=message,
                action=action,
            )

        # Handle query/answer
        return AgentOutput(
            agent_name="jira",
            success=True,
            message=message,
            data=result.get("data"),
        )

    def _build_jira_context(self, context: MemoryContext) -> str:
        """Build Jira context from memory items."""
        jira_items = [
            item for item in context.items
            if item.get("source") == "jira"
        ]

        if not jira_items:
            return "No relevant tasks found."

        lines = []
        for item in jira_items[:10]:
            title = item.get("title", "Untitled")
            metadata = item.get("metadata", {})
            status = metadata.get("status", "Unknown")
            assignee = metadata.get("assignee", "Unassigned")
            priority = metadata.get("priority", "")
            issue_key = metadata.get("issue_key", "")

            lines.append(f"- [{issue_key}] {title}")
            lines.append(f"  Status: {status} | Assignee: {assignee} | Priority: {priority}")

        return "\n".join(lines)

    def _build_entities_text(self, entities: dict[str, dict]) -> str:
        """Build entities text."""
        if not entities:
            return "No known team members."

        lines = []
        for name, details in entities.items():
            email = details.get("email", "")
            if email:
                lines.append(f"- {name}: {email}")

        return "\n".join(lines) if lines else "No known team members."

    def _extract_projects(self, context: MemoryContext) -> list[str]:
        """Extract known project keys from context."""
        projects = set()

        for item in context.items or []:
            if item.get("source") == "jira":
                metadata = item.get("metadata", {})
                project_key = metadata.get("project_key")
                if project_key:
                    projects.add(project_key)

        # Add common project keys based on context
        query_analysis = context.query_analysis or {}
        filters = query_analysis.get("filters") or {}
        projects_from_analysis = filters.get("projects") or []
        if projects_from_analysis:
            projects.update(projects_from_analysis)

        return list(projects) or ["SUCC", "NEP", "HCMS"]  # Default projects

    def _get_clarification_question(self, field: str) -> str:
        """Get clarification question for a field."""
        questions = {
            "project_key": "Which project should this task be in?",
            "summary": "What should the task title be?",
            "description": "Can you provide more details about the task?",
            "assignee": "Who should this be assigned to?",
            "priority": "What priority should this task have?",
            "due_date": "When is this task due?",
            "issue_type": "What type of issue is this (Task, Bug, Story)?",
        }
        return questions.get(field, f"What should the {field} be?")

    def _generate_confirmation_message(self, task: dict) -> str:
        """Generate a message asking for confirmation (task is NOT created yet)."""
        summary = task.get("summary", "Untitled")
        project = task.get("project_key", "Unknown")
        priority = task.get("priority", "Medium")
        assignee = task.get("assignee", "Unassigned")
        issue_type = task.get("issue_type", "Task")

        return (
            f"I'm ready to create the following Jira task:\n\n"
            f"**{summary}**\n"
            f"📁 Project: {project}\n"
            f"📋 Type: {issue_type}\n"
            f"🔥 Priority: {priority}\n"
            f"👤 Assignee: {assignee}\n\n"
            f"Would you like me to create this task?"
        )

    def _generate_create_preview(self, task: dict) -> str:
        """Generate human-readable preview for task creation."""
        lines = [
            f"Jira Task: {task.get('summary', 'No title')}",
            f"Project: {task.get('project_key', 'Unknown')}",
            f"Type: {task.get('issue_type', 'Task')}",
            f"Priority: {task.get('priority', 'Medium')}",
        ]

        if task.get("assignee"):
            lines.append(f"Assignee: {task.get('assignee')}")

        if task.get("description"):
            desc = task.get("description", "")[:200]
            lines.append(f"Description: {desc}...")

        if task.get("due_date"):
            lines.append(f"Due: {task.get('due_date')}")

        return "\n".join(lines)

    def _generate_update_preview(self, update: dict) -> str:
        """Generate human-readable preview for task update."""
        lines = [f"Update Task: {update.get('issue_key', 'Unknown')}"]

        if update.get("status"):
            lines.append(f"New Status: {update.get('status')}")

        fields = update.get("fields_to_update", {})
        for field, value in fields.items():
            lines.append(f"{field}: {value}")

        return "\n".join(lines)
