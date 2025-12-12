"""
Seed script to populate database with test data for all use cases.

Run with: python -m scripts.seed_data
"""

import asyncio
import uuid
from datetime import datetime, timedelta
import numpy as np

from sqlalchemy import text

# Add parent directory to path
import sys
sys.path.insert(0, '.')

from app.database import engine, async_session_factory, Base
from app.models import (
    User, UserPreference, KnowledgeItem, Embedding,
    Entity, EntityMention, ChatSession, ChatMessage, IntegrationSync
)
from app.config import get_settings

settings = get_settings()

# Test user
TEST_USER_ID = "test_user_001"
TEST_USER_EMAIL = "testuser@company.com"
TEST_USER_NAME = "Test User"


def generate_mock_embedding(text: str, dim: int = 1536) -> list[float]:
    """Generate a deterministic mock embedding based on text hash."""
    # Use hash of text to seed random for reproducibility
    seed = hash(text) % (2**32)
    np.random.seed(seed)
    # Generate normalized random vector
    vec = np.random.randn(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


async def create_tables():
    """Create all database tables."""
    # Enable extensions in separate transaction
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))

    # Create tables in separate transaction
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created")


async def seed_user(session) -> User:
    """Create test user."""
    user = User(
        external_user_id=TEST_USER_ID,
        email=TEST_USER_EMAIL,
        name=TEST_USER_NAME,
        preferences={
            "timezone": "America/New_York",
            "notification_enabled": True,
        }
    )
    session.add(user)
    await session.flush()
    print(f"✓ Created user: {user.email}")
    return user


async def seed_user_preferences(session, user: User):
    """Create user preferences."""
    preferences = [
        # Email preferences
        UserPreference(
            user_id=user.id,
            preference_type="email",
            preference_key="tone",
            preference_value="professional",
            confidence=0.9,
            sample_count=15,
        ),
        UserPreference(
            user_id=user.id,
            preference_type="email",
            preference_key="length",
            preference_value="medium",
            confidence=0.85,
            sample_count=12,
        ),
        UserPreference(
            user_id=user.id,
            preference_type="email",
            preference_key="signature",
            preference_value="Best regards",
            confidence=0.95,
            sample_count=20,
        ),
        # Working hours
        UserPreference(
            user_id=user.id,
            preference_type="schedule",
            preference_key="working_hours",
            preference_value={"start": "09:00", "end": "18:00", "timezone": "America/New_York"},
            confidence=0.9,
            sample_count=30,
        ),
        # Frequent contacts
        UserPreference(
            user_id=user.id,
            preference_type="contacts",
            preference_key="frequent",
            preference_value=[
                {"email": "sarah@client.com", "count": 25},
                {"email": "john@company.com", "count": 42},
                {"email": "mike@company.com", "count": 38},
                {"email": "david@partner.com", "count": 15},
                {"email": "lisa@company.com", "count": 28},
            ],
            confidence=0.95,
            sample_count=100,
        ),
    ]

    for pref in preferences:
        session.add(pref)

    print(f"✓ Created {len(preferences)} user preferences")


async def seed_entities(session, user: User) -> dict:
    """Create entities (people, projects, topics)."""
    entities = {}

    # People
    people = [
        {"name": "Sarah Chen", "email": "sarah@client.com", "role": "Client - Product Manager", "company": "Acme Corp"},
        {"name": "John Smith", "email": "john@company.com", "role": "Senior Developer", "company": "Our Company"},
        {"name": "Mike Johnson", "email": "mike@company.com", "role": "DevOps Engineer", "company": "Our Company"},
        {"name": "David Wilson", "email": "david@partner.com", "role": "Partner - Stakeholder", "company": "Partner Inc"},
        {"name": "Lisa Anderson", "email": "lisa@company.com", "role": "Tech Lead", "company": "Our Company"},
        {"name": "Alex Thompson", "email": "alex@company.com", "role": "New Developer", "company": "Our Company"},
        {"name": "Emily Davis", "email": "emily@company.com", "role": "Designer", "company": "Our Company"},
    ]

    for person in people:
        entity = Entity(
            user_id=user.id,
            entity_type="person",
            name=person["name"],
            normalized_name=person["name"].lower(),
            metadata={
                "emails": [person["email"]],
                "job_title": person["role"],
                "company": person["company"],
            },
            mention_count=np.random.randint(5, 50),
        )
        session.add(entity)
        await session.flush()
        entities[person["name"].split()[0].lower()] = entity

    # Projects
    projects = [
        {"name": "MOBILE", "description": "Mobile App Project", "status": "active"},
        {"name": "Q1-LAUNCH", "description": "Q1 Product Launch", "status": "active"},
        {"name": "PHOENIX", "description": "Phoenix Infrastructure", "status": "active"},
        {"name": "ALPHA", "description": "Alpha Project", "status": "active"},
        {"name": "PLATFORM", "description": "Platform Team", "status": "active"},
    ]

    for proj in projects:
        entity = Entity(
            user_id=user.id,
            entity_type="project",
            name=proj["name"],
            normalized_name=proj["name"].lower(),
            metadata={
                "key": proj["name"],
                "description": proj["description"],
                "status": proj["status"],
                "source": "jira",
            },
            mention_count=np.random.randint(10, 100),
        )
        session.add(entity)
        await session.flush()
        entities[proj["name"].lower()] = entity

    # Topics
    topics = ["authentication", "payment integration", "dark mode", "api", "deployment", "roadmap"]
    for topic in topics:
        entity = Entity(
            user_id=user.id,
            entity_type="topic",
            name=topic.title(),
            normalized_name=topic.lower(),
            metadata={"keywords": topic.split()},
            mention_count=np.random.randint(3, 30),
        )
        session.add(entity)
        await session.flush()
        entities[topic.replace(" ", "_")] = entity

    print(f"✓ Created {len(entities)} entities")
    return entities


async def seed_gmail_items(session, user: User, entities: dict) -> list[KnowledgeItem]:
    """Create Gmail email items."""
    now = datetime.utcnow()
    items = []

    emails = [
        # Use Case 1: Sarah's proposal email
        {
            "source_id": "email_001",
            "title": "Mobile App Project Proposal",
            "summary": "Sarah sent proposal for mobile app development. Attached PDF with detailed requirements. Project deadline is Q2 with budget of $150k. Requesting review and task creation.",
            "content": """Hi Team,

I'm excited to share our proposal for the Mobile App Project. Please find attached the detailed requirements document.

Key highlights:
- iOS and Android native development
- User authentication with OAuth and social login
- Product catalog with advanced search
- Shopping cart and checkout flow
- Payment integration (Stripe, Apple Pay)
- Push notifications
- Offline mode support

Timeline: 16 weeks total
Budget: $150,000

Please review and let me know if you have any questions. Would love to schedule a kickoff meeting once you've had a chance to review.

Best regards,
Sarah Chen
Product Manager, Acme Corp""",
            "metadata": {
                "from": "sarah@client.com",
                "to": [TEST_USER_EMAIL],
                "cc": ["john@company.com"],
                "thread_id": "thread_mobile_001",
                "labels": ["client", "proposal", "important"],
                "has_attachment": True,
                "attachments": [{"name": "Mobile_App_Proposal_v2.pdf", "type": "application/pdf"}],
            },
            "date": now - timedelta(days=3),
        },
        # Follow-up email
        {
            "source_id": "email_002",
            "title": "Re: Mobile App Project Proposal",
            "summary": "Follow-up discussion about timeline and resources. Sarah confirms deadline flexibility and asks about team allocation.",
            "content": """Hi,

Thanks for the quick review! To answer your questions:

1. Yes, we have some flexibility on the Q2 deadline - up to 2 weeks buffer
2. We'd prefer weekly status updates
3. John and Mike were recommended by your team lead

Looking forward to the kickoff!

Sarah""",
            "metadata": {
                "from": "sarah@client.com",
                "to": [TEST_USER_EMAIL],
                "thread_id": "thread_mobile_001",
                "labels": ["client"],
            },
            "date": now - timedelta(days=2),
        },
        # Use Case 2: David's Q1 status request
        {
            "source_id": "email_003",
            "title": "Q1 Project Status Update Request",
            "summary": "David from partner company requesting Q1 project status update. Needs completion percentage, blockers, and expected completion date for stakeholder meeting.",
            "content": """Hi,

Could you provide an update on the Q1 project? Specifically:
1. Current completion percentage
2. Any blockers or risks
3. Expected completion date

Our stakeholders are asking and we have a board meeting next week.

Thanks,
David Wilson
Partner Inc""",
            "metadata": {
                "from": "david@partner.com",
                "to": [TEST_USER_EMAIL],
                "thread_id": "thread_q1_status",
                "labels": ["partner", "status-request", "urgent"],
            },
            "date": now - timedelta(hours=6),
        },
        # Use Case 3: Lisa's team sync email
        {
            "source_id": "email_004",
            "title": "Team Sync - Roadmap Discussion",
            "summary": "Lisa proposing team sync meeting to discuss roadmap. Available Tuesday 2-4pm, Wednesday 10am-12pm, Thursday after 3pm. Attendees: Lisa, John, Sarah, Mike.",
            "content": """Hi team,

Let's schedule a sync to discuss the roadmap for next quarter.

I'm available:
- Tuesday 2-4pm
- Wednesday 10am-12pm
- Thursday after 3pm

Can someone send out the invite?

Attendees should be: Me, John, Sarah, Mike

Thanks,
Lisa""",
            "metadata": {
                "from": "lisa@company.com",
                "to": [TEST_USER_EMAIL, "john@company.com", "mike@company.com"],
                "thread_id": "thread_sync_001",
                "labels": ["internal", "meeting"],
            },
            "date": now - timedelta(days=2),
        },
        # Use Case 9: Dark mode request
        {
            "source_id": "email_005",
            "title": "Feature Request - Dark Mode",
            "summary": "Client requesting dark mode support for mobile app. High priority, deadline end of Q1. Users have been requesting this feature frequently.",
            "content": """Hi,

Our users have been requesting dark mode support. Can you add this to the mobile app?

Priority: High
Deadline: End of Q1 if possible

This has been one of our top requested features in user surveys.

Let me know the estimate.

Thanks,
Sarah""",
            "metadata": {
                "from": "sarah@client.com",
                "to": [TEST_USER_EMAIL],
                "thread_id": "thread_darkmode",
                "labels": ["client", "feature-request"],
            },
            "date": now - timedelta(days=1),
        },
        # Phoenix project update
        {
            "source_id": "email_006",
            "title": "Phoenix Deployment Schedule",
            "summary": "Update on Phoenix project deployment schedule. Moving to AWS instead of GCP. Go-live date confirmed for February 28. UAT kickoff scheduled for Thursday.",
            "content": """Team,

Quick update on Phoenix:

1. We've decided to deploy on AWS instead of GCP (cost analysis attached)
2. Go-live date is confirmed: February 28
3. UAT kickoff is this Thursday

Key decision: Sarah approved the AWS migration after reviewing the cost analysis.

Action items:
- Security checklist review needed
- Final performance testing
- Documentation update

Mike will handle the infrastructure setup.

Lisa""",
            "metadata": {
                "from": "lisa@company.com",
                "to": [TEST_USER_EMAIL, "mike@company.com", "john@company.com"],
                "thread_id": "thread_phoenix_deploy",
                "labels": ["internal", "phoenix", "deployment"],
            },
            "date": now - timedelta(hours=18),
        },
        # Vendor quote request
        {
            "source_id": "email_007",
            "title": "Quote Request - API Integration Services",
            "summary": "Vendor requesting quote for API integration services. Need response with requirements by Friday. Previous vendor communications available for context.",
            "content": """Hello,

We're interested in your API integration services for our platform.

Could you provide:
1. Pricing for standard integration package
2. Timeline estimate
3. Support options

We need this by Friday for our budget meeting.

Best,
External Vendor""",
            "metadata": {
                "from": "vendor@external.com",
                "to": [TEST_USER_EMAIL],
                "thread_id": "thread_vendor",
                "labels": ["vendor", "quote"],
            },
            "date": now - timedelta(days=1),
        },
        # Weekly standup reminder
        {
            "source_id": "email_008",
            "title": "Meeting Notes - Product Review",
            "summary": "Product review meeting notes. Discussed Q1 priorities, approved new design mockups, decided on feature prioritization. Action items assigned to team members.",
            "content": """Team,

Here are the notes from today's product review:

Attendees: Lisa, John, Mike, Emily, Test User

Discussion:
1. Q1 feature prioritization - approved final list
2. Design mockups for v2.0 - approved with minor changes
3. API performance concerns - Mike to investigate

Decisions:
- Dark mode will be prioritized for Q1
- New onboarding flow approved
- Push notification system to use Firebase

Action Items:
- John: Complete auth module by Friday
- Mike: Performance report by Monday
- Emily: Final mockups by Wednesday

Next meeting: Thursday 2pm

Lisa""",
            "metadata": {
                "from": "lisa@company.com",
                "to": ["team@company.com"],
                "thread_id": "thread_product_review",
                "labels": ["internal", "meeting-notes"],
            },
            "date": now - timedelta(days=5),
        },
        # November 2025 emails for temporal query testing
        {
            "source_id": "email_009",
            "title": "November Project Kickoff",
            "summary": "Kickoff meeting for new project starting in November. Discussing scope, timeline, and team assignments.",
            "content": """Hi Team,

I'm excited to announce the kickoff of our new initiative!

Key details:
- Project starts November 1st
- Initial planning phase: 2 weeks
- Team: John, Mike, Lisa, and Emily

Looking forward to working with everyone!

Best,
Sarah""",
            "metadata": {
                "from": "sarah@client.com",
                "to": [TEST_USER_EMAIL, "john@company.com"],
                "thread_id": "thread_nov_kickoff",
                "labels": ["client", "project"],
            },
            "date": datetime(2025, 11, 5, 10, 30, 0),
        },
        {
            "source_id": "email_010",
            "title": "November Status Report",
            "summary": "Monthly status report for November. Progress on all active projects and upcoming milestones.",
            "content": """Team,

Here's our November status report:

MOBILE Project:
- UI development: 75% complete
- Backend APIs: 90% complete
- Testing: Started

PHOENIX Project:
- Infrastructure setup: Complete
- Security review: In progress

Key milestones this month:
- User auth module shipped
- Performance improvements deployed

Let me know if you have questions.

David""",
            "metadata": {
                "from": "david@partner.com",
                "to": [TEST_USER_EMAIL],
                "thread_id": "thread_nov_status",
                "labels": ["partner", "status-report"],
            },
            "date": datetime(2025, 11, 15, 14, 0, 0),
        },
        {
            "source_id": "email_011",
            "title": "Re: November Budget Review",
            "summary": "Budget review discussion for November expenses. Need approval for additional resources.",
            "content": """Hi,

Following up on the budget discussion from last week.

November expenses:
- Cloud infrastructure: $12,500
- Software licenses: $3,200
- Contractor fees: $8,000

Total: $23,700 (within budget)

Please approve the Q4 projections when you get a chance.

Thanks,
Lisa""",
            "metadata": {
                "from": "lisa@company.com",
                "to": [TEST_USER_EMAIL],
                "thread_id": "thread_nov_budget",
                "labels": ["internal", "budget"],
            },
            "date": datetime(2025, 11, 22, 9, 15, 0),
        },
    ]

    for email_data in emails:
        item = KnowledgeItem(
            user_id=user.id,
            source_type="gmail",
            source_id=email_data["source_id"],
            content_type="email",
            title=email_data["title"],
            summary=email_data["summary"],
            content=email_data["content"],
            metadata=email_data["metadata"],
            source_created_at=email_data["date"],
        )
        session.add(item)
        await session.flush()

        # Create embedding
        embed_text = f"{email_data['title']} {email_data['summary']}"
        embedding = Embedding(
            knowledge_item_id=item.id,
            user_id=user.id,
            embedding=generate_mock_embedding(embed_text),
            chunk_index=0,
            chunk_text=embed_text[:500],
        )
        session.add(embedding)
        items.append(item)

    print(f"✓ Created {len(items)} Gmail items")
    return items


async def seed_gdrive_items(session, user: User, entities: dict) -> list[KnowledgeItem]:
    """Create Google Drive document items."""
    now = datetime.utcnow()
    items = []

    documents = [
        # Use Case 1: Mobile App Proposal PDF
        {
            "source_id": "doc_001",
            "title": "Mobile_App_Proposal_v2.pdf",
            "content": """# Mobile App Project Proposal

## Project Overview
Mobile application for iOS and Android platforms for Acme Corp's e-commerce platform.

## Requirements

### 1. User Authentication
- OAuth 2.0 integration (Google, Apple, Facebook)
- Social login support
- Biometric authentication (Face ID, Touch ID)
- Session management and security

### 2. Product Catalog
- Browse products by category
- Advanced search with filters
- Product details with images and reviews
- Wishlist functionality

### 3. Shopping Cart
- Add/remove items
- Update quantities
- Save cart for later
- Apply promo codes

### 4. Payment Integration
- Stripe payment gateway
- Apple Pay support
- Google Pay support
- Secure card storage

### 5. Push Notifications
- Order status updates
- Promotional notifications
- Personalized recommendations
- Firebase Cloud Messaging

### 6. Offline Mode
- Browse cached products
- Save items offline
- Sync when online
- Offline cart management

## Timeline
- Phase 1: Core features (8 weeks)
  - Authentication, Catalog, Cart
- Phase 2: Payment & notifications (4 weeks)
  - Stripe, Apple Pay, FCM
- Phase 3: Polish & launch (4 weeks)
  - Testing, optimization, deployment

## Budget
Total: $150,000
- Development: $120,000
- Design: $15,000
- Infrastructure: $10,000
- Contingency: $5,000

## Team Requirements
- 2 Mobile Developers (iOS/Android)
- 1 Backend Developer
- 1 UI/UX Designer
- 1 QA Engineer
- 1 Project Manager

## Success Metrics
- App Store rating: 4.5+
- Crash-free rate: 99.5%
- Load time: <2 seconds
- User retention: 40% at 30 days""",
            "metadata": {
                "mime_type": "application/pdf",
                "folder_path": "/Client Projects/Acme",
                "total_chunks": 3,
                "size_bytes": 245000,
                "owner": "sarah@client.com",
            },
            "date": now - timedelta(days=5),
        },
        # Architecture document
        {
            "source_id": "doc_002",
            "title": "Phoenix_Architecture_v3.pdf",
            "content": """# Phoenix Project - Architecture Document

## System Overview
Phoenix is a microservices-based infrastructure platform designed for high availability and scalability.

## Architecture Components

### API Gateway
- Kong-based (migrating to custom solution)
- Rate limiting and throttling
- Authentication middleware
- Request routing

### Services
1. User Service
   - Authentication
   - Profile management
   - Preferences

2. Product Service
   - Catalog management
   - Search indexing
   - Inventory tracking

3. Order Service
   - Order processing
   - Payment handling
   - Fulfillment

4. Notification Service
   - Push notifications
   - Email notifications
   - SMS alerts

### Data Layer
- PostgreSQL for relational data
- Redis for caching
- Elasticsearch for search
- S3 for file storage

### Infrastructure
- AWS EKS for container orchestration
- AWS RDS for databases
- CloudFront CDN
- Route 53 DNS

## Caching Strategy
- Redis cluster for session data
- Application-level caching
- CDN for static assets
- Database query caching

## Security
- OAuth 2.0 / JWT tokens
- API key management
- Rate limiting
- DDoS protection

## Monitoring
- OpenTelemetry for tracing
- Prometheus for metrics
- Grafana dashboards
- PagerDuty alerts""",
            "metadata": {
                "mime_type": "application/pdf",
                "folder_path": "/Projects/Phoenix/Documentation",
                "total_chunks": 2,
                "size_bytes": 180000,
                "owner": "lisa@company.com",
            },
            "date": now - timedelta(days=3),
        },
        # Mobile App Roadmap
        {
            "source_id": "doc_003",
            "title": "Mobile_App_Roadmap_2024.docx",
            "content": """# Mobile App Roadmap 2024

## Q1 Features
| Feature | Priority | Status | Jira | Notes |
|---------|----------|--------|------|-------|
| User Authentication | High | In Progress | MOBILE-42 | OAuth integration |
| Product Catalog | High | Planned | MOBILE-43 | Search & filters |
| Shopping Cart | High | Planned | MOBILE-44 | Core functionality |
| Offline Mode | Medium | Planned | MOBILE-45 | Phase 1 |

## Q2 Features
| Feature | Priority | Status | Jira | Notes |
|---------|----------|--------|------|-------|
| Payment Gateway | High | Planned | MOBILE-46 | Stripe + Apple Pay |
| Push Notifications | Medium | Planned | MOBILE-47 | Firebase FCM |
| Analytics | Medium | Planned | - | Mixpanel integration |

## Q3 Features
- Performance optimization
- A/B testing framework
- Advanced personalization

## Q4 Features
- International expansion
- Multi-language support
- Regional payment methods

## Team Allocation
- John: Authentication, Cart
- Mike: Infrastructure, DevOps
- Emily: UI/UX Design

## Milestones
- Feb 15: Beta release
- Feb 20: Client demo
- Mar 31: Q1 launch""",
            "metadata": {
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "folder_path": "/Projects/Mobile/Planning",
                "total_chunks": 1,
                "size_bytes": 45000,
                "owner": TEST_USER_EMAIL,
            },
            "date": now - timedelta(days=10),
        },
        # Alpha Project Status Report
        {
            "source_id": "doc_004",
            "title": "Alpha_Project_Status_Report_Jan2024.docx",
            "content": """# Alpha Project Status Report
Generated: January 2024

## Executive Summary
Project is 67% complete with 2 blockers requiring immediate attention.

## Progress Overview
| Status | Count | Percentage |
|--------|-------|------------|
| Done | 10 | 67% |
| In Progress | 3 | 20% |
| Blocked | 2 | 13% |

## Key Accomplishments
- User authentication module completed
- API integration approved by stakeholders
- Architecture review passed
- Database migration completed

## Current Blockers
1. ALPHA-23: Waiting on vendor API documentation
   - Owner: Mike
   - ETA: End of week

2. ALPHA-27: Design approval pending from client
   - Owner: Emily
   - Escalated to Sarah

## Team Contributions
| Member | Completed | In Progress |
|--------|-----------|-------------|
| John | 4 | 1 |
| Sarah | 3 | 1 |
| Mike | 3 | 1 |

## Upcoming Milestones
- Beta release: February 15
- Client demo: February 20
- Production launch: March 1

## Risks & Mitigations
1. Vendor delay - Contingency plan with alternative vendor
2. Resource constraint - Requested additional developer""",
            "metadata": {
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "folder_path": "/Projects/Alpha/Reports",
                "total_chunks": 1,
                "size_bytes": 35000,
                "owner": TEST_USER_EMAIL,
            },
            "date": now - timedelta(days=2),
        },
        # Platform Team Onboarding Doc
        {
            "source_id": "doc_005",
            "title": "Platform_Team_Onboarding.docx",
            "content": """# Platform Team Onboarding Guide

## Team Overview
The Platform team builds and maintains core infrastructure services.

## Key People
- **Lisa Anderson** (Tech Lead) - Architecture decisions, code reviews
- **John Smith** (Senior Dev) - API development, mentorship
- **Mike Johnson** (DevOps) - CI/CD, deployments, infrastructure

## Current Projects

### 1. API Gateway Migration (Priority: High)
- Moving from Kong to custom solution
- ETA: Q1 completion
- Starter task: PLAT-89 (auth middleware)

### 2. Monitoring Overhaul (Priority: Medium)
- Implementing distributed tracing
- OpenTelemetry adoption
- Grafana dashboards

## Key Documents
- Architecture Overview (link)
- API Design Guidelines (link)
- Deployment Runbook (link)
- Security Checklist (link)

## Recurring Meetings
- Daily Standup: 9:30 AM
- Sprint Planning: Monday 2 PM
- Tech Review: Thursday 3 PM
- Demo: Friday 4 PM

## Tech Stack
- Go for new services
- Python for existing services
- PostgreSQL, Redis, Elasticsearch
- AWS EKS, Terraform

## First Week Checklist
[ ] Set up dev environment
[ ] Get access to AWS, GitHub, Jira
[ ] 1:1 with Lisa (scheduled)
[ ] Review architecture docs
[ ] Pick up PLAT-89 starter task

## Important Decisions (Recent)
- Switched to Go for new services (Jan 5)
- Adopting OpenTelemetry (Jan 10)
- AWS over GCP for Phoenix (Jan 12)""",
            "metadata": {
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "folder_path": "/Teams/Platform/Onboarding",
                "total_chunks": 1,
                "size_bytes": 28000,
                "owner": "lisa@company.com",
            },
            "date": now - timedelta(days=15),
        },
    ]

    for doc_data in documents:
        item = KnowledgeItem(
            user_id=user.id,
            source_type="gdrive",
            source_id=doc_data["source_id"],
            content_type="document",
            title=doc_data["title"],
            content=doc_data["content"],
            metadata=doc_data["metadata"],
            source_created_at=doc_data["date"],
            source_updated_at=doc_data["date"],
        )
        session.add(item)
        await session.flush()

        # Create embeddings for chunks
        chunks = chunk_document(doc_data["content"])
        for i, chunk in enumerate(chunks):
            embedding = Embedding(
                knowledge_item_id=item.id,
                user_id=user.id,
                embedding=generate_mock_embedding(chunk),
                chunk_index=i,
                chunk_text=chunk[:500],
            )
            session.add(embedding)

        items.append(item)

    print(f"✓ Created {len(items)} GDrive items")
    return items


def chunk_document(content: str, chunk_size: int = 500) -> list[str]:
    """Simple chunking by paragraphs."""
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para.split())
        if current_size + para_size > chunk_size and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size

    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks if chunks else [content]


async def seed_jira_items(session, user: User, entities: dict) -> list[KnowledgeItem]:
    """Create Jira task items."""
    now = datetime.utcnow()
    items = []

    tasks = [
        # MOBILE project tasks
        {
            "source_id": "MOBILE-42",
            "title": "Implement User Authentication",
            "content": """Implement user authentication with OAuth and social login support.

## Acceptance Criteria
- Users can sign up with email/password
- OAuth integration with Google, Apple, Facebook
- Biometric authentication support
- Secure session management
- Password reset flow

## Technical Details
- Use OAuth 2.0 PKCE flow
- JWT tokens with refresh mechanism
- Secure storage for credentials

## Dependencies
- Design mockups (MOBILE-40)
- API endpoints (MOBILE-41)""",
            "metadata": {
                "project_key": "MOBILE",
                "type": "story",
                "status": "In Progress",
                "priority": "high",
                "assignee": "john@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["authentication", "phase-1", "security"],
                "components": ["mobile-app", "auth"],
                "story_points": 8,
            },
            "date": now - timedelta(days=7),
        },
        {
            "source_id": "MOBILE-43",
            "title": "Build Product Catalog",
            "content": """Build product catalog with search and filters.

## Acceptance Criteria
- Browse products by category
- Search with autocomplete
- Filter by price, rating, brand
- Product detail pages
- Image gallery

## Technical Details
- Elasticsearch for search
- Redis caching for performance
- Lazy loading for images""",
            "metadata": {
                "project_key": "MOBILE",
                "type": "story",
                "status": "To Do",
                "priority": "high",
                "assignee": "john@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["catalog", "phase-1", "search"],
                "story_points": 13,
            },
            "date": now - timedelta(days=5),
        },
        {
            "source_id": "MOBILE-44",
            "title": "Implement Shopping Cart",
            "content": """Implement shopping cart functionality.

## Acceptance Criteria
- Add/remove items from cart
- Update quantities
- Calculate totals with tax
- Apply promo codes
- Save cart across sessions

## Technical Details
- Optimistic UI updates
- Real-time inventory check
- Cart persistence in Redis""",
            "metadata": {
                "project_key": "MOBILE",
                "type": "story",
                "status": "To Do",
                "priority": "high",
                "assignee": "john@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["cart", "phase-1"],
                "story_points": 8,
            },
            "date": now - timedelta(days=5),
        },
        {
            "source_id": "MOBILE-45",
            "title": "Implement Offline Mode",
            "content": """Add offline support for the mobile app.

## Acceptance Criteria
- Browse cached products offline
- Queue actions for sync
- Sync when connectivity restored
- Show offline indicator

## Technical Details
- SQLite for local storage
- Background sync service
- Conflict resolution strategy""",
            "metadata": {
                "project_key": "MOBILE",
                "type": "story",
                "status": "To Do",
                "priority": "medium",
                "assignee": None,
                "reporter": TEST_USER_EMAIL,
                "labels": ["offline", "phase-1"],
                "story_points": 8,
            },
            "date": now - timedelta(days=5),
        },
        {
            "source_id": "MOBILE-46",
            "title": "Integrate Payment Gateway",
            "content": """Integrate Stripe and Apple Pay for payments.

## Acceptance Criteria
- Stripe payment flow
- Apple Pay integration
- Secure card storage
- Payment confirmation
- Receipt generation

## Technical Details
- Stripe SDK integration
- PCI compliance requirements
- Apple Pay merchant setup""",
            "metadata": {
                "project_key": "MOBILE",
                "type": "story",
                "status": "To Do",
                "priority": "high",
                "assignee": "mike@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["payments", "phase-2", "stripe"],
                "story_points": 10,
            },
            "date": now - timedelta(days=3),
        },
        {
            "source_id": "MOBILE-47",
            "title": "Setup Push Notifications",
            "content": """Implement push notifications using Firebase.

## Acceptance Criteria
- FCM integration
- Order status notifications
- Promotional notifications
- User preferences for notifications
- Deep linking support

## Technical Details
- Firebase Cloud Messaging
- Topic-based subscriptions
- Notification channels (Android)""",
            "metadata": {
                "project_key": "MOBILE",
                "type": "story",
                "status": "To Do",
                "priority": "medium",
                "assignee": "mike@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["notifications", "phase-2", "firebase"],
                "story_points": 5,
            },
            "date": now - timedelta(days=3),
        },
        # Q1-LAUNCH project tasks
        {
            "source_id": "Q1-15",
            "title": "Payment API Integration",
            "content": """Integrate with vendor payment API.

Blocked waiting on vendor documentation.

## Status
BLOCKED - Vendor has not provided updated API docs.

## Notes
- Reached out to vendor contact on Jan 10
- Expected docs by end of week
- Contingency: Use mock API for testing""",
            "metadata": {
                "project_key": "Q1-LAUNCH",
                "type": "task",
                "status": "Blocked",
                "priority": "high",
                "assignee": "mike@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["payment", "blocked", "vendor"],
                "blocker_reason": "Waiting on vendor API documentation",
            },
            "date": now - timedelta(days=10),
        },
        {
            "source_id": "Q1-18",
            "title": "Third-party Auth Integration",
            "content": """Integrate third-party authentication provider.

Blocked waiting on credentials.

## Status
BLOCKED - Credentials pending from partner team.

## Notes
- Escalated to David
- Expected by Friday""",
            "metadata": {
                "project_key": "Q1-LAUNCH",
                "type": "task",
                "status": "Blocked",
                "priority": "medium",
                "assignee": "john@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["auth", "blocked", "partner"],
                "blocker_reason": "Waiting on credentials from partner",
            },
            "date": now - timedelta(days=8),
        },
        # PHOENIX tasks
        {
            "source_id": "PHOENIX-45",
            "title": "Third-party Service Rate Limiting",
            "content": """Implement rate limiting for third-party API calls.

## Issue
External service hitting rate limits during peak traffic.

## Solution
- Implement client-side rate limiting
- Add request queuing
- Caching layer for repeated requests

## Status
BLOCKED - Need architecture review""",
            "metadata": {
                "project_key": "PHOENIX",
                "type": "bug",
                "status": "Blocked",
                "priority": "high",
                "assignee": "mike@company.com",
                "reporter": "lisa@company.com",
                "labels": ["performance", "rate-limiting", "blocked"],
            },
            "date": now - timedelta(days=4),
        },
        # ALPHA tasks
        {
            "source_id": "ALPHA-23",
            "title": "Vendor API Documentation Integration",
            "content": """Waiting on vendor API documentation to complete integration.

## Status
BLOCKED

## Notes
- Vendor contact: vendor@external.com
- Last contact: Jan 10
- Expected delivery: Jan 17""",
            "metadata": {
                "project_key": "ALPHA",
                "type": "task",
                "status": "Blocked",
                "priority": "high",
                "assignee": "mike@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["vendor", "blocked", "integration"],
            },
            "date": now - timedelta(days=12),
        },
        {
            "source_id": "ALPHA-27",
            "title": "Design Approval - Client Review",
            "content": """Design approval pending from client.

## Status
BLOCKED - Waiting on Sarah's approval

## Designs Submitted
- Homepage redesign
- Product page updates
- Checkout flow

## Notes
- Sent to Sarah on Jan 8
- Follow-up sent Jan 12""",
            "metadata": {
                "project_key": "ALPHA",
                "type": "task",
                "status": "Blocked",
                "priority": "medium",
                "assignee": "emily@company.com",
                "reporter": TEST_USER_EMAIL,
                "labels": ["design", "blocked", "client"],
            },
            "date": now - timedelta(days=10),
        },
        # PLATFORM tasks
        {
            "source_id": "PLAT-89",
            "title": "Auth Middleware Implementation",
            "content": """Implement authentication middleware for new API gateway.

## Requirements
- JWT validation
- Role-based access control
- Rate limiting per user
- Audit logging

## Technical Approach
- Go middleware package
- Redis for session cache
- Integration with existing auth service

## Good First Issue
This is marked as a starter task for new team members.""",
            "metadata": {
                "project_key": "PLATFORM",
                "type": "task",
                "status": "To Do",
                "priority": "medium",
                "assignee": None,
                "reporter": "lisa@company.com",
                "labels": ["auth", "middleware", "good-first-issue"],
            },
            "date": now - timedelta(days=5),
        },
        # Completed tasks for weekly report
        {
            "source_id": "PROJ-42",
            "title": "User Authentication Module",
            "content": "Completed user authentication implementation with OAuth support.",
            "metadata": {
                "project_key": "PROJ",
                "type": "story",
                "status": "Done",
                "priority": "high",
                "assignee": TEST_USER_EMAIL,
                "reporter": "lisa@company.com",
                "labels": ["auth", "completed"],
                "completed_at": (now - timedelta(days=2)).isoformat(),
            },
            "date": now - timedelta(days=10),
        },
        {
            "source_id": "PROJ-45",
            "title": "Payment Processing Bug Fix",
            "content": "Fixed critical bug in payment processing that caused double charges.",
            "metadata": {
                "project_key": "PROJ",
                "type": "bug",
                "status": "Done",
                "priority": "critical",
                "assignee": TEST_USER_EMAIL,
                "reporter": "john@company.com",
                "labels": ["bug", "payment", "completed"],
                "completed_at": (now - timedelta(days=3)).isoformat(),
            },
            "date": now - timedelta(days=8),
        },
        {
            "source_id": "PROJ-48",
            "title": "API Documentation Update",
            "content": "Updated API documentation for v2.0 endpoints.",
            "metadata": {
                "project_key": "PROJ",
                "type": "task",
                "status": "Done",
                "priority": "medium",
                "assignee": TEST_USER_EMAIL,
                "reporter": TEST_USER_EMAIL,
                "labels": ["documentation", "completed"],
                "completed_at": (now - timedelta(days=1)).isoformat(),
            },
            "date": now - timedelta(days=5),
        },
        {
            "source_id": "PROJ-55",
            "title": "Payment Gateway Integration",
            "content": "Integrate new payment gateway for international transactions. 70% complete.",
            "metadata": {
                "project_key": "PROJ",
                "type": "story",
                "status": "In Progress",
                "priority": "high",
                "assignee": TEST_USER_EMAIL,
                "reporter": "lisa@company.com",
                "labels": ["payment", "in-progress"],
                "progress": 70,
            },
            "date": now - timedelta(days=6),
        },
    ]

    for task_data in tasks:
        item = KnowledgeItem(
            user_id=user.id,
            source_type="jira",
            source_id=task_data["source_id"],
            content_type="task",
            title=task_data["title"],
            content=task_data["content"],
            metadata=task_data["metadata"],
            source_created_at=task_data["date"],
            source_updated_at=now - timedelta(hours=np.random.randint(1, 48)),
        )
        session.add(item)
        await session.flush()

        # Create embedding
        embed_text = f"{task_data['source_id']} {task_data['title']} {task_data['content'][:500]}"
        embedding = Embedding(
            knowledge_item_id=item.id,
            user_id=user.id,
            embedding=generate_mock_embedding(embed_text),
            chunk_index=0,
            chunk_text=embed_text[:500],
        )
        session.add(embedding)
        items.append(item)

    print(f"✓ Created {len(items)} Jira items")
    return items


async def seed_calendar_items(session, user: User, entities: dict) -> list[KnowledgeItem]:
    """Create calendar event items."""
    now = datetime.utcnow()
    items = []

    events = [
        # Upcoming meetings
        {
            "source_id": "evt_001",
            "title": "Q1 Project Review Meeting",
            "content": "Weekly project review meeting to discuss Q1 progress, blockers, and next steps.",
            "metadata": {
                "start": (now + timedelta(days=1, hours=14)).isoformat(),
                "end": (now + timedelta(days=1, hours=15)).isoformat(),
                "location": "Conference Room A",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "david@partner.com", "name": "David Wilson"},
                    {"email": "sarah@client.com", "name": "Sarah Chen"},
                    {"email": "mike@company.com", "name": "Mike Johnson"},
                ],
                "meet_link": "https://meet.google.com/abc-def-ghi",
                "recurrence": "weekly",
            },
            "date": now + timedelta(days=1, hours=14),
        },
        {
            "source_id": "evt_002",
            "title": "Phoenix UAT Kickoff",
            "content": "User Acceptance Testing kickoff for Phoenix project. Review test cases and assign testers.",
            "metadata": {
                "start": (now + timedelta(days=2, hours=10)).isoformat(),
                "end": (now + timedelta(days=2, hours=11, minutes=30)).isoformat(),
                "location": "Virtual",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "lisa@company.com", "name": "Lisa Anderson"},
                    {"email": "mike@company.com", "name": "Mike Johnson"},
                    {"email": "john@company.com", "name": "John Smith"},
                ],
                "meet_link": "https://meet.google.com/xyz-123-abc",
            },
            "date": now + timedelta(days=2, hours=10),
        },
        {
            "source_id": "evt_003",
            "title": "Team Lunch",
            "content": "Monthly team lunch - casual catch up.",
            "metadata": {
                "start": (now + timedelta(days=3, hours=12)).isoformat(),
                "end": (now + timedelta(days=3, hours=13)).isoformat(),
                "location": "Downtown Cafe",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "john@company.com", "name": "John Smith"},
                    {"email": "lisa@company.com", "name": "Lisa Anderson"},
                    {"email": "emily@company.com", "name": "Emily Davis"},
                ],
            },
            "date": now + timedelta(days=3, hours=12),
        },
        {
            "source_id": "evt_004",
            "title": "AWS Training Workshop",
            "content": "AWS certification training workshop - EKS and container orchestration.",
            "metadata": {
                "start": (now + timedelta(days=4, hours=9)).isoformat(),
                "end": (now + timedelta(days=4, hours=17)).isoformat(),
                "location": "Training Room B",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "mike@company.com", "name": "Mike Johnson"},
                ],
            },
            "date": now + timedelta(days=4, hours=9),
        },
        # Past meetings
        {
            "source_id": "evt_005",
            "title": "Phoenix Go-Live Planning",
            "content": """Meeting notes:
- Discussed deployment timeline
- Decided on AWS over GCP
- Go-live date: February 28
- Action items assigned

Attendees: Lisa, Mike, John, Test User

Decisions:
- AWS deployment confirmed
- UAT starts Thursday
- Security review needed""",
            "metadata": {
                "start": (now - timedelta(days=5, hours=14)).isoformat(),
                "end": (now - timedelta(days=5, hours=15)).isoformat(),
                "location": "Conference Room B",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "lisa@company.com", "name": "Lisa Anderson"},
                    {"email": "mike@company.com", "name": "Mike Johnson"},
                    {"email": "john@company.com", "name": "John Smith"},
                ],
            },
            "date": now - timedelta(days=5, hours=14),
        },
        {
            "source_id": "evt_006",
            "title": "Sprint Planning",
            "content": "Sprint 5 planning session. Committed to 25 story points.",
            "metadata": {
                "start": (now - timedelta(days=3, hours=14)).isoformat(),
                "end": (now - timedelta(days=3, hours=16)).isoformat(),
                "location": "Virtual",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "lisa@company.com", "name": "Lisa Anderson"},
                    {"email": "john@company.com", "name": "John Smith"},
                    {"email": "emily@company.com", "name": "Emily Davis"},
                ],
                "meet_link": "https://meet.google.com/spr-int-pln",
            },
            "date": now - timedelta(days=3, hours=14),
        },
        {
            "source_id": "evt_007",
            "title": "Design Team Meeting",
            "content": "Tomorrow at 10am - slides needed for design review presentation.",
            "metadata": {
                "start": (now + timedelta(days=1, hours=10)).isoformat(),
                "end": (now + timedelta(days=1, hours=11)).isoformat(),
                "location": "Design Studio",
                "attendees": [
                    {"email": TEST_USER_EMAIL, "name": "Test User"},
                    {"email": "emily@company.com", "name": "Emily Davis"},
                ],
            },
            "date": now + timedelta(days=1, hours=10),
        },
    ]

    for event_data in events:
        item = KnowledgeItem(
            user_id=user.id,
            source_type="calendar",
            source_id=event_data["source_id"],
            content_type="event",
            title=event_data["title"],
            content=event_data["content"],
            metadata=event_data["metadata"],
            source_created_at=event_data["date"],
        )
        session.add(item)
        await session.flush()

        # Create embedding
        embed_text = f"{event_data['title']} {event_data['content']}"
        embedding = Embedding(
            knowledge_item_id=item.id,
            user_id=user.id,
            embedding=generate_mock_embedding(embed_text),
            chunk_index=0,
            chunk_text=embed_text[:500],
        )
        session.add(embedding)
        items.append(item)

    print(f"✓ Created {len(items)} Calendar items")
    return items


async def seed_entity_mentions(session, user: User, entities: dict, items: list[KnowledgeItem]):
    """Create entity mentions linking entities to knowledge items."""
    mention_count = 0

    # Map of keywords to entity keys
    entity_keywords = {
        "sarah": "sarah",
        "sarah chen": "sarah",
        "john": "john",
        "john smith": "john",
        "mike": "mike",
        "mike johnson": "mike",
        "david": "david",
        "david wilson": "david",
        "lisa": "lisa",
        "lisa anderson": "lisa",
        "alex": "alex",
        "emily": "emily",
        "mobile": "mobile",
        "mobile app": "mobile",
        "q1-launch": "q1-launch",
        "q1 launch": "q1-launch",
        "phoenix": "phoenix",
        "alpha": "alpha",
        "platform": "platform",
        "authentication": "authentication",
        "payment": "payment_integration",
        "dark mode": "dark_mode",
    }

    for item in items:
        content_to_search = f"{item.title or ''} {item.content or ''} {item.summary or ''}".lower()

        mentioned_entities = set()
        for keyword, entity_key in entity_keywords.items():
            if keyword in content_to_search and entity_key in entities:
                mentioned_entities.add(entity_key)

        for entity_key in mentioned_entities:
            entity = entities[entity_key]
            mention = EntityMention(
                entity_id=entity.id,
                knowledge_item_id=item.id,
                mention_context=f"Mentioned in: {item.title}",
            )
            session.add(mention)
            mention_count += 1

    print(f"✓ Created {mention_count} entity mentions")


async def seed_chat_history(session, user: User):
    """Create sample chat sessions and messages."""
    now = datetime.utcnow()

    # Session 1: Previous conversation about proposal
    session1 = ChatSession(
        user_id=user.id,
        session_type="task",
        title="Mobile App Proposal Discussion",
        context_summary="Discussed Sarah's proposal, planned to send updated proposal by Friday",
    )
    session.add(session1)
    await session.flush()

    messages1 = [
        {
            "role": "user",
            "content": "I need to review Sarah's mobile app proposal and create some tasks from it",
            "context_items": [{"id": "doc_001", "relevance": 0.95}],
            "created_at": now - timedelta(days=3, hours=2),
        },
        {
            "role": "assistant",
            "content": """I found Sarah's proposal for the Mobile App Project. Here's a summary:

**Project:** Mobile App for Acme Corp
**Budget:** $150,000
**Timeline:** 16 weeks

**Key Features:**
1. User Authentication (OAuth, Social Login)
2. Product Catalog with search
3. Shopping Cart
4. Payment Integration (Stripe, Apple Pay)
5. Push Notifications
6. Offline Mode

Would you like me to create Jira tasks for these requirements?""",
            "context_items": [{"id": "doc_001", "relevance": 0.95}, {"id": "email_001", "relevance": 0.92}],
            "created_at": now - timedelta(days=3, hours=2) + timedelta(seconds=30),
        },
        {
            "role": "user",
            "content": "Yes, create tasks and assign Phase 1 to John and Phase 2 to Mike",
            "created_at": now - timedelta(days=3, hours=2) + timedelta(minutes=2),
        },
        {
            "role": "assistant",
            "content": """I'll create the tasks and send the updated proposal to Sarah by Friday.

Created tasks in MOBILE project:
- MOBILE-42: User Authentication (John)
- MOBILE-43: Product Catalog (John)
- MOBILE-44: Shopping Cart (John)
- MOBILE-45: Offline Mode (John)
- MOBILE-46: Payment Gateway (Mike)
- MOBILE-47: Push Notifications (Mike)

I'll remind you to send the updated proposal to sarah@client.com by Friday.""",
            "created_at": now - timedelta(days=3, hours=2) + timedelta(minutes=3),
            "pending_actions": [
                {"id": "act_001", "type": "send_email", "description": "Send proposal to Sarah", "status": "pending"}
            ],
        },
    ]

    for msg in messages1:
        chat_msg = ChatMessage(
            session_id=session1.id,
            user_id=user.id,
            role=msg["role"],
            content=msg["content"],
            context_items=msg.get("context_items", []),
            pending_actions=msg.get("pending_actions", []),
            created_at=msg["created_at"],
        )
        session.add(chat_msg)

    # Session 2: Jira task discussion
    session2 = ChatSession(
        user_id=user.id,
        session_type="task",
        title="PROJ-55 Assignment Discussion",
        context_summary="Created PROJ-55, user mentioned checking with Mike before assigning",
    )
    session.add(session2)
    await session.flush()

    messages2 = [
        {
            "role": "user",
            "content": "Create a task for API Documentation in the PROJ project",
            "created_at": now - timedelta(days=5, hours=4),
        },
        {
            "role": "assistant",
            "content": """Created task PROJ-55: API Documentation

**Summary:** API Documentation
**Project:** PROJ
**Status:** To Do
**Priority:** Medium

Would you like to assign this to someone?""",
            "created_at": now - timedelta(days=5, hours=4) + timedelta(seconds=20),
        },
        {
            "role": "user",
            "content": "I'll assign it after checking with Mike",
            "created_at": now - timedelta(days=5, hours=4) + timedelta(minutes=1),
        },
        {
            "role": "assistant",
            "content": "Got it! PROJ-55 is currently unassigned. Let me know when you'd like to assign it after speaking with Mike.",
            "created_at": now - timedelta(days=5, hours=4) + timedelta(minutes=1, seconds=15),
        },
    ]

    for msg in messages2:
        chat_msg = ChatMessage(
            session_id=session2.id,
            user_id=user.id,
            role=msg["role"],
            content=msg["content"],
            context_items=msg.get("context_items", []),
            created_at=msg["created_at"],
        )
        session.add(chat_msg)

    # Session 3: Meeting scheduling
    session3 = ChatSession(
        user_id=user.id,
        session_type="calendar",
        title="Design Team Meeting",
        context_summary="Scheduled meeting with design team, user needs to prepare slides",
    )
    session.add(session3)
    await session.flush()

    messages3 = [
        {
            "role": "user",
            "content": "Schedule a meeting with the design team for tomorrow",
            "created_at": now - timedelta(days=6, hours=3),
        },
        {
            "role": "assistant",
            "content": """I've scheduled the Design Team Meeting:

**When:** Tomorrow at 10:00 AM (1 hour)
**Where:** Design Studio
**Attendees:** You, Emily Davis

Calendar invite sent to all attendees.

You mentioned wanting to prepare slides beforehand - would you like me to remind you?""",
            "created_at": now - timedelta(days=6, hours=3) + timedelta(seconds=25),
        },
    ]

    for msg in messages3:
        chat_msg = ChatMessage(
            session_id=session3.id,
            user_id=user.id,
            role=msg["role"],
            content=msg["content"],
            context_items=msg.get("context_items", []),
            created_at=msg["created_at"],
        )
        session.add(chat_msg)

    print("✓ Created 3 chat sessions with history")


async def seed_integration_syncs(session, user: User):
    """Create integration sync status records."""
    now = datetime.utcnow()

    syncs = [
        IntegrationSync(
            user_id=user.id,
            source_type="gmail",
            last_sync_at=now - timedelta(hours=1),
            items_synced=8,
            status="completed",
        ),
        IntegrationSync(
            user_id=user.id,
            source_type="gdrive",
            last_sync_at=now - timedelta(hours=2),
            items_synced=5,
            status="completed",
        ),
        IntegrationSync(
            user_id=user.id,
            source_type="jira",
            last_sync_at=now - timedelta(hours=1),
            items_synced=15,
            status="completed",
        ),
        IntegrationSync(
            user_id=user.id,
            source_type="calendar",
            last_sync_at=now - timedelta(minutes=30),
            items_synced=7,
            status="completed",
        ),
    ]

    for sync in syncs:
        session.add(sync)

    print(f"✓ Created {len(syncs)} integration sync records")


async def main():
    """Main seed function."""
    print("\n" + "="*60)
    print("🌱 Seeding AI Assistant Database with Test Data")
    print("="*60 + "\n")

    # Create tables
    await create_tables()

    async with async_session_factory() as session:
        try:
            # Create user
            user = await seed_user(session)

            # Create preferences
            await seed_user_preferences(session, user)

            # Create entities
            entities = await seed_entities(session, user)

            # Create knowledge items from various sources
            all_items = []

            gmail_items = await seed_gmail_items(session, user, entities)
            all_items.extend(gmail_items)

            gdrive_items = await seed_gdrive_items(session, user, entities)
            all_items.extend(gdrive_items)

            jira_items = await seed_jira_items(session, user, entities)
            all_items.extend(jira_items)

            calendar_items = await seed_calendar_items(session, user, entities)
            all_items.extend(calendar_items)

            # Create entity mentions
            await seed_entity_mentions(session, user, entities, all_items)

            # Create chat history
            await seed_chat_history(session, user)

            # Create sync status
            await seed_integration_syncs(session, user)

            # Commit all changes
            await session.commit()

            print("\n" + "="*60)
            print("✅ Database seeded successfully!")
            print("="*60)
            print(f"""
📊 Summary:
   - User: {TEST_USER_EMAIL}
   - User ID (external): {TEST_USER_ID}
   - Emails: {len(gmail_items)}
   - Documents: {len(gdrive_items)}
   - Jira Tasks: {len(jira_items)}
   - Calendar Events: {len(calendar_items)}
   - Entities: {len(entities)}
   - Chat Sessions: 3

🔗 Test Endpoints:
   - Chat: POST http://localhost:8000/api/v1/chat
   - Sync Status: GET http://localhost:8000/api/v1/sync/status/{TEST_USER_ID}
   - Entities: GET http://localhost:8000/api/v1/entities/{TEST_USER_ID}
   - Preferences: GET http://localhost:8000/api/v1/preferences/{TEST_USER_ID}
   - Sessions: GET http://localhost:8000/api/v1/chat/sessions/{TEST_USER_ID}

📝 Sample Chat Request:
   curl -X POST http://localhost:8000/api/v1/chat \\
     -H "Content-Type: application/json" \\
     -d '{{"user_id": "{TEST_USER_ID}", "message": "What tasks does Sarah need me to work on?"}}'
""")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error seeding database: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
