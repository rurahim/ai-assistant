"""
External API client for Frontend/Backend data service.

This client communicates with the external service that manages:
- Gmail/Outlook emails
- GDrive/OneDrive documents
- Calendar events
- Jira tasks
"""

from datetime import datetime
from typing import Union,  Any, Optional
from uuid import UUID

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class ExternalAPIError(Exception):
    """Exception for external API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ExternalAPIClient:
    """
    Client for the Frontend/Backend data service API.

    Provides methods to:
    - Fetch emails, documents, events, tasks
    - Create Jira tasks
    - Send emails
    - Create calendar events
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url or settings.external_api_base
        self.api_key = api_key or settings.external_api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ExternalAPIClient":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """Make HTTP request with retry logic."""
        response = await self.client.request(method, endpoint, **kwargs)

        if response.status_code >= 400:
            raise ExternalAPIError(
                f"API error: {response.text}",
                status_code=response.status_code,
            )

        return response.json()

    # ============== Email Operations ==============

    async def get_emails(
        self,
        user_id: Union[str, UUID],
        since: Optional[datetime] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict:
        """
        Fetch emails for a user.

        Returns:
            {
                "items": [...],
                "next_cursor": "...",
                "has_more": true/false
            }
        """
        params = {"limit": limit}
        if since:
            params["since"] = since.isoformat()
        if cursor:
            params["cursor"] = cursor

        return await self._request(
            "GET",
            f"/users/{user_id}/emails",
            params=params,
        )

    async def get_email(self, user_id: Union[str, UUID], email_id: str) -> dict:
        """Fetch a single email with full content."""
        return await self._request(
            "GET",
            f"/users/{user_id}/emails/{email_id}",
        )

    async def send_email(
        self,
        user_id: Union[str, UUID],
        to: list[str],
        subject: str,
        body: str,
        cc: Optional[list[str]] = None,
        reply_to_id: Optional[str] = None,
    ) -> dict:
        """Send an email."""
        payload = {
            "to": to,
            "subject": subject,
            "body": body,
        }
        if cc:
            payload["cc"] = cc
        if reply_to_id:
            payload["reply_to_id"] = reply_to_id

        return await self._request(
            "POST",
            f"/users/{user_id}/emails/send",
            json=payload,
        )

    # ============== Document Operations ==============

    async def get_documents(
        self,
        user_id: Union[str, UUID],
        since: Optional[datetime] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
        mime_types: Optional[list[str]] = None,
    ) -> dict:
        """Fetch documents for a user."""
        params = {"limit": limit}
        if since:
            params["since"] = since.isoformat()
        if cursor:
            params["cursor"] = cursor
        if mime_types:
            params["mime_types"] = ",".join(mime_types)

        return await self._request(
            "GET",
            f"/users/{user_id}/documents",
            params=params,
        )

    async def get_document(self, user_id: Union[str, UUID], doc_id: str) -> dict:
        """Fetch a single document with full content."""
        return await self._request(
            "GET",
            f"/users/{user_id}/documents/{doc_id}",
        )

    async def create_document(
        self,
        user_id: Union[str, UUID],
        title: str,
        content: str,
        folder: Optional[str] = None,
        format: str = "google_doc",
    ) -> dict:
        """Create a new document."""
        payload = {
            "title": title,
            "content": content,
            "format": format,
        }
        if folder:
            payload["folder"] = folder

        return await self._request(
            "POST",
            f"/users/{user_id}/documents",
            json=payload,
        )

    # ============== Calendar Operations ==============

    async def get_events(
        self,
        user_id: Union[str, UUID],
        start_date: datetime,
        end_date: datetime,
        limit: int = 50,
    ) -> dict:
        """Fetch calendar events for a user."""
        params = {
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "limit": limit,
        }

        return await self._request(
            "GET",
            f"/users/{user_id}/events",
            params=params,
        )

    async def create_event(
        self,
        user_id: Union[str, UUID],
        title: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        attendees: Optional[list[str]] = None,
        location: Optional[str] = None,
        create_meet_link: bool = False,
    ) -> dict:
        """Create a calendar event."""
        payload = {
            "title": title,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "create_meet_link": create_meet_link,
        }
        if description:
            payload["description"] = description
        if attendees:
            payload["attendees"] = attendees
        if location:
            payload["location"] = location

        return await self._request(
            "POST",
            f"/users/{user_id}/calendar/events",
            json=payload,
        )

    # ============== Jira Operations ==============

    async def get_jira_issues(
        self,
        user_id: Union[str, UUID],
        since: Optional[datetime] = None,
        project_keys: Optional[list[str]] = None,
        status: Optional[list[str]] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> dict:
        """Fetch Jira issues for a user."""
        params = {"limit": limit}
        if since:
            params["since"] = since.isoformat()
        if project_keys:
            params["project_keys"] = ",".join(project_keys)
        if status:
            params["status"] = ",".join(status)
        if cursor:
            params["cursor"] = cursor

        return await self._request(
            "GET",
            f"/users/{user_id}/jira/issues",
            params=params,
        )

    async def create_jira_issue(
        self,
        user_id: Union[str, UUID],
        project_key: str,
        issue_type: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[list[str]] = None,
        sprint: Optional[str] = None,
    ) -> dict:
        """Create a Jira issue."""
        payload = {
            "project_key": project_key,
            "type": issue_type,
            "summary": summary,
        }
        if description:
            payload["description"] = description
        if assignee:
            payload["assignee"] = assignee
        if priority:
            payload["priority"] = priority
        if labels:
            payload["labels"] = labels
        if sprint:
            payload["sprint"] = sprint

        return await self._request(
            "POST",
            f"/users/{user_id}/jira/issues",
            json=payload,
        )

    async def update_jira_issue(
        self,
        user_id: Union[str, UUID],
        issue_key: str,
        updates: dict,
    ) -> dict:
        """Update a Jira issue."""
        return await self._request(
            "PUT",
            f"/users/{user_id}/jira/issues/{issue_key}",
            json=updates,
        )


# Global client instance
_external_client: Optional[ExternalAPIClient] = None


async def get_external_api() -> ExternalAPIClient:
    """Get the global external API client."""
    global _external_client
    if _external_client is None:
        _external_client = ExternalAPIClient()
        await _external_client.connect()
    return _external_client


async def close_external_api() -> None:
    """Close the global external API client."""
    global _external_client
    if _external_client:
        await _external_client.disconnect()
        _external_client = None
