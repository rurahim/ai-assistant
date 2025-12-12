# AI Assistant - Complete Data Reference Guide

This document explains **where every piece of data is stored**, **which memory type it belongs to**, **how to access it**, and **which code handles it**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MEMORY HIERARCHY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │ WORKING MEMORY  │    │ SEMANTIC MEMORY │    │ EPISODIC MEMORY │          │
│  │    (Redis)      │    │   (PostgreSQL   │    │  (PostgreSQL)   │          │
│  │                 │    │   + pgvector)   │    │                 │          │
│  │ - Session state │    │ - Embeddings    │    │ - Chat history  │          │
│  │ - Cache         │    │ - Knowledge     │    │ - Sessions      │          │
│  │ - Temp context  │    │ - Entities      │    │ - Messages      │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │PROCEDURAL MEMORY│    │ TEMPORAL MEMORY │                                 │
│  │  (PostgreSQL)   │    │  (PostgreSQL)   │                                 │
│  │                 │    │                 │                                 │
│  │ - Preferences   │    │ - Timestamps    │                                 │
│  │ - Learned       │    │ - Time-based    │                                 │
│  │   behaviors     │    │   queries       │                                 │
│  └─────────────────┘    └─────────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# SECTION 1: USER DATA

## Table: `users`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| external_user_id | VARCHAR(255) | Your lookup ID (e.g., "test_user_001") |
| email | VARCHAR(255) | User email |
| name | VARCHAR(255) | Display name |
| preferences | JSONB | User settings |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |

### Current Data:
```
┌──────────────────────────────────────┬─────────────────┬───────────────────────┬───────────┐
│ id                                   │ external_user_id│ email                 │ name      │
├──────────────────────────────────────┼─────────────────┼───────────────────────┼───────────┤
│ 66ab97a4-8161-4a19-8bdc-b02ebf94ea7f │ test_user_001   │ testuser@company.com  │ Test User │
└──────────────────────────────────────┴─────────────────┴───────────────────────┴───────────┘

preferences: {"timezone": "America/New_York", "notification_enabled": true}
```

### Memory Type: **Core Identity**

### Where to Access:
- **Database:** `SELECT * FROM users WHERE external_user_id = 'test_user_001';`
- **API Endpoint:** Used internally by all endpoints via `get_user()` helper
- **Python Model:** `app/models/user.py` → `class User`
- **Python Service:** `app/api/chat.py:get_user()` function

### Code Reference:
```python
# app/models/user.py:17-45
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    external_user_id: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
```

---

# SECTION 2: PROCEDURAL MEMORY (Learned Preferences)

## Table: `user_preferences`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| preference_type | VARCHAR(50) | Category (email, schedule, contacts) |
| preference_key | VARCHAR(100) | Specific preference |
| preference_value | JSONB | The learned value |
| confidence | FLOAT | How confident (0-1) |
| sample_count | INTEGER | How many times observed |

### Current Data:
```
┌─────────────────┬─────────────────┬─────────────────────────────────────────────────────┬────────────┐
│ preference_type │ preference_key  │ preference_value                                    │ confidence │
├─────────────────┼─────────────────┼─────────────────────────────────────────────────────┼────────────┤
│ email           │ tone            │ "professional"                                      │ 0.90       │
│ email           │ length          │ "medium"                                            │ 0.85       │
│ email           │ signature       │ "Best regards"                                      │ 0.95       │
│ schedule        │ working_hours   │ {"start": "09:00", "end": "18:00", "timezone": ...} │ 0.90       │
│ contacts        │ frequent        │ [{"email": "sarah@client.com", "count": 25}, ...]   │ 0.95       │
└─────────────────┴─────────────────┴─────────────────────────────────────────────────────┴────────────┘
```

### Memory Type: **PROCEDURAL MEMORY**
> Stores learned behaviors and patterns from user interactions

### Where to Access:
- **Database:**
  ```sql
  SELECT * FROM user_preferences WHERE user_id = '66ab97a4-8161-4a19-8bdc-b02ebf94ea7f';
  ```
- **API Endpoint:** `GET http://localhost:8000/api/v1/preferences/test_user_001`
- **Python Model:** `app/models/user.py` → `class UserPreference`
- **Python Service:** `app/services/preference_service.py` → `class PreferenceService`
- **API Router:** `app/api/preferences.py`

### Code Reference:
```python
# app/services/preference_service.py:28-65
class PreferenceService:
    async def get_user_preferences(self, db, user_id) -> dict:
        """Get all preferences for a user."""

    async def learn_preference(self, db, user_id, pref_type, key, value):
        """Learn/update a preference from user behavior."""

    async def get_email_style(self, db, user_id) -> dict:
        """Get learned email writing style."""
```

### How It's Used:
When drafting emails, the agent checks:
```python
# app/agents/email_agent.py uses this to match user's style
preferences = await preference_service.get_email_style(db, user_id)
# Returns: {"tone": "professional", "length": "medium", "signature": "Best regards"}
```

---

# SECTION 3: SEMANTIC MEMORY (Knowledge + Embeddings)

## Table: `knowledge_items`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| source_type | VARCHAR(50) | gmail, gdrive, jira, calendar |
| source_id | VARCHAR(255) | Original ID from source |
| content_type | VARCHAR(50) | email, document, task, event |
| title | VARCHAR(500) | Title/subject |
| summary | TEXT | AI-generated summary |
| content | TEXT | Full content |
| metadata | JSONB | Source-specific metadata |
| source_created_at | TIMESTAMP | When originally created |
| synced_at | TIMESTAMP | When we synced it |

### Memory Type: **SEMANTIC MEMORY**
> Long-term storage of facts, concepts, and knowledge

### Where to Access:
- **Database:**
  ```sql
  SELECT source_type, title, summary, LEFT(content, 200)
  FROM knowledge_items
  WHERE user_id = '66ab97a4-8161-4a19-8bdc-b02ebf94ea7f'
  ORDER BY source_type, source_created_at DESC;
  ```
- **Python Model:** `app/models/knowledge.py` → `class KnowledgeItem`
- **Python Service:** `app/services/context_service.py` → retrieval
- **Sync Service:** `app/services/sync_service.py` → ingestion

---

## GMAIL EMAILS (8 total)

### Database Query:
```sql
SELECT title, summary, content, source_created_at
FROM knowledge_items
WHERE source_type = 'gmail'
ORDER BY source_created_at DESC;
```

### Email 1: Mobile App Project Proposal
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ source_type: gmail                                                          │
│ content_type: email                                                         │
│ title: Mobile App Project Proposal                                          │
│ source_created_at: 2025-11-30                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY (AI-generated):                                                     │
│ Sarah sent proposal for mobile app development. Attached PDF with detailed  │
│ requirements. Project deadline is Q2 with budget of $150k. Requesting       │
│ review and task creation.                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ FULL CONTENT:                                                               │
│ Hi Team,                                                                    │
│                                                                             │
│ I'm excited to share our proposal for the Mobile App Project. Please find   │
│ attached the detailed requirements document.                                │
│                                                                             │
│ Key highlights:                                                             │
│ - iOS and Android native development                                        │
│ - User authentication with OAuth and social login                           │
│ - Product catalog with advanced search                                      │
│ - Shopping cart and checkout flow                                           │
│ - Payment integration (Stripe, Apple Pay)                                   │
│ - Push notifications                                                        │
│ - Offline mode support                                                      │
│                                                                             │
│ Timeline: 16 weeks total                                                    │
│ Budget: $150,000                                                            │
│                                                                             │
│ Please review and let me know if you have any questions. Would love to      │
│ schedule a kickoff meeting once you've had a chance to review.              │
│                                                                             │
│ Best regards,                                                               │
│ Sarah Chen                                                                  │
│ Product Manager, Acme Corp                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 2: Re: Mobile App Project Proposal
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Re: Mobile App Project Proposal                                      │
│ source_created_at: 2025-12-01                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: Follow-up discussion about timeline and resources. Sarah confirms  │
│ deadline flexibility and asks about team allocation.                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ Hi,                                                                         │
│                                                                             │
│ Thanks for the quick review! To answer your questions:                      │
│                                                                             │
│ 1. Yes, we have some flexibility on the Q2 deadline - up to 2 weeks buffer  │
│ 2. We'd prefer weekly status updates                                        │
│ 3. John and Mike were recommended by your team lead                         │
│                                                                             │
│ Looking forward to the kickoff!                                             │
│                                                                             │
│ Sarah                                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 3: Q1 Project Status Update Request
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Q1 Project Status Update Request                                     │
│ source_created_at: 2025-12-03                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: David from partner company requesting Q1 project status update.    │
│ Needs completion percentage, blockers, and expected completion date for     │
│ stakeholder meeting.                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ Hi,                                                                         │
│                                                                             │
│ Could you provide an update on the Q1 project? Specifically:                │
│ 1. Current completion percentage                                            │
│ 2. Any blockers or risks                                                    │
│ 3. Expected completion date                                                 │
│                                                                             │
│ Our stakeholders are asking and we have a board meeting next week.          │
│                                                                             │
│ Thanks,                                                                     │
│ David Wilson                                                                │
│ Partner Inc                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 4: Team Sync - Roadmap Discussion
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Team Sync - Roadmap Discussion                                       │
│ source_created_at: 2025-12-01                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: Lisa proposing team sync meeting to discuss roadmap. Available     │
│ Tuesday 2-4pm, Wednesday 10am-12pm, Thursday after 3pm.                     │
│ Attendees: Lisa, John, Sarah, Mike.                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ Hi team,                                                                    │
│                                                                             │
│ Let's schedule a sync to discuss the roadmap for next quarter.              │
│                                                                             │
│ I'm available:                                                              │
│ - Tuesday 2-4pm                                                             │
│ - Wednesday 10am-12pm                                                       │
│ - Thursday after 3pm                                                        │
│                                                                             │
│ Can someone send out the invite?                                            │
│                                                                             │
│ Attendees should be: Me, John, Sarah, Mike                                  │
│                                                                             │
│ Thanks,                                                                     │
│ Lisa                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 5: Feature Request - Dark Mode
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Feature Request - Dark Mode                                          │
│ source_created_at: 2025-12-02                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: Client requesting dark mode support for mobile app. High priority, │
│ deadline end of Q1. Users have been requesting this feature frequently.     │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ Hi,                                                                         │
│                                                                             │
│ Our users have been requesting dark mode support. Can you add this to the   │
│ mobile app?                                                                 │
│                                                                             │
│ Priority: High                                                              │
│ Deadline: End of Q1 if possible                                             │
│                                                                             │
│ This has been one of our top requested features in user surveys.            │
│                                                                             │
│ Let me know the estimate.                                                   │
│                                                                             │
│ Thanks,                                                                     │
│ Sarah                                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 6: Phoenix Deployment Schedule
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Phoenix Deployment Schedule                                          │
│ source_created_at: 2025-12-02                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: Update on Phoenix project deployment schedule. Moving to AWS       │
│ instead of GCP. Go-live date confirmed for February 28. UAT kickoff         │
│ scheduled for Thursday.                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ Team,                                                                       │
│                                                                             │
│ Quick update on Phoenix:                                                    │
│                                                                             │
│ 1. We've decided to deploy on AWS instead of GCP (cost analysis attached)   │
│ 2. Go-live date is confirmed: February 28                                   │
│ 3. UAT kickoff is this Thursday                                             │
│                                                                             │
│ Key decision: Sarah approved the AWS migration after reviewing cost analysis│
│                                                                             │
│ Action items:                                                               │
│ - Security checklist review needed                                          │
│ - Final performance testing                                                 │
│ - Documentation update                                                      │
│                                                                             │
│ Mike will handle the infrastructure setup.                                  │
│                                                                             │
│ Lisa                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 7: Quote Request - API Integration Services
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Quote Request - API Integration Services                             │
│ source_created_at: 2025-12-02                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: Vendor requesting quote for API integration services. Need         │
│ response with requirements by Friday.                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Email 8: Meeting Notes - Product Review
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Meeting Notes - Product Review                                       │
│ source_created_at: 2025-11-28                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY: Product review meeting notes. Discussed Q1 priorities, approved    │
│ new design mockups, decided on feature prioritization.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ Team,                                                                       │
│                                                                             │
│ Here are the notes from today's product review:                             │
│                                                                             │
│ Attendees: Lisa, John, Mike, Emily, Test User                               │
│                                                                             │
│ Discussion:                                                                 │
│ 1. Q1 feature prioritization - approved final list                          │
│ 2. Design mockups for v2.0 - approved with minor changes                    │
│ 3. API performance concerns - Mike to investigate                           │
│                                                                             │
│ Decisions:                                                                  │
│ - Dark mode will be prioritized for Q1                                      │
│ - New onboarding flow approved                                              │
│ - Push notification system to use Firebase                                  │
│                                                                             │
│ Action Items:                                                               │
│ - John: Complete auth module by Friday                                      │
│ - Mike: Performance report by Monday                                        │
│ - Emily: Final mockups by Wednesday                                         │
│                                                                             │
│ Next meeting: Thursday 2pm                                                  │
│                                                                             │
│ Lisa                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Code That Handles Emails:
```python
# app/services/sync_service.py:250-335 - Ingestion
async def sync_gmail(self, db, user_id, days=30):
    """Sync Gmail emails for a user."""
    # Fetches from external API, creates KnowledgeItem, generates embedding

# app/services/context_service.py - Retrieval
async def retrieve(self, db, user_id, query, sources=['gmail'], ...):
    """Retrieve relevant context using hybrid search."""

# app/agents/email_agent.py - Email-specific operations
class EmailAgent(BaseAgent):
    """Specialist agent for email-related tasks."""
```

---

## GOOGLE DRIVE DOCUMENTS (5 total)

### Database Query:
```sql
SELECT title, LEFT(content, 1000) as content_preview
FROM knowledge_items
WHERE source_type = 'gdrive';
```

### Document 1: Mobile_App_Proposal_v2.pdf
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ source_type: gdrive                                                         │
│ content_type: document                                                      │
│ title: Mobile_App_Proposal_v2.pdf                                           │
│ source_created_at: 2025-11-28                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ FULL CONTENT:                                                               │
│                                                                             │
│ # Mobile App Project Proposal                                               │
│                                                                             │
│ ## Project Overview                                                         │
│ Mobile application for iOS and Android platforms for Acme Corp's            │
│ e-commerce platform.                                                        │
│                                                                             │
│ ## Requirements                                                             │
│                                                                             │
│ ### 1. User Authentication                                                  │
│ - OAuth 2.0 integration (Google, Apple, Facebook)                           │
│ - Social login support                                                      │
│ - Biometric authentication (Face ID, Touch ID)                              │
│ - Session management and security                                           │
│                                                                             │
│ ### 2. Product Catalog                                                      │
│ - Browse products by category                                               │
│ - Advanced search with filters                                              │
│ - Product details with images and reviews                                   │
│ - Wishlist functionality                                                    │
│                                                                             │
│ ### 3. Shopping Cart                                                        │
│ - Add/remove items                                                          │
│ - Update quantities                                                         │
│ - Save cart for later                                                       │
│ - Apply promo codes                                                         │
│                                                                             │
│ ### 4. Payment Integration                                                  │
│ - Stripe payment gateway                                                    │
│ - Apple Pay support                                                         │
│ - Google Pay support                                                        │
│ - Secure card storage                                                       │
│                                                                             │
│ ### 5. Push Notifications                                                   │
│ - Order status updates                                                      │
│ - Promotional notifications                                                 │
│ - Personalized recommendations                                              │
│ - Firebase Cloud Messaging                                                  │
│                                                                             │
│ ### 6. Offline Mode                                                         │
│ - Browse cached products                                                    │
│ - Save items offline                                                        │
│ - Sync when online                                                          │
│ - Offline cart management                                                   │
│                                                                             │
│ ## Timeline                                                                 │
│ - Phase 1: Core features (8 weeks) - Authentication, Catalog, Cart          │
│ - Phase 2: Payment & notifications (4 weeks) - Stripe, Apple Pay, FCM       │
│ - Phase 3: Polish & launch (4 weeks) - Testing, optimization, deployment    │
│                                                                             │
│ ## Budget                                                                   │
│ Total: $150,000                                                             │
│ - Development: $120,000                                                     │
│ - Design: $15,000                                                           │
│ - Infrastructure: $10,000                                                   │
│ - Contingency: $5,000                                                       │
│                                                                             │
│ ## Team Requirements                                                        │
│ - 2 Mobile Developers (iOS/Android)                                         │
│ - 1 Backend Developer                                                       │
│ - 1 UI/UX Designer                                                          │
│ - 1 QA Engineer                                                             │
│ - 1 Project Manager                                                         │
│                                                                             │
│ ## Success Metrics                                                          │
│ - App Store rating: 4.5+                                                    │
│ - Crash-free rate: 99.5%                                                    │
│ - Load time: <2 seconds                                                     │
│ - User retention: 40% at 30 days                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Document 2: Phoenix_Architecture_v3.pdf
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Phoenix_Architecture_v3.pdf                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ # Phoenix Project - Architecture Document                                   │
│                                                                             │
│ ## System Overview                                                          │
│ Phoenix is a microservices-based infrastructure platform designed for       │
│ high availability and scalability.                                          │
│                                                                             │
│ ## Architecture Components                                                  │
│                                                                             │
│ ### API Gateway                                                             │
│ - Kong-based (migrating to custom solution)                                 │
│ - Rate limiting and throttling                                              │
│ - Authentication middleware                                                 │
│ - Request routing                                                           │
│                                                                             │
│ ### Services                                                                │
│ 1. User Service - Authentication, Profile, Preferences                      │
│ 2. Product Service - Catalog, Search, Inventory                             │
│ 3. Order Service - Processing, Payment, Fulfillment                         │
│ 4. Notification Service - Push, Email, SMS                                  │
│                                                                             │
│ ### Data Layer                                                              │
│ - PostgreSQL for relational data                                            │
│ - Redis for caching                                                         │
│ - Elasticsearch for search                                                  │
│ - S3 for file storage                                                       │
│                                                                             │
│ ### Infrastructure                                                          │
│ - AWS EKS for container orchestration                                       │
│ - AWS RDS for databases                                                     │
│ - CloudFront CDN                                                            │
│ - Route 53 DNS                                                              │
│                                                                             │
│ ### Security                                                                │
│ - OAuth 2.0 / JWT tokens                                                    │
│ - API key management                                                        │
│ - Rate limiting                                                             │
│ - DDoS protection                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Document 3: Mobile_App_Roadmap_2024.docx
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Mobile_App_Roadmap_2024.docx                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ # Mobile App Roadmap 2024                                                   │
│                                                                             │
│ ## Q1 Features                                                              │
│ | Feature             | Priority | Status      | Jira      |               │
│ |---------------------|----------|-------------|-----------|               │
│ | User Authentication | High     | In Progress | MOBILE-42 |               │
│ | Product Catalog     | High     | Planned     | MOBILE-43 |               │
│ | Shopping Cart       | High     | Planned     | MOBILE-44 |               │
│ | Offline Mode        | Medium   | Planned     | MOBILE-45 |               │
│                                                                             │
│ ## Q2 Features                                                              │
│ | Feature            | Priority | Jira      |                              │
│ |--------------------|----------|-----------|                              │
│ | Payment Gateway    | High     | MOBILE-46 |                              │
│ | Push Notifications | Medium   | MOBILE-47 |                              │
│ | Analytics          | Medium   | -         |                              │
│                                                                             │
│ ## Team Allocation                                                          │
│ - John: Authentication, Cart                                                │
│ - Mike: Infrastructure, DevOps                                              │
│ - Emily: UI/UX Design                                                       │
│                                                                             │
│ ## Milestones                                                               │
│ - Feb 15: Beta release                                                      │
│ - Feb 20: Client demo                                                       │
│ - Mar 31: Q1 launch                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Document 4: Alpha_Project_Status_Report_Jan2024.docx
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Alpha_Project_Status_Report_Jan2024.docx                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ # Alpha Project Status Report                                               │
│                                                                             │
│ ## Executive Summary                                                        │
│ Project is 67% complete with 2 blockers requiring immediate attention.      │
│                                                                             │
│ ## Progress Overview                                                        │
│ | Status      | Count | Percentage |                                       │
│ |-------------|-------|------------|                                       │
│ | Done        | 10    | 67%        |                                       │
│ | In Progress | 3     | 20%        |                                       │
│ | Blocked     | 2     | 13%        |                                       │
│                                                                             │
│ ## Current Blockers                                                         │
│ 1. ALPHA-23: Waiting on vendor API documentation (Owner: Mike)              │
│ 2. ALPHA-27: Design approval pending from client (Owner: Emily)             │
│                                                                             │
│ ## Team Contributions                                                       │
│ - John: 4 completed, 1 in progress                                          │
│ - Sarah: 3 completed, 1 in progress                                         │
│ - Mike: 3 completed, 1 in progress                                          │
│                                                                             │
│ ## Upcoming Milestones                                                      │
│ - Beta release: February 15                                                 │
│ - Client demo: February 20                                                  │
│ - Production launch: March 1                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Document 5: Platform_Team_Onboarding.docx
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ title: Platform_Team_Onboarding.docx                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONTENT:                                                                    │
│ # Platform Team Onboarding Guide                                            │
│                                                                             │
│ ## Key People                                                               │
│ - Lisa Anderson (Tech Lead) - Architecture decisions, code reviews          │
│ - John Smith (Senior Dev) - API development, mentorship                     │
│ - Mike Johnson (DevOps) - CI/CD, deployments, infrastructure                │
│                                                                             │
│ ## Current Projects                                                         │
│ 1. API Gateway Migration (Priority: High)                                   │
│    - Moving from Kong to custom solution                                    │
│    - Starter task: PLAT-89 (auth middleware)                                │
│                                                                             │
│ 2. Monitoring Overhaul (Priority: Medium)                                   │
│    - OpenTelemetry adoption                                                 │
│    - Grafana dashboards                                                     │
│                                                                             │
│ ## Tech Stack                                                               │
│ - Go for new services                                                       │
│ - Python for existing services                                              │
│ - PostgreSQL, Redis, Elasticsearch                                          │
│ - AWS EKS, Terraform                                                        │
│                                                                             │
│ ## First Week Checklist                                                     │
│ [ ] Set up dev environment                                                  │
│ [ ] Get access to AWS, GitHub, Jira                                         │
│ [ ] 1:1 with Lisa                                                           │
│ [ ] Review architecture docs                                                │
│ [ ] Pick up PLAT-89 starter task                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Code That Handles Documents:
```python
# app/services/sync_service.py:336-392 - Document ingestion with chunking
async def _process_document(self, db, user_id, doc):
    """Process and store a document with chunking."""
    content = doc.get("content_text", "")
    chunks = self.embedding_service.chunk_document(content)
    # Creates KnowledgeItem + multiple embeddings for chunks

# app/services/embedding_service.py:85-110 - Chunking logic
def chunk_document(self, content, chunk_size=600, overlap=100):
    """Split document into overlapping chunks for better retrieval."""

# app/agents/document_agent.py - Document-specific operations
class DocumentAgent(BaseAgent):
    """Specialist agent for document-related tasks."""
```

---

## JIRA TASKS (15 total)

### Database Query:
```sql
SELECT title, content, metadata->>'status' as status, metadata->>'project_key' as project
FROM knowledge_items
WHERE source_type = 'jira'
ORDER BY metadata->>'project_key', source_created_at DESC;
```

### MOBILE Project Tasks:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE-42: Implement User Authentication                                    │
│ Status: In Progress | Assignee: John                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Implement user authentication with OAuth and social login support.          │
│                                                                             │
│ ## Acceptance Criteria                                                      │
│ - Users can sign up with email/password                                     │
│ - OAuth integration with Google, Apple, Facebook                            │
│ - Biometric authentication support                                          │
│ - Secure session management                                                 │
│ - Password reset flow                                                       │
│                                                                             │
│ ## Technical Details                                                        │
│ - Use OAuth 2.0 PKCE flow                                                   │
│ - JWT tokens with refresh mechanism                                         │
│ - Secure storage for credentials                                            │
│                                                                             │
│ ## Dependencies                                                             │
│ - Design mockups (MOBILE-40)                                                │
│ - API endpoints (MOBILE-41)                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE-43: Build Product Catalog                                            │
│ Status: Planned | Assignee: John                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ ## Acceptance Criteria                                                      │
│ - Browse products by category                                               │
│ - Search with autocomplete                                                  │
│ - Filter by price, rating, brand                                            │
│ - Product detail pages                                                      │
│ - Image gallery                                                             │
│                                                                             │
│ ## Technical Details                                                        │
│ - Elasticsearch for search                                                  │
│ - Redis caching for performance                                             │
│ - Lazy loading for images                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE-44: Implement Shopping Cart                                          │
│ Status: Planned | Assignee: John                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ ## Acceptance Criteria                                                      │
│ - Add/remove items from cart                                                │
│ - Update quantities                                                         │
│ - Calculate totals with tax                                                 │
│ - Apply promo codes                                                         │
│ - Save cart across sessions                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE-45: Implement Offline Mode                                           │
│ Status: Planned | Assignee: John                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ - SQLite for local storage                                                  │
│ - Background sync service                                                   │
│ - Conflict resolution strategy                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE-46: Integrate Payment Gateway                                        │
│ Status: Planned | Assignee: Mike                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ - Stripe SDK integration                                                    │
│ - Apple Pay integration                                                     │
│ - PCI compliance requirements                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE-47: Setup Push Notifications                                         │
│ Status: Planned | Assignee: Mike                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ - Firebase Cloud Messaging                                                  │
│ - Topic-based subscriptions                                                 │
│ - Deep linking support                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### BLOCKED Tasks (Important!):
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Q1-LAUNCH: Third-party Auth Integration                                     │
│ Status: BLOCKED                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ BLOCKED - Credentials pending from partner team.                            │
│ Escalated to David. Expected by Friday.                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PHOENIX: Payment API Integration                                            │
│ Status: BLOCKED                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ BLOCKED - Vendor has not provided updated API docs.                         │
│ Reached out to vendor contact on Jan 10.                                    │
│ Contingency: Use mock API for testing.                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ALPHA: Design Approval - Client Review                                      │
│ Status: BLOCKED                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ BLOCKED - Waiting on Sarah's approval.                                      │
│ Designs submitted: Homepage, Product page, Checkout flow.                   │
│ Sent Jan 8, follow-up sent Jan 12.                                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PLATFORM: Third-party Service Rate Limiting                                 │
│ Status: BLOCKED                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ BLOCKED - Need architecture review.                                         │
│ External service hitting rate limits during peak traffic.                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Code That Handles Tasks:
```python
# app/services/sync_service.py:394-459 - Task ingestion
async def _process_jira_issue(self, db, user_id, issue):
    """Process and store a Jira issue."""

# app/agents/task_agent.py - Task-specific operations
class TaskAgent(BaseAgent):
    """Specialist agent for task management."""

    async def _search_tasks(self, state, project_key=None, status=None):
        """Search tasks with filters."""

    async def _create_task(self, state, summary, description, project, assignee):
        """Create a new task."""
```

---

## CALENDAR EVENTS (7 total)

### Database Query:
```sql
SELECT title, content, source_created_at, metadata
FROM knowledge_items
WHERE source_type = 'calendar'
ORDER BY source_created_at;
```

### Events:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phoenix Go-Live Planning | Nov 27                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ Meeting notes:                                                              │
│ - Discussed deployment timeline                                             │
│ - Decided on AWS over GCP                                                   │
│ - Go-live date: February 28                                                 │
│ - Action items assigned                                                     │
│                                                                             │
│ Attendees: Lisa, Mike, John, Test User                                      │
│                                                                             │
│ Decisions:                                                                  │
│ - AWS deployment confirmed                                                  │
│ - UAT starts Thursday                                                       │
│ - Security review needed                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Sprint Planning | Nov 29                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Sprint 5 planning session. Committed to 25 story points.                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Design Team Meeting | Dec 4 (Tomorrow)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Tomorrow at 10am - slides needed for design review presentation.            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Q1 Project Review Meeting | Dec 5                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ Weekly project review meeting to discuss Q1 progress, blockers, next steps. │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Phoenix UAT Kickoff | Dec 5                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ User Acceptance Testing kickoff for Phoenix project.                        │
│ Review test cases and assign testers.                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Team Lunch | Dec 6                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Monthly team lunch - casual catch up.                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ AWS Training Workshop | Dec 7                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ AWS certification training workshop - EKS and container orchestration.      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# SECTION 4: EMBEDDINGS (Vector Search)

## Table: `embeddings`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| knowledge_item_id | UUID | FK to knowledge_items |
| user_id | UUID | FK to users |
| embedding | VECTOR(1536) | The actual vector |
| embedding_model | VARCHAR(50) | Model used |
| chunk_index | INTEGER | For chunked docs |
| chunk_text | TEXT | The text that was embedded |

### Memory Type: **SEMANTIC MEMORY (Vector Index)**
> Enables similarity search for relevant context retrieval

### Current Stats:
```
Total embeddings: 36
Model: text-embedding-3-small
Dimensions: 1536
Index type: HNSW (via pgvector)
```

### Where to Access:
- **Database:**
  ```sql
  SELECT chunk_text, embedding_model, chunk_index
  FROM embeddings LIMIT 5;
  ```
- **Python Model:** `app/models/embedding.py` → `class Embedding`
- **Python Service:** `app/services/embedding_service.py` → `class EmbeddingService`
- **Context Service:** `app/services/context_service.py` → `_semantic_search()`

### How Semantic Search Works:
```python
# app/services/context_service.py:120-180
async def _semantic_search(self, db, user_id, query, sources, ...):
    """Perform semantic similarity search using pgvector."""

    # 1. Create embedding for query
    query_embedding = await self.embedding_service.create_embedding(query)

    # 2. Search using cosine similarity
    stmt = (
        select(
            Embedding,
            KnowledgeItem,
            (1 - Embedding.embedding.cosine_distance(query_embedding)).label("similarity")
        )
        .join(KnowledgeItem)
        .where(Embedding.user_id == str(user_id))
        .order_by(desc("similarity"))
        .limit(limit)
    )

    # Returns items ranked by semantic similarity
```

### Code Reference:
```python
# app/services/embedding_service.py:28-65
class EmbeddingService:
    async def create_embedding(self, text: str) -> list[float]:
        """Create embedding for text using OpenAI."""
        response = await self.openai.embeddings.create(
            input=text,
            model=settings.embedding_model  # text-embedding-3-small
        )
        return response.data[0].embedding  # 1536-dim vector

    def chunk_document(self, content, chunk_size=600, overlap=100):
        """Split document into overlapping chunks."""
        # Returns list of chunks for separate embeddings
```

---

# SECTION 5: ENTITIES (Extracted Knowledge)

## Table: `entities`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| entity_type | VARCHAR(50) | person, project, topic, company |
| name | VARCHAR(255) | Display name |
| normalized_name | VARCHAR(255) | Lowercase for matching |
| metadata | JSONB | Type-specific data |
| mention_count | INTEGER | How often mentioned |
| last_seen_at | TIMESTAMP | Last mention time |

### Memory Type: **SEMANTIC MEMORY (Structured)**
> Extracted entities for entity-based search and context linking

### Current Entities:

#### People (7):
```
┌─────────────────┬──────────┬─────────────────────────────────────────────────┐
│ Name            │ Mentions │ Context                                         │
├─────────────────┼──────────┼─────────────────────────────────────────────────┤
│ David Wilson    │ 40       │ Partner company, asks for status updates        │
│ Sarah Chen      │ 36       │ Product Manager at Acme Corp, sends proposals   │
│ Lisa Anderson   │ 32       │ Tech Lead, schedules meetings, makes decisions  │
│ Alex Thompson   │ 31       │ Team member                                     │
│ Emily Davis     │ 28       │ UI/UX Designer                                  │
│ Mike Johnson    │ 5        │ DevOps, infrastructure, Phase 2 owner           │
│ John Smith      │ 5        │ Senior Dev, Phase 1 owner                       │
└─────────────────┴──────────┴─────────────────────────────────────────────────┘
```

#### Projects (5):
```
┌─────────────┬──────────┬─────────────────────────────────────────────────────┐
│ Name        │ Mentions │ Description                                         │
├─────────────┼──────────┼─────────────────────────────────────────────────────┤
│ PLATFORM    │ 79       │ Core infrastructure services                        │
│ Q1-LAUNCH   │ 59       │ Q1 launch project                                   │
│ ALPHA       │ 55       │ Alpha project - 67% complete                        │
│ PHOENIX     │ 50       │ Microservices platform, AWS deployment              │
│ MOBILE      │ 38       │ Mobile app for Acme Corp                            │
└─────────────┴──────────┴─────────────────────────────────────────────────────┘
```

#### Topics (6):
```
┌─────────────────────┬──────────┐
│ Name                │ Mentions │
├─────────────────────┼──────────┤
│ Authentication      │ 29       │
│ Dark Mode           │ 18       │
│ Api                 │ 14       │
│ Roadmap             │ 8        │
│ Deployment          │ 7        │
│ Payment Integration │ 5        │
└─────────────────────┴──────────┘
```

### Where to Access:
- **Database:**
  ```sql
  SELECT name, entity_type, mention_count FROM entities ORDER BY mention_count DESC;
  ```
- **API Endpoint:** `GET http://localhost:8000/api/v1/entities/test_user_001`
- **Python Model:** `app/models/entity.py` → `class Entity`
- **Python Service:** `app/services/entity_service.py` → `class EntityService`
- **API Router:** `app/api/entities.py`

### Code Reference:
```python
# app/services/entity_service.py:35-90
class EntityService:
    async def extract_and_store(self, db, user_id, knowledge_item, raw_data):
        """Extract entities from content and store them."""
        # Extracts people from email from/to/cc
        # Extracts project keys from Jira
        # Uses GPT for complex extraction

    async def find_entity(self, db, user_id, name):
        """Find an entity by name (fuzzy match)."""

    async def get_entity_context(self, db, user_id, entity_id):
        """Get all items related to an entity."""
```

---

# SECTION 6: EPISODIC MEMORY (Chat History)

## Table: `chat_sessions`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| session_type | VARCHAR(50) | email, document, task, calendar, general |
| title | VARCHAR(255) | Session title |
| context_summary | TEXT | AI summary of session |
| metadata | JSONB | Session metadata |
| created_at | TIMESTAMP | Start time |
| updated_at | TIMESTAMP | Last activity |

## Table: `chat_messages`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| session_id | UUID | FK to chat_sessions |
| user_id | UUID | FK to users |
| role | VARCHAR(20) | user, assistant, system |
| content | TEXT | Message content |
| context_items | JSONB | Retrieved context used |
| tokens_used | INTEGER | Token count |
| model_used | VARCHAR(50) | Which model |
| pending_actions | JSONB | Actions awaiting confirmation |
| created_at | TIMESTAMP | When sent |

### Memory Type: **EPISODIC MEMORY**
> Records of past interactions for continuity and context

### Current Sessions:

#### Session 1: Mobile App Proposal Discussion
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Session ID: aeb9852a-f0f8-487c-9dcf-581bc7623cd6                            │
│ Type: task                                                                  │
│ Title: Mobile App Proposal Discussion                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ USER: I need to review Sarah's mobile app proposal and create some tasks    │
│       from it                                                               │
│                                                                             │
│ ASSISTANT: I found Sarah's proposal for the Mobile App Project. Here's a    │
│            summary:                                                         │
│                                                                             │
│            **Project:** Mobile App for Acme Corp                            │
│            **Budget:** $150,000                                             │
│            **Timeline:** 16 weeks                                           │
│                                                                             │
│            **Key Features:**                                                │
│            1. User Authentication (OAuth, Social Login)                     │
│            2. Product Catalog with search                                   │
│            3. Shopping Cart                                                 │
│            4. Payment Integration (Stripe, Apple Pay)                       │
│            5. Push Notifications                                            │
│            6. Offline Mode                                                  │
│                                                                             │
│            Would you like me to create Jira tasks for these requirements?   │
├─────────────────────────────────────────────────────────────────────────────┤
│ USER: Yes, create tasks and assign Phase 1 to John and Phase 2 to Mike      │
│                                                                             │
│ ASSISTANT: I'll create the tasks and send the updated proposal to Sarah by  │
│            Friday.                                                          │
│                                                                             │
│            Created tasks in MOBILE project:                                 │
│            - MOBILE-42: User Authentication (John)                          │
│            - MOBILE-43: Product Catalog (John)                              │
│            - MOBILE-44: Shopping Cart (John)                                │
│            - MOBILE-45: Offline Mode (John)                                 │
│            - MOBILE-46: Payment Gateway (Mike)                              │
│            - MOBILE-47: Push Notifications (Mike)                           │
│                                                                             │
│            I'll remind you to send the updated proposal to                  │
│            sarah@client.com by Friday.                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Session 2: PROJ-55 Assignment Discussion
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Session ID: 1ce4a3c4-a796-427a-a0e9-ea8e60b31913                            │
│ Type: task                                                                  │
│ Title: PROJ-55 Assignment Discussion                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ USER: Create a task for API Documentation in the PROJ project               │
│                                                                             │
│ ASSISTANT: Created task PROJ-55: API Documentation                          │
│                                                                             │
│            **Summary:** API Documentation                                   │
│            **Project:** PROJ                                                │
│            **Status:** To Do                                                │
│            **Priority:** Medium                                             │
│                                                                             │
│            Would you like to assign this to someone?                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ USER: I'll assign it after checking with Mike                               │
│                                                                             │
│ ASSISTANT: Got it! PROJ-55 is currently unassigned. Let me know when you'd  │
│            like to assign it after speaking with Mike.                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Session 3: Design Team Meeting
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Session ID: fc321b47-ce3e-443f-8aa2-43a192a10c95                            │
│ Type: calendar                                                              │
│ Title: Design Team Meeting                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ USER: Schedule a meeting with the design team for tomorrow                  │
│                                                                             │
│ ASSISTANT: I've scheduled the Design Team Meeting:                          │
│                                                                             │
│            **When:** Tomorrow at 10:00 AM (1 hour)                          │
│            **Where:** Design Studio                                         │
│            **Attendees:** You, Emily Davis                                  │
│                                                                             │
│            Calendar invite sent to all attendees.                           │
│                                                                             │
│            You mentioned wanting to prepare slides beforehand - would you   │
│            like me to remind you?                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Where to Access:
- **Database:**
  ```sql
  -- Get sessions
  SELECT id, title, session_type FROM chat_sessions;

  -- Get messages for a session
  SELECT role, content FROM chat_messages
  WHERE session_id = 'aeb9852a-f0f8-487c-9dcf-581bc7623cd6'
  ORDER BY created_at;
  ```
- **API Endpoint:**
  - `GET http://localhost:8000/api/v1/chat/sessions/test_user_001`
  - `GET http://localhost:8000/api/v1/chat/sessions/{session_id}/messages`
- **Python Model:** `app/models/chat.py` → `class ChatSession`, `class ChatMessage`
- **API Router:** `app/api/chat.py`

### Code Reference:
```python
# app/api/chat.py:80-200
@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Main chat endpoint."""
    # 1. Get or create session
    # 2. Load chat history (episodic memory)
    # 3. Retrieve context (semantic memory)
    # 4. Run orchestrator agent
    # 5. Save message and response

# app/models/chat.py
class ChatSession(Base):
    """Represents a conversation session."""

class ChatMessage(Base):
    """Individual message in a session."""
```

---

# SECTION 7: WORKING MEMORY (Redis)

## Storage: Redis (not PostgreSQL)

### Memory Type: **WORKING MEMORY**
> Short-term, fast-access storage for active session state

### What's Stored:
- Current session context
- Cached embeddings
- Rate limiting counters
- Temporary state during multi-turn interactions

### Where to Access:
- **Redis CLI:**
  ```bash
  docker exec -it ai_assistant_redis redis-cli
  KEYS *
  GET session:test_user_001
  ```
- **Python Service:** `app/core/redis_client.py`
- **Memory Service:** `app/core/memory.py` → `class WorkingMemory`

### Code Reference:
```python
# app/core/memory.py:18-100
class WorkingMemory:
    """Redis-backed working memory for session state."""

    async def store_context(self, user_id, session_id, context):
        """Store current context for quick access."""

    async def get_context(self, user_id, session_id):
        """Retrieve current context."""

    async def clear_session(self, user_id, session_id):
        """Clear session when done."""

# app/core/redis_client.py
class RedisClient:
    """Redis connection management."""
    async def get(self, key): ...
    async def set(self, key, value, ttl=None): ...
```

---

# SECTION 8: FILE STRUCTURE REFERENCE

```
app/
├── main.py                    # FastAPI app entry point
├── config.py                  # Settings from .env
├── database.py                # PostgreSQL connection
│
├── models/                    # SQLAlchemy models (database schema)
│   ├── __init__.py
│   ├── user.py               # User, UserPreference, UserFeedback
│   ├── knowledge.py          # KnowledgeItem
│   ├── embedding.py          # Embedding (vectors)
│   ├── entity.py             # Entity, EntityMention
│   ├── chat.py               # ChatSession, ChatMessage
│   └── sync.py               # IntegrationSync
│
├── services/                  # Business logic
│   ├── __init__.py
│   ├── embedding_service.py  # Create embeddings, chunk documents
│   ├── context_service.py    # Hybrid search (semantic + entity + fulltext)
│   ├── sync_service.py       # Ingest from external sources
│   ├── entity_service.py     # Extract and manage entities
│   └── preference_service.py # Learn and retrieve preferences
│
├── agents/                    # Multi-agent system
│   ├── __init__.py
│   ├── base.py               # BaseAgent with tool support
│   ├── orchestrator.py       # Main agent that coordinates
│   ├── email_agent.py        # Email specialist
│   ├── document_agent.py     # Document specialist
│   ├── task_agent.py         # Task/Jira specialist
│   └── action_executor.py    # Executes confirmed actions
│
├── api/                       # REST API endpoints
│   ├── __init__.py
│   ├── chat.py               # POST /api/v1/chat
│   ├── sync.py               # Sync endpoints
│   ├── entities.py           # Entity CRUD
│   ├── preferences.py        # Preference endpoints
│   └── webhooks.py           # External webhooks
│
├── core/                      # Core utilities
│   ├── __init__.py
│   ├── redis_client.py       # Redis connection
│   ├── memory.py             # WorkingMemory class
│   └── external_api.py       # External API client
│
└── workers/                   # Background tasks
    ├── celery_app.py         # Celery configuration
    └── sync_tasks.py         # Async sync jobs
```

---

# SECTION 9: API ENDPOINTS

| Method | Endpoint | Description | Handler |
|--------|----------|-------------|---------|
| POST | `/api/v1/chat` | Main chat | `app/api/chat.py:chat()` |
| GET | `/api/v1/chat/sessions/{user_id}` | List sessions | `app/api/chat.py` |
| GET | `/api/v1/chat/sessions/{session_id}/messages` | Get messages | `app/api/chat.py` |
| GET | `/api/v1/entities/{user_id}` | List entities | `app/api/entities.py` |
| GET | `/api/v1/entities/{user_id}/{entity_id}` | Get entity | `app/api/entities.py` |
| GET | `/api/v1/preferences/{user_id}` | Get preferences | `app/api/preferences.py` |
| PUT | `/api/v1/preferences/{user_id}` | Update preference | `app/api/preferences.py` |
| POST | `/api/v1/sync/start` | Start sync | `app/api/sync.py` |
| GET | `/api/v1/sync/status/{user_id}` | Sync status | `app/api/sync.py` |
| GET | `/health` | Health check | `app/main.py` |
| GET | `/ready` | Readiness check | `app/main.py` |
| GET | `/docs` | Swagger UI | FastAPI auto |

---

# SECTION 10: SAMPLE QUERIES TO TRY

Once OpenAI connection works:

### About People
```
"What has Sarah sent me recently?"
"What tasks is John working on?"
"What did David ask about?"
"Who is Lisa and what does she do?"
```

### About Projects
```
"What's the status of the MOBILE project?"
"Tell me about Phoenix deployment"
"What are the blockers in ALPHA project?"
"What's happening with Q1-LAUNCH?"
```

### About Documents
```
"What's in Sarah's mobile app proposal?"
"Show me the Phoenix architecture"
"What does the roadmap say about Q1?"
"What's the status of the Alpha project?"
```

### About Tasks
```
"What tasks are blocked?"
"What's assigned to Mike?"
"What payment-related tasks are there?"
"What needs to be done for authentication?"
```

### About Meetings
```
"What meetings do I have coming up?"
"When is the Phoenix UAT kickoff?"
"What happened in the product review meeting?"
```

### Cross-Context Queries
```
"David asked for a status update - what should I tell him?"
"Lisa wants to schedule a roadmap sync - when is she available?"
"What decisions were made about Phoenix deployment?"
```

---

# SECTION 11: DATABASE ACCESS COMMANDS

### PostgreSQL
```bash
# Connect to database
docker exec -it ai_assistant_postgres psql -U ai_assistant -d ai_assistant_db

# Quick queries
\dt                           # List tables
\d knowledge_items            # Describe table
SELECT COUNT(*) FROM embeddings;
```

### Redis
```bash
# Connect to Redis
docker exec -it ai_assistant_redis redis-cli

# Commands
KEYS *
GET session:test_user_001
```

### API Testing
```bash
# Health
curl http://localhost:8000/health

# Entities
curl http://localhost:8000/api/v1/entities/test_user_001

# Preferences
curl http://localhost:8000/api/v1/preferences/test_user_001

# Chat (needs OpenAI connection)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_001", "message": "What has Sarah sent me?"}'
```
