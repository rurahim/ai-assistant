"""
Document Agent - Document generation and analysis.

Handles:
- Generating documents (proposals, reports, etc.)
- Summarizing documents
- Applying templates
- Creating formatted content
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


DOCUMENT_SYSTEM_PROMPT = """You are a document generation specialist agent. Your job is to:
1. Generate professional documents (proposals, reports, summaries)
2. Apply templates to content
3. Structure information clearly
4. Summarize long documents

## Available Context
You will receive:
- User's request
- Relevant documents and context from memory
- Project information
- Past communications related to the topic

## Output Format
Return a JSON object with:
{
    "action": "generate_document" | "summarize" | "apply_template" | "answer",
    "document_details": {
        "title": "Document Title",
        "format": "pdf" | "docx" | "gdoc" | "markdown",
        "template": "technical_proposal" | "report" | "summary" | null,
        "content": {
            "sections": [
                {"title": "Section Title", "content": "Section content..."}
            ]
        },
        "output_destination": "gdrive" | "local"
    },
    "summary": "Document summary if summarizing",
    "message": "Human-readable response",
    "needs_clarification": true/false,
    "clarification_questions": [
        {"field": "format", "question": "What format?", "options": ["PDF", "Word", "Google Doc"]}
    ]
}

## Document Templates
1. **technical_proposal**: Executive Summary, Technical Approach, Timeline, Team, Budget
2. **project_report**: Overview, Progress, Challenges, Next Steps
3. **meeting_summary**: Attendees, Agenda, Discussion Points, Action Items
4. **general_report**: Introduction, Main Content, Conclusion

## Rules
1. Use context from memory to enrich document content
2. Structure documents with clear sections
3. Keep professional tone unless specified otherwise
4. Include relevant data and references from context
5. For proposals, include specific details from past discussions

Only output valid JSON."""


class DocumentAgent:
    """Document generation and analysis agent."""

    def __init__(self, db: AsyncSession, openai_client: Optional[AsyncOpenAI] = None):
        self.db = db
        self.client = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.chat_model_advanced  # Use advanced model for document generation

    async def process(
        self,
        message: str,
        context: MemoryContext,
        user_id: str,
    ) -> AgentOutput:
        """
        Process a document-related request.

        Args:
            message: User's message
            context: Retrieved context from Memory Agent
            user_id: User ID

        Returns:
            AgentOutput with action or answer
        """
        # Build context
        doc_context = self._build_document_context(context)

        user_prompt = f"""User Request: "{message}"

## Available Context
{doc_context}

Generate or process the requested document. Return JSON:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": DOCUMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=4000
            )

            result = json.loads(response.choices[0].message.content)
            return self._process_result(result, user_id)

        except Exception as e:
            return AgentOutput(
                agent_name="document",
                success=False,
                message=f"Failed to process document request: {str(e)}",
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
                agent_name="document",
                success=True,
                message=message,
                clarifications=clarifications,
            )

        # Handle document generation
        if action_type == "generate_document":
            doc = result.get("document_details", {})

            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action = Action(
                id=action_id,
                type="create_document",
                status="needs_confirmation",
                payload={
                    "title": doc.get("title", "Untitled Document"),
                    "format": doc.get("format", "pdf"),
                    "template": doc.get("template"),
                    "content": doc.get("content", {}),
                    "output_destination": doc.get("output_destination", "gdrive"),
                },
                preview=self._generate_preview(doc),
                missing_fields=[],
            )

            return AgentOutput(
                agent_name="document",
                success=True,
                message=message,
                action=action,
            )

        # Handle summarization
        if action_type == "summarize":
            return AgentOutput(
                agent_name="document",
                success=True,
                message=message,
                data={
                    "summary": result.get("summary"),
                }
            )

        # Handle template application
        if action_type == "apply_template":
            doc = result.get("document_details", {})
            return AgentOutput(
                agent_name="document",
                success=True,
                message=message,
                data={
                    "document": doc,
                }
            )

        # Default answer
        return AgentOutput(
            agent_name="document",
            success=True,
            message=message,
        )

    def _build_document_context(self, context: MemoryContext) -> str:
        """Build context from all memory items for document generation."""
        lines = []

        # Group by source type
        by_source = {}
        for item in context.items:
            source = item.get("source", "unknown")
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(item)

        # Format each source group
        for source, items in by_source.items():
            lines.append(f"\n### {source.upper()} ({len(items)} items)")

            for item in items[:5]:  # Limit per source
                title = item.get("title", "Untitled")
                content = item.get("content", item.get("summary", ""))[:300]
                date = item.get("source_created_at", "")

                lines.append(f"\n**{title}**")
                if date:
                    lines.append(f"Date: {date}")
                lines.append(content)

        return "\n".join(lines) if lines else "No relevant context found."

    def _generate_preview(self, doc: dict) -> str:
        """Generate human-readable preview for document."""
        title = doc.get("title", "Untitled")
        format_ = doc.get("format", "pdf").upper()
        template = doc.get("template", "custom")
        content = doc.get("content", {})
        sections = content.get("sections", [])

        lines = [
            f"Document: {title}",
            f"Format: {format_}",
            f"Template: {template}",
            "",
            "Sections:",
        ]

        for section in sections[:5]:
            section_title = section.get("title", "Untitled Section")
            section_content = section.get("content", "")[:100]
            lines.append(f"  - {section_title}")
            if section_content:
                lines.append(f"    {section_content}...")

        if len(sections) > 5:
            lines.append(f"  ... and {len(sections) - 5} more sections")

        return "\n".join(lines)
