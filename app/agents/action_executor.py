"""
Action Executor - Executes confirmed actions via external APIs.
"""

from datetime import datetime
from typing import Union,  Any, Optional
from uuid import UUID

from app.core.external_api import ExternalAPIClient, ExternalAPIError


class ActionResult:
    """Result of an executed action."""

    def __init__(
        self,
        success: bool,
        action_id: str,
        action_type: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.action_id = action_id
        self.action_type = action_type
        self.result = result
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "result": self.result,
            "error": self.error,
        }


class ActionExecutor:
    """
    Executes confirmed actions via external APIs.

    Supported actions:
    - send_email
    - create_jira_task
    - update_jira_task
    - create_calendar_event
    - create_document
    """

    def __init__(self, external_api: Optional[ExternalAPIClient] = None):
        self.external_api = external_api

    async def execute(
        self,
        user_id: Union[str, UUID],
        action_id: str,
        action_type: str,
        params: dict,
    ) -> ActionResult:
        """
        Execute a single action.

        Args:
            user_id: User ID for API authentication
            action_id: ID of the action being executed
            action_type: Type of action
            params: Action parameters

        Returns:
            ActionResult with success status and result/error
        """
        try:
            handler = self._get_handler(action_type)
            if not handler:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=action_type,
                    error=f"Unknown action type: {action_type}",
                )

            result = await handler(user_id, params)

            return ActionResult(
                success=True,
                action_id=action_id,
                action_type=action_type,
                result=result,
            )

        except ExternalAPIError as e:
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=action_type,
                error=f"API error: {e}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=action_type,
                error=f"Execution error: {e}",
            )

    def _get_handler(self, action_type: str):
        """Get the handler function for an action type."""
        handlers = {
            "send_email": self._execute_send_email,
            "create_jira_task": self._execute_create_jira_task,
            "update_jira_task": self._execute_update_jira_task,
            "create_calendar_event": self._execute_create_event,
            "create_document": self._execute_create_document,
        }
        return handlers.get(action_type)

    async def _execute_send_email(
        self,
        user_id: Union[str, UUID],
        params: dict,
    ) -> dict:
        """Execute send email action."""
        result = await self.external_api.send_email(
            user_id=user_id,
            to=params["to"],
            subject=params["subject"],
            body=params["body"],
            cc=params.get("cc"),
            reply_to_id=params.get("reply_to_id"),
        )

        return {
            "message_id": result.get("message_id"),
            "status": "sent",
            "to": params["to"],
            "subject": params["subject"],
        }

    async def _execute_create_jira_task(
        self,
        user_id: Union[str, UUID],
        params: dict,
    ) -> dict:
        """Execute create Jira task action."""
        result = await self.external_api.create_jira_issue(
            user_id=user_id,
            project_key=params["project_key"],
            issue_type=params["type"],
            summary=params["summary"],
            description=params.get("description"),
            assignee=params.get("assignee"),
            priority=params.get("priority"),
            labels=params.get("labels"),
            sprint=params.get("sprint"),
        )

        return {
            "id": result.get("id"),
            "key": result.get("key"),
            "url": result.get("url"),
            "summary": params["summary"],
        }

    async def _execute_update_jira_task(
        self,
        user_id: Union[str, UUID],
        params: dict,
    ) -> dict:
        """Execute update Jira task action."""
        result = await self.external_api.update_jira_issue(
            user_id=user_id,
            issue_key=params["issue_key"],
            updates=params["updates"],
        )

        return {
            "key": params["issue_key"],
            "updated_fields": list(params["updates"].keys()),
        }

    async def _execute_create_event(
        self,
        user_id: Union[str, UUID],
        params: dict,
    ) -> dict:
        """Execute create calendar event action."""
        start = datetime.fromisoformat(params["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(params["end"].replace("Z", "+00:00"))

        result = await self.external_api.create_event(
            user_id=user_id,
            title=params["title"],
            start=start,
            end=end,
            description=params.get("description"),
            attendees=params.get("attendees"),
            location=params.get("location"),
            create_meet_link=params.get("create_meet_link", False),
        )

        return {
            "id": result.get("id"),
            "url": result.get("url"),
            "meet_link": result.get("meet_link"),
            "title": params["title"],
        }

    async def _execute_create_document(
        self,
        user_id: Union[str, UUID],
        params: dict,
    ) -> dict:
        """Execute create document action."""
        result = await self.external_api.create_document(
            user_id=user_id,
            title=params["title"],
            content=params["content"],
            folder=params.get("folder"),
            format=params.get("format", "google_doc"),
        )

        return {
            "id": result.get("id"),
            "url": result.get("url"),
            "title": params["title"],
        }

    async def execute_batch(
        self,
        user_id: Union[str, UUID],
        actions: list[dict],
    ) -> list[ActionResult]:
        """
        Execute multiple actions in sequence.

        Args:
            user_id: User ID
            actions: List of actions to execute

        Returns:
            List of ActionResults
        """
        results = []

        for action in actions:
            result = await self.execute(
                user_id=user_id,
                action_id=action["id"],
                action_type=action["type"],
                params=action["params"],
            )
            results.append(result)

            # Stop on first failure if critical
            if not result.success and action.get("stop_on_failure", False):
                break

        return results
