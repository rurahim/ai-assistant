"""
API endpoints for external database data.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

from external_db.database import get_local_db_context
from sqlalchemy import text

router = APIRouter(prefix="/external", tags=["External Data"])


# Response models
class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    image: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    provider: str
    provider_account_id: str
    email: str
    name: Optional[str]
    image: Optional[str]
    is_active: bool
    cloud_id: Optional[str]
    cloud_name: Optional[str]
    cloud_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarEventResponse(BaseModel):
    id: UUID
    account_id: UUID
    event_id: str
    title: Optional[str]
    description: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    location: Optional[str]
    is_all_day: bool
    attendees: Optional[str]
    organizer: Optional[str]
    time_zone: Optional[str]
    is_cancelled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailResponse(BaseModel):
    id: UUID
    account_id: UUID
    message_id: str
    thread_id: Optional[str]
    subject: Optional[str]
    from_address: Optional[str]
    to_addresses: Optional[str]
    is_read: bool
    is_starred: bool
    received_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ContactResponse(BaseModel):
    id: UUID
    account_id: UUID
    contact_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    email: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: UUID
    account_id: UUID
    task_id: str
    title: Optional[str]
    description: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    due_date: Optional[datetime]
    completed_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class JiraBoardResponse(BaseModel):
    id: UUID
    account_id: UUID
    board_id: str
    name: Optional[str]
    type: Optional[str]
    project_key: Optional[str]
    project_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JiraIssueResponse(BaseModel):
    id: UUID
    account_id: UUID
    issue_id: str
    issue_key: str
    summary: Optional[str]
    issue_type: Optional[str]
    status: Optional[str]
    priority: Optional[str]
    assignee: Optional[str]
    reporter: Optional[str]
    project_key: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class OnlineMeetingResponse(BaseModel):
    id: UUID
    account_id: UUID
    meeting_id: str
    subject: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    join_url: Optional[str]
    organizer: Optional[str]
    is_cancelled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SyncStatusResponse(BaseModel):
    table: str
    count: int


# Endpoints

@router.get("/health")
async def health_check():
    """Health check for external database connection."""
    try:
        async with get_local_db_context() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "external_data_db"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


@router.get("/sync-status", response_model=list[SyncStatusResponse])
async def get_sync_status():
    """Get row counts for all synced tables."""
    async with get_local_db_context() as session:
        tables = [
            "users", "accounts", "calendar_events", "emails",
            "contacts", "tasks", "jira_boards", "jira_issues", "online_meetings"
        ]
        results = []
        for table in tables:
            result = await session.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            count = result.scalar()
            results.append({"table": table, "count": count})
        return results


@router.get("/users", response_model=list[UserResponse])
async def get_users(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced users."""
    async with get_local_db_context() as session:
        result = await session.execute(
            text("SELECT * FROM users ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset}
        )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID):
    """Get a specific user by ID."""
    async with get_local_db_context() as session:
        result = await session.execute(
            text("SELECT * FROM users WHERE id = :id"),
            {"id": user_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(row._mapping)


@router.get("/users/{user_id}/accounts", response_model=list[AccountResponse])
async def get_user_accounts(user_id: UUID):
    """Get all accounts for a user."""
    async with get_local_db_context() as session:
        result = await session.execute(
            text("SELECT * FROM accounts WHERE user_id = :user_id ORDER BY created_at DESC"),
            {"user_id": user_id}
        )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/accounts", response_model=list[AccountResponse])
async def get_accounts(
    provider: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced accounts."""
    async with get_local_db_context() as session:
        if provider:
            result = await session.execute(
                text("SELECT * FROM accounts WHERE provider = :provider ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
                {"provider": provider, "limit": limit, "offset": offset}
            )
        else:
            result = await session.execute(
                text("SELECT * FROM accounts ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset}
            )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: UUID):
    """Get a specific account by ID."""
    async with get_local_db_context() as session:
        result = await session.execute(
            text("SELECT * FROM accounts WHERE id = :id"),
            {"id": account_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        return dict(row._mapping)


@router.get("/calendar-events", response_model=list[CalendarEventResponse])
async def get_calendar_events(
    account_id: Optional[UUID] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced calendar events."""
    async with get_local_db_context() as session:
        if account_id:
            result = await session.execute(
                text("SELECT * FROM calendar_events WHERE account_id = :account_id ORDER BY start_time DESC LIMIT :limit OFFSET :offset"),
                {"account_id": account_id, "limit": limit, "offset": offset}
            )
        else:
            result = await session.execute(
                text("SELECT * FROM calendar_events ORDER BY start_time DESC LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset}
            )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/calendar-events/{event_id}", response_model=CalendarEventResponse)
async def get_calendar_event(event_id: UUID):
    """Get a specific calendar event by ID."""
    async with get_local_db_context() as session:
        result = await session.execute(
            text("SELECT * FROM calendar_events WHERE id = :id"),
            {"id": event_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Calendar event not found")
        return dict(row._mapping)


@router.get("/emails", response_model=list[EmailResponse])
async def get_emails(
    account_id: Optional[UUID] = None,
    is_read: Optional[bool] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced emails."""
    async with get_local_db_context() as session:
        query = "SELECT * FROM emails WHERE 1=1"
        params = {"limit": limit, "offset": offset}

        if account_id:
            query += " AND account_id = :account_id"
            params["account_id"] = account_id
        if is_read is not None:
            query += " AND is_read = :is_read"
            params["is_read"] = is_read

        query += " ORDER BY received_at DESC LIMIT :limit OFFSET :offset"
        result = await session.execute(text(query), params)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/contacts", response_model=list[ContactResponse])
async def get_contacts(
    account_id: Optional[UUID] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced contacts."""
    async with get_local_db_context() as session:
        if account_id:
            result = await session.execute(
                text("SELECT * FROM contacts WHERE account_id = :account_id ORDER BY display_name LIMIT :limit OFFSET :offset"),
                {"account_id": account_id, "limit": limit, "offset": offset}
            )
        else:
            result = await session.execute(
                text("SELECT * FROM contacts ORDER BY display_name LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset}
            )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/tasks", response_model=list[TaskResponse])
async def get_tasks(
    account_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced tasks."""
    async with get_local_db_context() as session:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = {"limit": limit, "offset": offset}

        if account_id:
            query += " AND account_id = :account_id"
            params["account_id"] = account_id
        if status:
            query += " AND status = :status"
            params["status"] = status

        query += " ORDER BY due_date LIMIT :limit OFFSET :offset"
        result = await session.execute(text(query), params)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/jira-boards", response_model=list[JiraBoardResponse])
async def get_jira_boards(
    account_id: Optional[UUID] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced Jira boards."""
    async with get_local_db_context() as session:
        if account_id:
            result = await session.execute(
                text("SELECT * FROM jira_boards WHERE account_id = :account_id ORDER BY name LIMIT :limit OFFSET :offset"),
                {"account_id": account_id, "limit": limit, "offset": offset}
            )
        else:
            result = await session.execute(
                text("SELECT * FROM jira_boards ORDER BY name LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset}
            )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/jira-issues", response_model=list[JiraIssueResponse])
async def get_jira_issues(
    account_id: Optional[UUID] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced Jira issues."""
    async with get_local_db_context() as session:
        query = "SELECT * FROM jira_issues WHERE 1=1"
        params = {"limit": limit, "offset": offset}

        if account_id:
            query += " AND account_id = :account_id"
            params["account_id"] = account_id
        if status:
            query += " AND status = :status"
            params["status"] = status
        if assignee:
            query += " AND assignee = :assignee"
            params["assignee"] = assignee

        query += " ORDER BY issue_key LIMIT :limit OFFSET :offset"
        result = await session.execute(text(query), params)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/online-meetings", response_model=list[OnlineMeetingResponse])
async def get_online_meetings(
    account_id: Optional[UUID] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """Get all synced online meetings."""
    async with get_local_db_context() as session:
        if account_id:
            result = await session.execute(
                text("SELECT * FROM online_meetings WHERE account_id = :account_id ORDER BY start_time DESC LIMIT :limit OFFSET :offset"),
                {"account_id": account_id, "limit": limit, "offset": offset}
            )
        else:
            result = await session.execute(
                text("SELECT * FROM online_meetings ORDER BY start_time DESC LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset}
            )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.post("/sync")
async def trigger_sync():
    """Trigger a sync from the external database."""
    try:
        from external_db.sync import sync_all
        results = await sync_all()
        return {
            "status": "success",
            "message": "Sync completed",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
