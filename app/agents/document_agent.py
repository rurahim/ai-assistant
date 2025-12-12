"""
Document Agent - Specialist for document creation and analysis.
"""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent, AgentState, AgentResponse, Tool

DOCUMENT_AGENT_SYSTEM_PROMPT = """You are an expert document specialist. Your job is to:
1. Create well-structured documents (reports, summaries, proposals)
2. Summarize existing documents
3. Extract key information from documents
4. Update document sections

## Guidelines:
- Use clear, professional language
- Structure documents with headers and sections
- Include tables for data when appropriate
- Use markdown formatting
- Be thorough but concise

## Document Types:
- Status Reports: Executive summary, progress, blockers, next steps
- Meeting Notes: Attendees, topics, decisions, action items
- Project Summaries: Overview, team, milestones, risks
- Technical Docs: Description, architecture, implementation details

## Output Format:
Provide documents in markdown format with clear structure."""


class DocumentAgent(BaseAgent):
    """Document specialist agent for creating and analyzing documents."""

    def __init__(self, db: AsyncSession):
        super().__init__(
            name="document_agent",
            system_prompt=DOCUMENT_AGENT_SYSTEM_PROMPT,
        )
        self.db = db
        self._register_tools()

    def _register_tools(self) -> None:
        """Register document-specific tools."""

        # Create Document Tool
        self.register_tool(Tool(
            name="create_document",
            description="Create a new document",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Document title",
                    },
                    "content": {
                        "type": "string",
                        "description": "Document content (markdown)",
                    },
                    "doc_type": {
                        "type": "string",
                        "enum": ["report", "summary", "proposal", "notes", "other"],
                        "description": "Type of document",
                    },
                    "folder": {
                        "type": "string",
                        "description": "Optional folder path to save to",
                    },
                },
                "required": ["title", "content"],
            },
            handler=self._handle_create_document,
        ))

        # Summarize Document Tool
        self.register_tool(Tool(
            name="summarize_document",
            description="Create a summary of document content",
            parameters={
                "type": "object",
                "properties": {
                    "max_length": {
                        "type": "string",
                        "enum": ["brief", "medium", "detailed"],
                        "description": "Desired summary length",
                    },
                    "focus": {
                        "type": "string",
                        "description": "Optional: specific aspect to focus on",
                    },
                },
                "required": [],
            },
            handler=self._handle_summarize_document,
        ))

        # Extract Key Points Tool
        self.register_tool(Tool(
            name="extract_key_points",
            description="Extract key points from document context",
            parameters={
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Categories to extract (decisions, risks, requirements)",
                    },
                },
                "required": [],
            },
            handler=self._handle_extract_key_points,
        ))

        # Generate Report Tool
        self.register_tool(Tool(
            name="generate_report",
            description="Generate a report from multiple sources",
            parameters={
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "enum": ["status", "weekly", "project", "meeting"],
                        "description": "Type of report to generate",
                    },
                    "title": {
                        "type": "string",
                        "description": "Report title",
                    },
                    "include_sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sections to include",
                    },
                },
                "required": ["report_type", "title"],
            },
            handler=self._handle_generate_report,
        ))

    async def _handle_create_document(
        self,
        state: AgentState,
        title: str,
        content: str,
        doc_type: str = "other",
        folder: Optional[str] = None,
    ) -> dict:
        """Handle document creation."""
        action_id = str(uuid.uuid4())[:8]

        action = {
            "id": f"act_{action_id}",
            "type": "create_document",
            "params": {
                "title": title,
                "content": content,
                "folder": folder,
                "format": "google_doc",
            },
            "description": f"Create document: {title}",
            "status": "pending_confirmation",
        }

        state.pending_actions.append(action)

        return {
            "document": {
                "title": title,
                "content_preview": content[:500] + "..." if len(content) > 500 else content,
                "type": doc_type,
                "folder": folder,
            },
            "action_id": action["id"],
            "status": "ready_for_creation",
        }

    async def _handle_summarize_document(
        self,
        state: AgentState,
        max_length: str = "medium",
        focus: Optional[str] = None,
    ) -> dict:
        """Handle document summarization."""
        # Get document context
        docs = [
            item for item in state.context_items
            if item.get("source") in ("gdrive", "onedrive")
        ]

        if not docs:
            return {"error": "No document context available"}

        # Build summary info
        return {
            "document_count": len(docs),
            "titles": [d.get("title") for d in docs],
            "summary_request": {
                "length": max_length,
                "focus": focus,
            },
        }

    async def _handle_extract_key_points(
        self,
        state: AgentState,
        categories: Optional[list[str]] = None,
    ) -> dict:
        """Handle key point extraction."""
        categories = categories or ["decisions", "action_items", "risks"]

        key_points = {cat: [] for cat in categories}

        # Would use LLM to extract key points from context
        return {
            "key_points": key_points,
            "source_count": len(state.context_items),
        }

    async def _handle_generate_report(
        self,
        state: AgentState,
        report_type: str,
        title: str,
        include_sections: Optional[list[str]] = None,
    ) -> dict:
        """Handle report generation."""
        # Define default sections by report type
        section_templates = {
            "status": ["Executive Summary", "Progress", "Blockers", "Next Steps"],
            "weekly": ["Accomplishments", "In Progress", "Blockers", "Next Week"],
            "project": ["Overview", "Team", "Progress", "Milestones", "Risks"],
            "meeting": ["Attendees", "Agenda", "Discussion", "Decisions", "Action Items"],
        }

        sections = include_sections or section_templates.get(report_type, [])

        # Build report structure
        report_content = f"# {title}\n\n"
        report_content += f"*Generated: {state.metadata.get('timestamp', 'now')}*\n\n"

        for section in sections:
            report_content += f"## {section}\n\n"
            report_content += f"[Content for {section}]\n\n"

        return {
            "report_type": report_type,
            "title": title,
            "sections": sections,
            "content_preview": report_content,
        }

    async def run(self, state: AgentState) -> AgentResponse:
        """Run the document agent."""
        response = await self.run_with_tools(state)
        response.pending_actions = state.pending_actions
        return response
