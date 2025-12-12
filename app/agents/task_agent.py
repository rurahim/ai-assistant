"""
Task Agent - Specialist for task extraction and Jira management.
"""

import json
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent, AgentState, AgentResponse, Tool

TASK_AGENT_SYSTEM_PROMPT = """You are an expert task management specialist. Your job is to:
1. Extract tasks from documents, emails, and conversations
2. Create well-structured Jira tasks
3. Find related existing tasks
4. Ask for clarification when information is missing

## CRITICAL: Required Information Before Creating Tasks
You MUST have the following information before creating any task. If ANY of these are missing, DO NOT create the task - instead report what information is needed:

1. **Project Key** - Which Jira project? (REQUIRED)
2. **Specific Tasks** - What exactly needs to be done? (REQUIRED - do NOT invent tasks)
3. **Assignee** - Who should do this? (Ask if not specified)
4. **Priority** - How urgent is this? (Ask if not specified)

## What NOT to Do:
- Do NOT invent email addresses (e.g., "finance_team@example.com")
- Do NOT make up project keys
- Do NOT create tasks that weren't explicitly mentioned in the source context
- Do NOT assume who should be assigned to tasks
- Do NOT assume priorities unless clearly stated

## What TO Do:
- Extract ONLY tasks that are explicitly mentioned in the context
- Report what information is missing
- Ask the user to provide missing details
- Only proceed when you have all required information

## Task Structure (when all info is available):
- Summary: Clear, concise title (imperative verb)
- Description: Full context from source, acceptance criteria
- Type: story, task, bug, epic
- Priority: low, medium, high
- Labels: relevant tags
- Assignee: ONLY if explicitly provided

## Output Format:
When information is missing, clearly state:
- What context you found
- What specific information is needed to create tasks
- Ask the user to provide the missing details"""


class TaskAgent(BaseAgent):
    """Task specialist agent for task extraction and management."""

    def __init__(self, db: AsyncSession):
        super().__init__(
            name="task_agent",
            system_prompt=TASK_AGENT_SYSTEM_PROMPT,
        )
        self.db = db
        self._register_tools()

    def _register_tools(self) -> None:
        """Register task-specific tools."""

        # Extract Tasks Tool
        self.register_tool(Tool(
            name="extract_tasks",
            description="Extract tasks from provided context",
            parameters={
                "type": "object",
                "properties": {
                    "include_estimates": {
                        "type": "boolean",
                        "description": "Include effort estimates",
                    },
                    "suggest_assignees": {
                        "type": "boolean",
                        "description": "Suggest assignees based on context",
                    },
                },
                "required": [],
            },
            handler=self._handle_extract_tasks,
        ))

        # Create Jira Task Tool
        self.register_tool(Tool(
            name="create_jira_task",
            description="Create a Jira task/issue",
            parameters={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Jira project key (e.g., MOBILE, PROJ)",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Task summary/title",
                    },
                    "description": {
                        "type": "string",
                        "description": "Full task description",
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": ["story", "task", "bug", "epic"],
                        "description": "Type of issue",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Task priority",
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Assignee email address",
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Task labels",
                    },
                    "sprint": {
                        "type": "string",
                        "description": "Sprint name to add task to",
                    },
                },
                "required": ["project_key", "summary", "issue_type"],
            },
            handler=self._handle_create_jira_task,
        ))

        # Find Related Tasks Tool
        self.register_tool(Tool(
            name="find_related_tasks",
            description="Find tasks related to the current context",
            parameters={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Optional: specific project to search",
                    },
                    "status": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by status (e.g., ['To Do', 'In Progress'])",
                    },
                },
                "required": [],
            },
            handler=self._handle_find_related_tasks,
        ))

        # Batch Create Tasks Tool
        self.register_tool(Tool(
            name="batch_create_tasks",
            description="Create multiple tasks at once",
            parameters={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "project_key": {"type": "string"},
                                "summary": {"type": "string"},
                                "description": {"type": "string"},
                                "issue_type": {"type": "string"},
                                "priority": {"type": "string"},
                                "assignee": {"type": "string"},
                                "labels": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["project_key", "summary", "issue_type"],
                        },
                        "description": "List of tasks to create",
                    },
                    "sprint": {
                        "type": "string",
                        "description": "Sprint to add all tasks to",
                    },
                },
                "required": ["tasks"],
            },
            handler=self._handle_batch_create_tasks,
        ))

    async def _handle_extract_tasks(
        self,
        state: AgentState,
        include_estimates: bool = True,
        suggest_assignees: bool = True,
    ) -> dict:
        """Handle task extraction from context."""
        # This would use LLM to extract tasks from context
        extracted_tasks = []

        # Build prompt context from items
        context_text = ""
        for item in state.context_items:
            title = item.get("title", "")
            content = item.get("summary") or item.get("content", "")[:1000]
            context_text += f"\n---\n{title}\n{content}"

        # Would call LLM here to extract tasks
        return {
            "tasks": extracted_tasks,
            "count": len(extracted_tasks),
            "context_items_analyzed": len(state.context_items),
        }

    async def _handle_create_jira_task(
        self,
        state: AgentState,
        project_key: str,
        summary: str,
        issue_type: str,
        description: Optional[str] = None,
        priority: str = "medium",
        assignee: Optional[str] = None,
        labels: Optional[list[str]] = None,
        sprint: Optional[str] = None,
    ) -> dict:
        """Handle Jira task creation."""
        action_id = str(uuid.uuid4())[:8]

        # Resolve assignee email if name provided
        if assignee:
            for entity in state.entities:
                if entity.get("type") == "person":
                    if assignee.lower() in entity.get("name", "").lower():
                        assignee = entity.get("metadata", {}).get("emails", [assignee])[0]
                        break

        action = {
            "id": f"act_{action_id}",
            "type": "create_jira_task",
            "params": {
                "project_key": project_key,
                "type": issue_type,
                "summary": summary,
                "description": description,
                "priority": priority,
                "assignee": assignee,
                "labels": labels or [],
                "sprint": sprint,
            },
            "description": f"Create {issue_type}: {summary}",
            "status": "pending_confirmation",
        }

        state.pending_actions.append(action)

        return {
            "task": {
                "project_key": project_key,
                "summary": summary,
                "type": issue_type,
                "priority": priority,
                "assignee": assignee,
            },
            "action_id": action["id"],
            "status": "ready_for_creation",
        }

    async def _handle_find_related_tasks(
        self,
        state: AgentState,
        project_key: Optional[str] = None,
        status: Optional[list[str]] = None,
    ) -> dict:
        """Handle finding related tasks."""
        # Get Jira tasks from context
        jira_tasks = [
            item for item in state.context_items
            if item.get("source") == "jira"
        ]

        # Filter by project if specified
        if project_key:
            jira_tasks = [
                t for t in jira_tasks
                if t.get("metadata", {}).get("project_key") == project_key
            ]

        # Filter by status if specified
        if status:
            jira_tasks = [
                t for t in jira_tasks
                if t.get("metadata", {}).get("status") in status
            ]

        return {
            "related_tasks": [
                {
                    "id": t.get("source_id"),
                    "title": t.get("title"),
                    "status": t.get("metadata", {}).get("status"),
                    "priority": t.get("metadata", {}).get("priority"),
                }
                for t in jira_tasks[:10]
            ],
            "count": len(jira_tasks),
        }

    async def _handle_batch_create_tasks(
        self,
        state: AgentState,
        tasks: list[dict],
        sprint: Optional[str] = None,
    ) -> dict:
        """Handle batch task creation."""
        created_actions = []

        for task in tasks:
            action_id = str(uuid.uuid4())[:8]

            action = {
                "id": f"act_{action_id}",
                "type": "create_jira_task",
                "params": {
                    "project_key": task["project_key"],
                    "type": task["issue_type"],
                    "summary": task["summary"],
                    "description": task.get("description"),
                    "priority": task.get("priority", "medium"),
                    "assignee": task.get("assignee"),
                    "labels": task.get("labels", []),
                    "sprint": sprint,
                },
                "description": f"Create {task['issue_type']}: {task['summary']}",
                "status": "pending_confirmation",
            }

            state.pending_actions.append(action)
            created_actions.append({
                "action_id": action["id"],
                "summary": task["summary"],
            })

        return {
            "tasks_prepared": len(created_actions),
            "actions": created_actions,
            "sprint": sprint,
            "status": "ready_for_confirmation",
        }

    async def run(self, state: AgentState) -> AgentResponse:
        """Run the task agent."""
        response = await self.run_with_tools(state)
        response.pending_actions = state.pending_actions
        return response
