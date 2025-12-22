"""
Multi-agent system for the AI Assistant.

Agents:
- AgentOrchestrator: Main coordinator (routes to specialist agents)
- TriageAgent: LLM-based intent classification
- MemoryAgent: Centralized RAG context retrieval
- EmailAgent: Email drafting and analysis
- CalendarAgent: Meeting scheduling and calendar management
- JiraAgent: Task/ticket creation and management
- DocumentAgent: Document creation and summarization
"""

from app.agents.base import BaseAgent, AgentState, Tool, ToolResult
from app.agents.orchestrator import AgentOrchestrator, create_orchestrator
from app.agents.triage_agent import TriageAgent, get_triage_agent
from app.agents.memory_agent import MemoryAgent
from app.agents.email_agent import EmailAgent
from app.agents.calendar_agent import CalendarAgent
from app.agents.jira_agent import JiraAgent
from app.agents.document_agent import DocumentAgent

__all__ = [
    # Base classes
    "BaseAgent",
    "AgentState",
    "Tool",
    "ToolResult",
    # Main orchestrator
    "AgentOrchestrator",
    "create_orchestrator",
    # Core agents
    "TriageAgent",
    "get_triage_agent",
    "MemoryAgent",
    # Specialist agents
    "EmailAgent",
    "CalendarAgent",
    "JiraAgent",
    "DocumentAgent",
]
