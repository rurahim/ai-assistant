"""
Sync script to fetch data from external database and store in local database.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from external_db.database import (
    get_external_db_context,
    get_local_db_context,
    init_local_db,
    close_all_connections,
)
from external_db.models import (
    User,
    Account,
    AIPreference,
    CalendarEvent,
    Email,
    Contact,
    Task,
    JiraBoard,
    JiraIssue,
    OnlineMeeting,
)


# Column mappings from external DB (camelCase) to local DB (snake_case)
COLUMN_MAPPINGS = {
    "users": {
        "id": "id",
        "email": "email",
        "name": "name",
        "image": "image",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "accounts": {
        "id": "id",
        "userId": "user_id",
        "provider": "provider",
        "providerAccountId": "provider_account_id",
        "email": "email",
        "name": "name",
        "image": "image",
        "accessToken": "access_token",
        "refreshToken": "refresh_token",
        "expiresAt": "expires_at",
        "scope": "scope",
        "isActive": "is_active",
        "cloudId": "cloud_id",
        "cloudName": "cloud_name",
        "cloudUrl": "cloud_url",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "ai_preferences": {
        "id": "id",
        "userId": "user_id",
        "tone": "tone",
        "length": "length",
        "includeGreeting": "include_greeting",
        "includeSignature": "include_signature",
        "customInstructions": "custom_instructions",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "calendar_events": {
        "id": "id",
        "accountId": "account_id",
        "eventId": "event_id",
        "title": "title",
        "description": "description",
        "startTime": "start_time",
        "endTime": "end_time",
        "location": "location",
        "isAllDay": "is_all_day",
        "attendees": "attendees",
        "organizer": "organizer",
        "recurrence": "recurrence",
        "timeZone": "time_zone",
        "isCancelled": "is_cancelled",
        "metadata": "metadata",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "emails": {
        "id": "id",
        "accountId": "account_id",
        "messageId": "message_id",
        "threadId": "thread_id",
        "subject": "subject",
        "from": "from_address",
        "to": "to_addresses",
        "cc": "cc",
        "bcc": "bcc",
        "body": "body",
        "bodyHtml": "body_html",
        "isRead": "is_read",
        "isStarred": "is_starred",
        "isDraft": "is_draft",
        "labels": "labels",
        "attachments": "attachments",
        "receivedAt": "received_at",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "contacts": {
        "id": "id",
        "accountId": "account_id",
        "contactId": "contact_id",
        "firstName": "first_name",
        "lastName": "last_name",
        "displayName": "display_name",
        "email": "email",
        "emails": "emails",
        "phoneNumbers": "phone_numbers",
        "company": "company",
        "jobTitle": "job_title",
        "notes": "notes",
        "photoUrl": "photo_url",
        "metadata": "metadata",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "tasks": {
        "id": "id",
        "accountId": "account_id",
        "taskId": "task_id",
        "title": "title",
        "description": "description",
        "status": "status",
        "priority": "priority",
        "dueDate": "due_date",
        "completedDate": "completed_date",
        "listId": "list_id",
        "listName": "list_name",
        "metadata": "metadata",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "jira_boards": {
        "id": "id",
        "accountId": "account_id",
        "boardId": "board_id",
        "name": "name",
        "type": "type",
        "projectKey": "project_key",
        "projectName": "project_name",
        "location": "location",
        "metadata": "metadata",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "jira_issues": {
        "id": "id",
        "accountId": "account_id",
        "issueId": "issue_id",
        "issueKey": "issue_key",
        "summary": "summary",
        "description": "description",
        "issueType": "issue_type",
        "status": "status",
        "priority": "priority",
        "assignee": "assignee",
        "reporter": "reporter",
        "projectKey": "project_key",
        "projectName": "project_name",
        "labels": "labels",
        "issueCreatedAt": "issue_created_at",
        "issueUpdatedAt": "issue_updated_at",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
    "online_meetings": {
        "id": "id",
        "accountId": "account_id",
        "meetingId": "meeting_id",
        "subject": "subject",
        "description": "description",
        "startTime": "start_time",
        "endTime": "end_time",
        "timeZone": "time_zone",
        "isOnlineMeeting": "is_online_meeting",
        "joinUrl": "join_url",
        "conferenceId": "conference_id",
        "dialInUrl": "dial_in_url",
        "attendees": "attendees",
        "organizer": "organizer",
        "isCancelled": "is_cancelled",
        "metadata": "metadata",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
    },
}

# Table to model mapping
TABLE_MODEL_MAP = {
    "users": User,
    "accounts": Account,
    "ai_preferences": AIPreference,
    "calendar_events": CalendarEvent,
    "emails": Email,
    "contacts": Contact,
    "tasks": Task,
    "jira_boards": JiraBoard,
    "jira_issues": JiraIssue,
    "online_meetings": OnlineMeeting,
}

# Sync order (respecting foreign key dependencies)
SYNC_ORDER = [
    "users",
    "accounts",
    "ai_preferences",
    "calendar_events",
    "emails",
    "contacts",
    "tasks",
    "jira_boards",
    "jira_issues",
    "online_meetings",
]


def map_row(table_name: str, row: dict) -> dict:
    """Map external DB column names to local DB column names."""
    mapping = COLUMN_MAPPINGS.get(table_name, {})
    mapped = {}
    for ext_col, local_col in mapping.items():
        if ext_col in row:
            mapped[local_col] = row[ext_col]
    return mapped


async def fetch_external_table(session: AsyncSession, table_name: str) -> list[dict]:
    """Fetch all rows from an external table."""
    query = text(f'SELECT * FROM "{table_name}"')
    result = await session.execute(query)
    columns = result.keys()
    rows = result.fetchall()
    return [dict(zip(columns, row)) for row in rows]


async def upsert_local_table(
    session: AsyncSession,
    table_name: str,
    rows: list[dict],
) -> int:
    """Upsert rows into local table using raw SQL ON CONFLICT."""
    if not rows:
        return 0

    mapped_rows = [map_row(table_name, row) for row in rows]
    if not mapped_rows:
        return 0

    # Get column names from the first row
    columns = list(mapped_rows[0].keys())

    # Build the INSERT ... ON CONFLICT DO UPDATE statement using raw SQL
    # This avoids the SQLAlchemy 'metadata' attribute conflict
    col_names = ", ".join(f'"{col}"' for col in columns)
    placeholders = ", ".join(f":{col}" for col in columns)
    update_cols = ", ".join(f'"{col}" = EXCLUDED."{col}"' for col in columns if col != "id")

    sql = f"""
        INSERT INTO "{table_name}" ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET {update_cols}
    """

    # Execute for each row (can be batched for better performance)
    for row in mapped_rows:
        await session.execute(text(sql), row)

    return len(mapped_rows)


async def sync_table(table_name: str) -> dict:
    """Sync a single table from external to local database."""
    print(f"  Syncing {table_name}...")

    async with get_external_db_context() as ext_session:
        rows = await fetch_external_table(ext_session, table_name)

    if not rows:
        print(f"    No data in {table_name}")
        return {"table": table_name, "synced": 0, "status": "empty"}

    async with get_local_db_context() as local_session:
        count = await upsert_local_table(local_session, table_name, rows)

    print(f"    Synced {count} rows")
    return {"table": table_name, "synced": count, "status": "success"}


async def sync_users_with_external_id(table_name: str) -> dict:
    """Sync users table and ensure external_user_id is set."""
    print(f"  Syncing {table_name} with external_user_id...")

    async with get_external_db_context() as ext_session:
        rows = await fetch_external_table(ext_session, table_name)

    if not rows:
        print(f"    No data in {table_name}")
        return {"table": table_name, "synced": 0, "status": "empty"}

    async with get_local_db_context() as local_session:
        # Insert users with external_user_id set to id
        count = 0
        for row in rows:
            mapped = map_row(table_name, row)
            user_id = str(mapped["id"])

            # Use raw SQL with proper parameter binding (no type cast in placeholder)
            sql = text("""
                INSERT INTO users (id, email, name, image, created_at, updated_at, external_user_id, preferences)
                VALUES (:id, :email, :name, :image, :created_at, :updated_at, :external_user_id, '{}'::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    image = EXCLUDED.image,
                    updated_at = EXCLUDED.updated_at
            """)
            await local_session.execute(sql, {
                "id": mapped["id"],
                "email": mapped["email"],
                "name": mapped.get("name"),
                "image": mapped.get("image"),
                "created_at": mapped["created_at"],
                "updated_at": mapped["updated_at"],
                "external_user_id": user_id,
            })
            count += 1

    print(f"    Synced {count} rows")
    return {"table": table_name, "synced": count, "status": "success"}


async def sync_to_knowledge_items() -> dict:
    """
    Transform synced raw data into knowledge_items with embeddings.
    Uses existing SyncService and EmbeddingService code paths.
    """
    import json
    from app.database import get_db_context
    from app.models import KnowledgeItem
    from app.services.embedding_service import EmbeddingService
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy import select

    print("\n" + "=" * 60)
    print("Creating Knowledge Items with Embeddings")
    print("=" * 60)

    embedding_service = EmbeddingService()
    total_items = 0

    async with get_db_context() as session:
        # Get all users and their accounts
        users_result = await session.execute(text("SELECT id, external_user_id FROM users"))
        users = users_result.fetchall()

        for user_row in users:
            user_id = user_row[0]
            print(f"\n  Processing user: {user_id}")

            # Get accounts for this user
            accounts_result = await session.execute(
                text("SELECT id, provider FROM accounts WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            accounts = accounts_result.fetchall()
            account_ids = [a[0] for a in accounts]

            if not account_ids:
                print(f"    No accounts for user")
                continue

            # Process emails -> knowledge_items using ORM
            emails_result = await session.execute(
                text("""
                    SELECT id, message_id, subject, from_address, to_addresses, body,
                           is_read, thread_id, labels, received_at, account_id
                    FROM emails
                    WHERE account_id = ANY(:account_ids)
                """),
                {"account_ids": account_ids}
            )
            emails = emails_result.fetchall()
            print(f"    Processing {len(emails)} emails...")

            for email in emails:
                try:
                    email_id, message_id, subject, from_addr, to_addr, body, is_read, thread_id, labels, received_at, account_id = email

                    # Get provider from account
                    source_type = "gmail"
                    for acc in accounts:
                        if acc[0] == account_id and "microsoft" in str(acc[1]).lower():
                            source_type = "outlook"
                            break

                    content = (body or "")[:10000]
                    summary = f"Email from {from_addr}: {subject}"[:500] if from_addr and subject else subject or ""
                    # Use ORM insert like existing SyncService
                    stmt = insert(KnowledgeItem).values(
                        user_id=str(user_id),
                        source_type=source_type,
                        source_id=str(email_id),
                        content_type="email",
                        title=subject,
                        summary=summary,
                        content=content,
                        item_metadata={
                            "from": from_addr,
                            "to": to_addr,
                            "thread_id": thread_id,
                            "labels": labels,
                            "is_read": is_read,
                        },
                        source_created_at=received_at,
                    ).on_conflict_do_update(
                        index_elements=["user_id", "source_type", "source_id"],
                        set_={
                            "title": subject,
                            "summary": summary,
                            "content": content,
                            "synced_at": datetime.now(),
                        },
                    ).returning(KnowledgeItem.id)

                    result = await session.execute(stmt)
                    item_id = result.scalar_one()

                    # Get the knowledge item for embedding (existing code path)
                    item_result = await session.execute(
                        select(KnowledgeItem).where(KnowledgeItem.id == item_id)
                    )
                    knowledge_item = item_result.scalar_one()

                    # Create embedding using existing embed_knowledge_item
                    text_for_embedding = f"Subject: {subject}\nFrom: {from_addr}\n{content[:3000]}"
                    await embedding_service.embed_knowledge_item(session, knowledge_item, text_for_embedding)

                    total_items += 1
                except Exception as e:
                    print(f"      Error processing email: {e}")
                    continue

            await session.commit()

            # Process calendar_events -> knowledge_items using ORM
            events_result = await session.execute(
                text("""
                    SELECT id, event_id, title, description, start_time, end_time,
                           location, attendees, organizer, account_id
                    FROM calendar_events
                    WHERE account_id = ANY(:account_ids)
                """),
                {"account_ids": account_ids}
            )
            events = events_result.fetchall()
            print(f"    Processing {len(events)} calendar events...")

            for event in events:
                try:
                    event_row_id, event_id, title, description, start_time, end_time, location, attendees, organizer, account_id = event

                    content = description or ""
                    summary = f"Event: {title}" if title else ""

                    stmt = insert(KnowledgeItem).values(
                        user_id=str(user_id),
                        source_type="calendar",
                        source_id=str(event_row_id),
                        content_type="event",
                        title=title,
                        summary=summary,
                        content=content,
                        item_metadata={
                            "start": str(start_time) if start_time else None,
                            "end": str(end_time) if end_time else None,
                            "location": location,
                            "attendees": attendees,
                            "organizer": organizer,
                        },
                        source_created_at=start_time,
                    ).on_conflict_do_update(
                        index_elements=["user_id", "source_type", "source_id"],
                        set_={
                            "title": title,
                            "content": content,
                            "synced_at": datetime.now(),
                        },
                    ).returning(KnowledgeItem.id)

                    result = await session.execute(stmt)
                    item_id = result.scalar_one()

                    # Get the knowledge item for embedding
                    item_result = await session.execute(
                        select(KnowledgeItem).where(KnowledgeItem.id == item_id)
                    )
                    knowledge_item = item_result.scalar_one()

                    text_for_embedding = f"{title}\n{description or ''}"
                    await embedding_service.embed_knowledge_item(session, knowledge_item, text_for_embedding)

                    total_items += 1
                except Exception as e:
                    print(f"      Error processing event: {e}")
                    continue

            await session.commit()

            # Process jira_issues -> knowledge_items using ORM
            issues_result = await session.execute(
                text("""
                    SELECT id, issue_key, summary, description, status, priority,
                           assignee, reporter, project_key, issue_created_at, account_id
                    FROM jira_issues
                    WHERE account_id = ANY(:account_ids)
                """),
                {"account_ids": account_ids}
            )
            issues = issues_result.fetchall()
            print(f"    Processing {len(issues)} jira issues...")

            for issue in issues:
                try:
                    issue_row_id, issue_key, issue_summary, description, status, priority, assignee, reporter, project_key, issue_created_at, account_id = issue

                    content = description or ""
                    summary_text = f"[{issue_key}] {issue_summary}" if issue_key else issue_summary

                    stmt = insert(KnowledgeItem).values(
                        user_id=str(user_id),
                        source_type="jira",
                        source_id=issue_key or str(issue_row_id),
                        content_type="task",
                        title=issue_summary,
                        summary=summary_text,
                        content=content,
                        item_metadata={
                            "project_key": project_key,
                            "status": status,
                            "priority": priority,
                            "assignee": assignee,
                            "reporter": reporter,
                        },
                        source_created_at=issue_created_at,
                    ).on_conflict_do_update(
                        index_elements=["user_id", "source_type", "source_id"],
                        set_={
                            "title": issue_summary,
                            "content": content,
                            "synced_at": datetime.now(),
                        },
                    ).returning(KnowledgeItem.id)

                    result = await session.execute(stmt)
                    item_id = result.scalar_one()

                    # Get the knowledge item for embedding
                    item_result = await session.execute(
                        select(KnowledgeItem).where(KnowledgeItem.id == item_id)
                    )
                    knowledge_item = item_result.scalar_one()

                    text_for_embedding = f"{issue_summary}\n{content}"
                    await embedding_service.embed_knowledge_item(session, knowledge_item, text_for_embedding)

                    total_items += 1
                except Exception as e:
                    print(f"      Error processing jira issue: {e}")
                    continue

            await session.commit()

            # Process online_meetings -> knowledge_items using ORM
            meetings_result = await session.execute(
                text("""
                    SELECT id, meeting_id, subject, description, start_time, end_time,
                           join_url, attendees, organizer, account_id
                    FROM online_meetings
                    WHERE account_id = ANY(:account_ids)
                """),
                {"account_ids": account_ids}
            )
            meetings = meetings_result.fetchall()
            print(f"    Processing {len(meetings)} online meetings...")

            for meeting in meetings:
                try:
                    meeting_row_id, meeting_id, subject, description, start_time, end_time, join_url, attendees, organizer, account_id = meeting

                    content = description or ""
                    summary_text = f"Meeting: {subject}" if subject else ""

                    stmt = insert(KnowledgeItem).values(
                        user_id=str(user_id),
                        source_type="calendar",  # Use calendar source for online meetings
                        source_id=str(meeting_row_id),
                        content_type="meeting",
                        title=subject,
                        summary=summary_text,
                        content=content,
                        item_metadata={
                            "start": str(start_time) if start_time else None,
                            "end": str(end_time) if end_time else None,
                            "join_url": join_url,
                            "attendees": attendees,
                            "organizer": organizer,
                        },
                        source_created_at=start_time,
                    ).on_conflict_do_update(
                        index_elements=["user_id", "source_type", "source_id"],
                        set_={
                            "title": subject,
                            "content": content,
                            "synced_at": datetime.now(),
                        },
                    ).returning(KnowledgeItem.id)

                    result = await session.execute(stmt)
                    item_id = result.scalar_one()

                    # Get the knowledge item for embedding
                    item_result = await session.execute(
                        select(KnowledgeItem).where(KnowledgeItem.id == item_id)
                    )
                    knowledge_item = item_result.scalar_one()

                    text_for_embedding = f"{subject}\n{description or ''}"
                    await embedding_service.embed_knowledge_item(session, knowledge_item, text_for_embedding)

                    total_items += 1
                except Exception as e:
                    print(f"      Error processing online meeting: {e}")
                    continue

            await session.commit()

    print(f"\nTotal knowledge items created: {total_items}")
    return {"knowledge_items": total_items, "status": "success"}


async def sync_all() -> list[dict]:
    """Sync all tables from external to local database."""
    print("=" * 60)
    print("Starting External Database Sync")
    print("=" * 60)

    # Initialize local database tables
    print("\nInitializing local database...")
    await init_local_db()
    print("Local database initialized.\n")

    results = []
    for table_name in SYNC_ORDER:
        try:
            # Special handling for users table
            if table_name == "users":
                result = await sync_users_with_external_id(table_name)
            else:
                result = await sync_table(table_name)
            results.append(result)
        except Exception as e:
            print(f"    Error syncing {table_name}: {e}")
            results.append({"table": table_name, "synced": 0, "status": f"error: {e}"})

    print("\n" + "=" * 60)
    print("Sync Summary")
    print("=" * 60)
    total = 0
    for r in results:
        status = r["status"]
        count = r["synced"]
        total += count
        print(f"  {r['table']}: {count} rows ({status})")

    print(f"\nTotal rows synced: {total}")

    # Now transform raw data into knowledge_items with embeddings
    try:
        ki_result = await sync_to_knowledge_items()
        results.append(ki_result)
    except Exception as e:
        print(f"Error creating knowledge items: {e}")
        import traceback
        traceback.print_exc()
        results.append({"knowledge_items": 0, "status": f"error: {e}"})

    return results


async def main():
    """Main entry point."""
    try:
        await sync_all()
    finally:
        await close_all_connections()


if __name__ == "__main__":
    asyncio.run(main())
