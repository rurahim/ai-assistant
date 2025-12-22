"""
Standardized schemas for the multi-agent system.

These schemas define the request/response formats for all agent interactions.
"""

from datetime import datetime
from typing import Optional, Literal, Any
from uuid import UUID
from pydantic import BaseModel, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class Attachment(BaseModel):
    """Attachment for ad-hoc content (emails, documents)."""
    type: Literal["email", "email_thread", "document"]
    content: Optional[dict] = None  # Ad-hoc content in payload
    source_id: Optional[str] = None  # Reference to existing item in DB


class ChatRequest(BaseModel):
    """Main chat request schema."""
    user_id: str = Field(..., description="User ID for identification")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    message: str = Field(..., description="User's message")
    attachments: Optional[list[Attachment]] = Field(None, description="Optional attachments")
    confirm_action: Optional[str] = Field(None, description="Action ID to confirm")


# =============================================================================
# ACTION SCHEMAS
# =============================================================================

class ActionPayload(BaseModel):
    """Base action payload."""
    pass


class SendEmailPayload(ActionPayload):
    """Payload for send_email action."""
    to: list[str]
    cc: Optional[list[str]] = None
    bcc: Optional[list[str]] = None
    subject: str
    body: str
    reply_to_id: Optional[str] = None
    attachments: Optional[list[dict]] = None


class CreateMeetingPayload(ActionPayload):
    """Payload for create_meeting action."""
    title: str
    description: Optional[str] = None
    start_time: str  # ISO format
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = 30
    attendees: list[str]
    location: Optional[str] = None
    video_conference: bool = True
    reminder_minutes: Optional[int] = 15


class CreateJiraTaskPayload(ActionPayload):
    """Payload for create_jira_task action."""
    project_key: str
    issue_type: str = "Task"
    summary: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    priority: Optional[str] = "Medium"
    labels: Optional[list[str]] = None
    due_date: Optional[str] = None


class UpdateJiraTaskPayload(ActionPayload):
    """Payload for update_jira_task action."""
    issue_key: str
    summary: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None


class CreateDocumentPayload(ActionPayload):
    """Payload for create_document action."""
    title: str
    format: Literal["pdf", "docx", "gdoc", "markdown"] = "pdf"
    template: Optional[str] = None
    content: dict  # sections, paragraphs, etc.
    output_destination: Optional[str] = "gdrive"


class Action(BaseModel):
    """Action to be executed by backend."""
    id: str = Field(..., description="Unique action ID (act_xxxxxxxx)")
    type: Literal[
        "send_email",
        "create_meeting",
        "update_meeting",
        "cancel_meeting",
        "create_jira_task",
        "update_jira_task",
        "create_document",
        "multi_action"
    ]
    status: Literal["needs_confirmation", "ready"]
    payload: dict
    preview: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None


# =============================================================================
# CLARIFICATION SCHEMAS
# =============================================================================

class ClarificationQuestion(BaseModel):
    """Question to ask user for missing information."""
    field: str = Field(..., description="Field name that needs clarification")
    question: str = Field(..., description="Natural language question")
    options: Optional[list[str]] = Field(None, description="Suggested options")
    required: bool = True


# =============================================================================
# SOURCE SCHEMAS
# =============================================================================

class SourceReference(BaseModel):
    """Reference to a source used in the response."""
    id: str
    type: str  # email, calendar, jira, document, gmail, outlook, meeting, etc.
    title: str
    date: Optional[str] = None
    relevance: Optional[float] = None


# =============================================================================
# METADATA SCHEMAS
# =============================================================================

class ResponseMetadata(BaseModel):
    """Metadata about the response generation."""
    agents_used: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    processing_time_ms: int = 0
    intent: Optional[str] = None
    confidence: Optional[float] = None
    query_analysis: Optional[dict] = None


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class ChatResponse(BaseModel):
    """Standardized chat response schema."""
    response_type: Literal["answer", "action", "clarification"]
    message: str
    session_id: str

    # For actions
    action: Optional[Action] = None

    # For clarifications
    clarifications: Optional[list[ClarificationQuestion]] = None

    # Sources used
    sources: list[SourceReference] = Field(default_factory=list)

    # Metadata
    metadata: Optional[ResponseMetadata] = None


class ErrorDetail(BaseModel):
    """Error detail schema."""
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: ErrorDetail


# =============================================================================
# INTERNAL AGENT SCHEMAS
# =============================================================================

class TriageResult(BaseModel):
    """Result from triage agent's intent classification."""
    intent: str
    confidence: float
    agents_needed: list[str]
    requires_context: bool = True
    requires_clarification: bool = False
    clarification_fields: list[str] = Field(default_factory=list)
    synthesized_request: Optional[str] = None  # Combined request from multi-turn conversation
    reasoning: str = ""


class MemoryContext(BaseModel):
    """Context retrieved by memory agent."""
    items: list[dict] = Field(default_factory=list)
    entities: dict[str, dict] = Field(default_factory=dict)  # name -> {email, type, org}
    user_preferences: dict = Field(default_factory=dict)
    episodic: list[dict] = Field(default_factory=list)
    query_analysis: Optional[dict] = None


class AgentOutput(BaseModel):
    """Output from a specialist agent."""
    agent_name: str
    success: bool
    message: str
    action: Optional[Action] = None
    clarifications: Optional[list[ClarificationQuestion]] = None
    data: Optional[dict] = None


# =============================================================================
# SESSION SCHEMAS
# =============================================================================

class PendingAction(BaseModel):
    """Pending action stored in session."""
    id: str
    type: str
    payload: dict
    preview: str
    created_at: datetime
    expires_at: datetime


class SessionState(BaseModel):
    """Session state stored in Redis/DB."""
    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    pending_actions: list[PendingAction] = Field(default_factory=list)
    context_summary: Optional[str] = None
    last_intent: Optional[str] = None
