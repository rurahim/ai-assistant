"""
Query Analyzer Service - LLM-based query understanding.

Extracts structured information from natural language queries:
- Entities (people names, emails, projects)
- Time ranges (dates, relative times like "last week", "November 2025")
- Intent/source type (emails, tasks, documents, events)

This is a GENERIC solution that handles any query format.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()


@dataclass
class QueryAnalysis:
    """Structured query analysis result."""

    # Original query
    query: str

    # Extracted entities (names, emails)
    entities: list[str] = field(default_factory=list)

    # Detected sources (gmail, jira, calendar, gdrive, etc.)
    sources: list[str] = field(default_factory=list)

    # Time range
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    time_type: Optional[str] = None  # "past", "future", "specific"

    # Intent
    intent: str = "search"  # search, create, update, delete

    # Is this asking for most recent items?
    is_temporal: bool = False

    # Confidence
    confidence: float = 0.0


class QueryAnalyzer:
    """
    Analyzes natural language queries to extract structured information.

    Uses a hybrid approach:
    1. Fast regex/keyword matching for common patterns
    2. LLM for complex/ambiguous queries
    """

    # Source keywords mapping
    SOURCE_KEYWORDS = {
        "email": ["gmail", "outlook"],
        "emails": ["gmail", "outlook"],
        "mail": ["gmail", "outlook"],
        "inbox": ["gmail", "outlook"],
        "message": ["gmail", "outlook"],
        "messages": ["gmail", "outlook"],
        "document": ["gdrive", "onedrive"],
        "documents": ["gdrive", "onedrive"],
        "doc": ["gdrive", "onedrive"],
        "docs": ["gdrive", "onedrive"],
        "file": ["gdrive", "onedrive"],
        "files": ["gdrive", "onedrive"],
        "task": ["jira"],
        "tasks": ["jira"],
        "ticket": ["jira"],
        "tickets": ["jira"],
        "issue": ["jira"],
        "issues": ["jira"],
        "jira": ["jira"],
        "assigned": ["jira"],  # "assigned to X" usually means tasks
        "assignee": ["jira"],
        "meeting": ["calendar"],
        "meetings": ["calendar"],
        "calendar": ["calendar"],
        "event": ["calendar"],
        "events": ["calendar"],
        "appointment": ["calendar"],
        "schedule": ["calendar"],
    }

    # Temporal keywords
    PAST_TEMPORAL = ["last", "latest", "recent", "newest", "previous", "yesterday", "ago"]
    FUTURE_TEMPORAL = ["next", "upcoming", "coming up", "tomorrow", "scheduled", "future"]

    # Month names for date parsing
    MONTHS = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def analyze(self, query: str, use_llm: bool = True) -> QueryAnalysis:
        """
        Analyze a query to extract structured information.

        Args:
            query: Natural language query
            use_llm: Whether to use LLM for complex queries (default True)

        Returns:
            QueryAnalysis with extracted entities, sources, dates, etc.
        """
        result = QueryAnalysis(query=query)

        # 1. Fast pattern matching first
        self._extract_sources_fast(query, result)
        self._extract_entities_fast(query, result)
        self._extract_dates_fast(query, result)
        self._detect_temporal_type(query, result)

        # 2. Use LLM for complex queries or low confidence
        if use_llm and result.confidence < 0.7:
            await self._analyze_with_llm(query, result)

        return result

    def _extract_sources_fast(self, query: str, result: QueryAnalysis) -> None:
        """Fast source detection using keywords."""
        query_lower = query.lower()
        sources = set()

        for keyword, source_list in self.SOURCE_KEYWORDS.items():
            if keyword in query_lower:
                sources.update(source_list)

        result.sources = list(sources)
        if sources:
            result.confidence += 0.3

    def _extract_entities_fast(self, query: str, result: QueryAnalysis) -> None:
        """Fast entity extraction using patterns."""
        entities = []

        # Email pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, query)
        entities.extend(emails)

        # "from X", "to X", "by X", "assigned to X" patterns
        name_patterns = [
            r'from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'assigned\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'assignee[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r"([A-Z][a-z]+)'s\s+(?:tasks?|emails?|documents?|meetings?)",
        ]

        for pattern in name_patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)

        # Capitalized words that might be names (but not at start of sentence)
        # Skip common words
        skip_words = {"the", "a", "an", "in", "on", "at", "to", "from", "by", "for",
                     "what", "where", "when", "how", "which", "who", "tasks", "emails",
                     "documents", "meetings", "calendar", "jira", "gmail", "show", "find",
                     "get", "list", "search", "all", "my", "i", "me", "november", "december",
                     "january", "february", "march", "april", "may", "june", "july", "august",
                     "september", "october", "monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"}

        words = query.split()
        for i, word in enumerate(words):
            # Skip first word (might be capitalized as sentence start)
            if i == 0:
                continue
            # Check if capitalized and not a common word
            if word[0].isupper() and word.lower() not in skip_words:
                # Clean punctuation
                clean_word = re.sub(r'[^\w]', '', word)
                if clean_word and len(clean_word) >= 2:
                    entities.append(clean_word)

        result.entities = list(set(entities))
        if entities:
            result.confidence += 0.2

    def _extract_dates_fast(self, query: str, result: QueryAnalysis) -> None:
        """Fast date extraction using patterns."""
        query_lower = query.lower()
        now = datetime.now(timezone.utc)

        # "November 2025" pattern (month + year)
        month_year_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{4})'
        match = re.search(month_year_pattern, query_lower)
        if match:
            month_name, year = match.groups()
            month = self.MONTHS.get(month_name)
            if month:
                year = int(year)
                result.date_from = datetime(year, month, 1, tzinfo=timezone.utc)
                # Last day of month
                if month == 12:
                    result.date_to = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                else:
                    result.date_to = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                result.time_type = "specific"
                result.confidence += 0.3
                return

        # "last November", "last month" patterns
        last_month_pattern = r'last\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)'
        match = re.search(last_month_pattern, query_lower)
        if match:
            month_name = match.group(1)
            month = self.MONTHS.get(month_name)
            if month:
                # Figure out the year
                year = now.year if month < now.month else now.year - 1
                result.date_from = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    result.date_to = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                else:
                    result.date_to = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                result.time_type = "past"
                result.confidence += 0.3
                return

        # Standalone month name pattern: "november's emails", "november emails", "in november"
        # Matches month name optionally followed by 's or preceded by "in"
        standalone_month_pattern = r"(?:in\s+)?(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)(?:'s)?"
        match = re.search(standalone_month_pattern, query_lower)
        if match:
            month_name = match.group(1)
            month = self.MONTHS.get(month_name)
            if month:
                # Determine year: if month <= current month, use current year
                # If month > current month, use previous year (most recent occurrence)
                if month <= now.month:
                    year = now.year
                else:
                    year = now.year - 1
                result.date_from = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    result.date_to = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                else:
                    result.date_to = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                result.time_type = "past"
                result.is_temporal = True
                result.confidence += 0.3
                return

        # Relative time patterns
        relative_patterns = {
            "today": (now.replace(hour=0, minute=0, second=0), now, "past"),
            "yesterday": (
                (now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
                now.replace(hour=0, minute=0, second=0),
                "past"
            ),
            "this week": (now - timedelta(days=now.weekday()), now, "past"),
            "last week": (
                now - timedelta(days=now.weekday() + 7),
                now - timedelta(days=now.weekday()),
                "past"
            ),
            "this month": (now.replace(day=1), now, "past"),
            "last month": (
                (now.replace(day=1) - timedelta(days=1)).replace(day=1),
                now.replace(day=1),
                "past"
            ),
            "next week": (now, now + timedelta(days=7), "future"),
            "next month": (now, now + timedelta(days=30), "future"),
            "coming up": (now, now + timedelta(days=14), "future"),
            "upcoming": (now, now + timedelta(days=14), "future"),
            "tomorrow": (
                (now + timedelta(days=1)).replace(hour=0, minute=0, second=0),
                (now + timedelta(days=2)).replace(hour=0, minute=0, second=0),
                "future"
            ),
        }

        for pattern, (date_from, date_to, time_type) in relative_patterns.items():
            if pattern in query_lower:
                result.date_from = date_from
                result.date_to = date_to
                result.time_type = time_type
                result.confidence += 0.3
                return

    def _detect_temporal_type(self, query: str, result: QueryAnalysis) -> None:
        """Detect if query is asking for recent/latest items."""
        query_lower = query.lower()

        # Check for past temporal keywords
        if any(kw in query_lower for kw in self.PAST_TEMPORAL):
            result.is_temporal = True
            if not result.time_type:
                result.time_type = "past"

        # Check for future temporal keywords
        if any(kw in query_lower for kw in self.FUTURE_TEMPORAL):
            result.is_temporal = True
            if not result.time_type:
                result.time_type = "future"
                # Set default future range if not already set
                if not result.date_from:
                    now = datetime.now(timezone.utc)
                    result.date_from = now
                    result.date_to = now + timedelta(days=30)

    async def _analyze_with_llm(self, query: str, result: QueryAnalysis) -> None:
        """Use LLM for complex query analysis."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a query analyzer. Extract structured information from user queries.
Today's date is {today}.

Return a JSON object with these fields:
- entities: list of person names, emails, or project names mentioned
- sources: list of data sources (one or more of: gmail, outlook, jira, calendar, gdrive, onedrive)
- date_from: ISO date string if a start date is implied (or null)
- date_to: ISO date string if an end date is implied (or null)
- time_type: "past", "future", or "specific" (or null if no time reference)
- intent: "search", "create", "update", or "delete"

Examples:
- "tasks assigned to Mike" → {{"entities": ["Mike"], "sources": ["jira"], "intent": "search"}}
- "emails from John last week" → {{"entities": ["John"], "sources": ["gmail", "outlook"], "time_type": "past", "intent": "search"}}
- "meetings coming up" → {{"sources": ["calendar"], "time_type": "future", "date_from": "{today}", "intent": "search"}}
- "November 2025 events" → {{"sources": ["calendar"], "date_from": "2025-11-01", "date_to": "2025-11-30", "time_type": "specific", "intent": "search"}}

Only output valid JSON, nothing else."""
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                temperature=0,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()
            # Clean up potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            data = json.loads(content)

            # Merge LLM results with fast extraction results
            if data.get("entities"):
                result.entities = list(set(result.entities + data["entities"]))

            if data.get("sources"):
                result.sources = list(set(result.sources + data["sources"]))

            if data.get("date_from") and not result.date_from:
                result.date_from = datetime.fromisoformat(data["date_from"].replace("Z", "+00:00"))
                if result.date_from.tzinfo is None:
                    result.date_from = result.date_from.replace(tzinfo=timezone.utc)

            if data.get("date_to") and not result.date_to:
                result.date_to = datetime.fromisoformat(data["date_to"].replace("Z", "+00:00"))
                if result.date_to.tzinfo is None:
                    result.date_to = result.date_to.replace(tzinfo=timezone.utc)

            if data.get("time_type"):
                result.time_type = data["time_type"]

            if data.get("intent"):
                result.intent = data["intent"]

            result.confidence = min(1.0, result.confidence + 0.4)

        except Exception as e:
            # LLM analysis failed, continue with fast extraction results
            print(f"LLM query analysis failed: {e}")


# Singleton instance
_analyzer: Optional[QueryAnalyzer] = None


def get_query_analyzer() -> QueryAnalyzer:
    """Get singleton query analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = QueryAnalyzer()
    return _analyzer
