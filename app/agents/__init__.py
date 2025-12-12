"""
Multi-agent system for the AI Assistant.

Agents:
- OrchestratorAgent: Main coordinator
- EmailAgent: Email drafting and analysis
- DocumentAgent: Document creation and summarization
- TaskAgent: Task extraction and Jira management
- ActionExecutor: External action execution
"""

from app.agents.base import BaseAgent, AgentState, Tool, ToolResult
from app.agents.orchestrator import OrchestratorAgent
from app.agents.email_agent import EmailAgent
from app.agents.document_agent import DocumentAgent
from app.agents.task_agent import TaskAgent
from app.agents.action_executor import ActionExecutor

__all__ = [
    "BaseAgent",
    "AgentState",
    "Tool",
    "ToolResult",
    "OrchestratorAgent",
    "EmailAgent",
    "DocumentAgent",
    "TaskAgent",
    "ActionExecutor",
]
