TEST CATEGORY 1: SIMPLE SINGLE-SOURCE QUERIES Easy
Test E001: Simple Person Search
json
POST /api/v1/chat
{
  "user_id": "test_user_001",
  "message": "What has Sarah sent me recently?"
}
Expected Results:
✅ Route to: Gmail only
✅ Entity detected: Sarah Johnson
✅ Context fetched: "Mobile App Project Proposal", "Sprint Planning Session"
✅ Response mentions: mobile app, Q2, $150k budget
⏱️ Time scope: Recent emails
❌ Should NOT mention: Jira tasks, calendar events
Score: 10 points
✅Output:
{
    "session_id": "3016aadf-3c0e-4869-bc3f-9974cb0c394d",
    "response": "The last email from Sarah is titled **\"Mobile App Project Proposal.\"** Here's a brief summary:\n\n- **Content:** Sarah sent a proposal for mobile app development, including an attached PDF with detailed requirements. The project deadline is set for Q2, with a budget of $150k. She is requesting a review and task creation.\n\nWould you like to take any specific actions regarding this email, such as responding or reviewing it?",
    "needs_clarification": true,
    "clarification": {
        "question": "Would you like to take any specific actions on Sarah's last email regarding the 'Mobile App Project Proposal'?",
        "options": null,
        "required_for": null
    },
    "context_used": [
        {
            "id": "fd21065a-6cdd-4194-a8d7-58eb9d02e441",
            "source": "gmail",
            "title": "Mobile App Project Proposal",
            "summary": "Sarah sent proposal for mobile app development. Attached PDF with detailed requirements. Project deadline is Q2 with budget of $150k. Requesting review and task creation.",
            "content_type": "email",
            "source_created_at": "2025-11-30T10:53:16.683538+00:00",
            "relevance_score": 0.603
        },
        {
            "id": "84e0f49b-ffac-4ab7-a401-ec300fb6a2a3",
            "source": "gmail",
            "title": "Re: Mobile App Project Proposal",
            "summary": "Follow-up discussion about timeline and resources. Sarah confirms deadline flexibility and asks about team allocation.",
            "content_type": "email",
            "source_created_at": "2025-12-01T10:53:16.683538+00:00",
            "relevance_score": 0.603
        },
        {
            "id": "00517bc6-c377-496e-aa6e-6e99e8be3371",
            "source": "gmail",
            "title": "Team Sync - Roadmap Discussion",
            "summary": "Lisa proposing team sync meeting to discuss roadmap. Available Tuesday 2-4pm, Wednesday 10am-12pm, Thursday after 3pm. Attendees: Lisa, John, Sarah, Mike.",
            "content_type": "email",
            "source_created_at": "2025-12-01T10:53:16.683538+00:00",
            "relevance_score": 0.603
        },
        {
            "id": "f52d52c8-eab1-4d1e-a37c-c96187891ad5",
            "source": "gmail",
            "title": "Feature Request - Dark Mode",
            "summary": "Client requesting dark mode support for mobile app. High priority, deadline end of Q1. Users have been requesting this feature frequently.",
            "content_type": "email",
            "source_created_at": "2025-12-02T10:53:16.683538+00:00",
            "relevance_score": 0.603
        },
        {
            "id": "fc14390e-9ec7-4ff0-97c7-6cb802e3d320",
            "source": "gmail",
            "title": "Phoenix Deployment Schedule",
            "summary": "Update on Phoenix project deployment schedule. Moving to AWS instead of GCP. Go-live date confirmed for February 28. UAT kickoff scheduled for Thursday.",
            "content_type": "email",
            "source_created_at": "2025-12-02T16:53:16.683538+00:00",
            "relevance_score": 0.603
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 4510,
    "model_used": "gpt-4o-mini"
}



Test E002: Simple Task Query
json
{
  "user_id": "test_user_001",
  "message": "What tasks are assigned to Mike?"
}
Expected:
✅ Route to: Jira only
✅ Entity: Mike Chen
✅ Context: "MOBILE-103", "ALPHA-201"
✅ Response mentions: payment gateway integration, API documentation
❌ Should NOT mention: emails, documents
Score: 10 points
Output:
{
    "session_id": "5018d288-631b-4dac-b1fd-5d2e39af6511",
    "response": "Here are the tasks and meetings assigned to Mike:\n\n1. **Meeting Notes - Product Review**\n   - Summary: Product review meeting notes discussing Q1 priorities, approved new design mockups, and feature prioritization. Action items assigned to team members.\n   - Source: Gmail\n\n2. **Phoenix Go-Live Planning**\n   - Summary: Discussed deployment timeline, decided on AWS over GCP, and confirmed go-live date (February 28). Action items assigned.\n   - Attendees: Lisa, Mike, John, Test User\n   - Source: Calendar\n\n3. **Phoenix Deployment Schedule**\n   - Summary: Update on the Phoenix project deployment schedule, confirming the move to AWS and go-live date. UAT kickoff scheduled for Thursday.\n   - Source: Gmail\n\n4. **Team Sync - Roadmap Discussion**\n   - Summary: Proposal for a team sync meeting to discuss the roadmap. Available times: Tuesday 2-4pm, Wednesday 10am-12pm, Thursday after 3pm.\n   - Attendees: Lisa, John, Sarah, Mike\n   - Source: Gmail\n\n5. **Re: Mobile App Project Proposal**\n   - Summary: Follow-up discussion about the timeline and resources. Confirmation of deadline flexibility and team allocation.\n   - Source: Gmail\n\nIf you need more details or actions related to these tasks, please let me know!",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [
        {
            "id": "8e3a775e-3fce-499e-a094-d99e24e41963",
            "source": "gmail",
            "title": "Meeting Notes - Product Review",
            "summary": "Product review meeting notes. Discussed Q1 priorities, approved new design mockups, decided on feature prioritization. Action items assigned to team members.",
            "content_type": "email",
            "source_created_at": "2025-11-28T10:53:16.683538+00:00",
            "relevance_score": 0.433
        },
        {
            "id": "0ccbd636-793e-40f1-a002-c2c2fc225b65",
            "source": "calendar",
            "title": "Phoenix Go-Live Planning",
            "summary": null,
            "content_type": "event",
            "source_created_at": "2025-11-27T20:53:16.874049+00:00",
            "relevance_score": 0.383
        },
        {
            "id": "fc14390e-9ec7-4ff0-97c7-6cb802e3d320",
            "source": "gmail",
            "title": "Phoenix Deployment Schedule",
            "summary": "Update on Phoenix project deployment schedule. Moving to AWS instead of GCP. Go-live date confirmed for February 28. UAT kickoff scheduled for Thursday.",
            "content_type": "email",
            "source_created_at": "2025-12-02T16:53:16.683538+00:00",
            "relevance_score": 0.267
        },
        {
            "id": "00517bc6-c377-496e-aa6e-6e99e8be3371",
            "source": "gmail",
            "title": "Team Sync - Roadmap Discussion",
            "summary": "Lisa proposing team sync meeting to discuss roadmap. Available Tuesday 2-4pm, Wednesday 10am-12pm, Thursday after 3pm. Attendees: Lisa, John, Sarah, Mike.",
            "content_type": "email",
            "source_created_at": "2025-12-01T10:53:16.683538+00:00",
            "relevance_score": 0.267
        },
        {
            "id": "84e0f49b-ffac-4ab7-a401-ec300fb6a2a3",
            "source": "gmail",
            "title": "Re: Mobile App Project Proposal",
            "summary": "Follow-up discussion about timeline and resources. Sarah confirms deadline flexibility and asks about team allocation.",
            "content_type": "email",
            "source_created_at": "2025-12-01T10:53:16.683538+00:00",
            "relevance_score": 0.267
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 2982,
    "model_used": "gpt-4o-mini"
}

Test E003: Document Lookup
json
{
  "user_id": "test_user_001",
  "message": "What's in the Phoenix architecture document?"
}
Expected:
✅ Route to: Google Drive only
✅ Entity: Phoenix
✅ Context: "Phoenix System Architecture.pdf"
✅ Response mentions: microservices, Kubernetes, AWS
❌ Should NOT mention: unrelated projects
Score: 10 points
✅Output:
{
    "session_id": "6deb0acd-9a01-48c2-b5fa-d31c9e018e7a",
    "response": "The **Phoenix architecture document** titled **\"Phoenix_Architecture_v3.pdf\"** contains the following key information:\n\n### System Overview\n- Phoenix is a microservices-based infrastructure platform designed for **high availability** and **scalability**.\n\n### Architecture Components\n- The document outlines various components of the architecture, though the specifics weren't fully retrieved.\n\nIf you would like to access the complete document or need more details, please let me know!",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [
        {
            "id": "a2ffbd33-17af-43a5-b0c3-8cf74f83ff7c",
            "source": "gdrive",
            "title": "Phoenix_Architecture_v3.pdf",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-30T10:53:16.741262+00:00",
            "relevance_score": 0.59
        },
        {
            "id": "436b2026-52ec-4181-9fed-dbc3da05e2fd",
            "source": "gdrive",
            "title": "Platform_Team_Onboarding.docx",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-18T10:53:16.741262+00:00",
            "relevance_score": 0.58
        },
        {
            "id": "072fed6f-56ad-46d0-b6a2-482edafef57e",
            "source": "gdrive",
            "title": "Alpha_Project_Status_Report_Jan2024.docx",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-12-01T10:53:16.741262+00:00",
            "relevance_score": 0.33
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 2612,
    "model_used": "gpt-4o-mini"
}

Test E004: Meeting Query
json
{
  "user_id": "test_user_001",
  "message": "When is the Product Review meeting?"
}
Expected:
✅ Route to: Calendar only
✅ Context: "Product Review with Stakeholders"
✅ Response mentions: December 6, 2025, 3:00 PM, Conference Room A
✅ Attendees: Lisa Martinez, John Smith, others
Score: 10 points
Output:
{
    "session_id": "3ca9e6e9-17d9-4476-b9d6-d8627a760057",
    "response": "It appears that there is no specific \"Product Review\" meeting scheduled in the calendar. However, there is a related meeting called the **Q1 Project Review Meeting**. \n\n### Q1 Project Review Meeting Details:\n- **Purpose:** Weekly project review meeting to discuss Q1 progress, blockers, and next steps.\n\nWould you like me to provide more information about this meeting or assist you with anything else?",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [
        {
            "id": "f37f49c7-4850-4fa5-a32c-ddad1efe6486",
            "source": "calendar",
            "title": "Q1 Project Review Meeting",
            "summary": null,
            "content_type": "event",
            "source_created_at": "2025-12-05T00:53:16.874049+00:00",
            "relevance_score": 0.783
        },
        {
            "id": "af9931d3-d89b-4f4d-85f7-c325e437201d",
            "source": "calendar",
            "title": "Design Team Meeting",
            "summary": null,
            "content_type": "event",
            "source_created_at": "2025-12-04T20:53:16.874049+00:00",
            "relevance_score": 0.783
        },
        {
            "id": "0ccbd636-793e-40f1-a002-c2c2fc225b65",
            "source": "calendar",
            "title": "Phoenix Go-Live Planning",
            "summary": null,
            "content_type": "event",
            "source_created_at": "2025-11-27T20:53:16.874049+00:00",
            "relevance_score": 0.783
        },
        {
            "id": "9ac043c3-33e5-4959-ad00-1f567af31c11",
            "source": "calendar",
            "title": "Phoenix UAT Kickoff",
            "summary": null,
            "content_type": "event",
            "source_created_at": "2025-12-05T20:53:16.874049+00:00",
            "relevance_score": 0.617
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 5191,
    "model_used": "gpt-4o-mini"
}

TEST CATEGORY 2: ENTITY RECOGNITION & TRACKING Medium
Test M001: Ambiguous Entity Reference
json
{
  "user_id": "test_user_001",
  "message": "What's the latest from John?"
}
Expected:
✅ Entity resolved: John Smith (Developer)
✅ Route to: Gmail + Jira
✅ Context: Email "Need backend review" + Jira tasks MOBILE-102, ALPHA-202
✅ Response integrates both sources
🎯 Challenge: Multiple Johns don't exist, but system should handle properly
Score: 15 points
{
    "session_id": "6d50fc79-a7c1-445c-9a57-1e6f168ca38e",
    "response": "It looks like there are no recent updates or messages from John in the internal records. If you're looking for something specific, could you please clarify what information or context regarding John you are interested in?",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 6144,
    "model_used": "gpt-4o-mini"
}


Test M002: Project Entity Across Sources
json
{
  "user_id": "test_user_001",
  "message": "Tell me everything about the MOBILE project"
}
Expected:
✅ Entity: Mobile App Project
✅ Route to: Gmail + Jira + Google Drive + Calendar
✅ Context from Gmail: Sarah's proposal email
✅ Context from Jira: MOBILE-101, MOBILE-102, MOBILE-103, MOBILE-104
✅ Context from Drive: Requirements doc (if exists)
✅ Context from Calendar: Sprint planning session
✅ Response synthesizes: proposal + current tasks + status
Challenge: Merge information from 4 sources coherently
Score: 20 points
✅Output:{
    "session_id": "4e07aeeb-f0aa-4fdd-bb07-7b6b86a78640",
    "response": "Here's a summary of the **MOBILE project** based on the available context:\n\n### Project Overview\n- **Name:** MOBILE\n- **Type:** Project focused on mobile application development for Acme Corp's e-commerce platform.\n\n### Key Documents and Emails:\n1. **Mobile App Project Proposal**\n   - **Source:** Gmail\n   - **Summary:** A proposal sent by Sarah for mobile app development with a detailed PDF attached. The project deadline is set for Q2 with a budget of $150k. Requests for review and task creation were made.\n\n2. **Re: Mobile App Project Proposal**\n   - **Source:** Gmail\n   - **Summary:** Follow-up discussion regarding the timeline and resources. Sarah confirmed flexibility on the deadline and inquired about team allocation.\n\n3. **Mobile_App_Proposal_v2.pdf**\n   - **Source:** Google Drive\n   - **Summary:** Detailed project proposal document outlining requirements such as user authentication using OAuth 2.0.\n\n4. **Feature Request - Dark Mode**\n   - **Source:** Gmail\n   - **Summary:** A client has requested dark mode support for the mobile app, marked as high priority with a deadline by the end of Q1.\n\n5. **Mobile_App_Roadmap_2024.docx**\n   - **Source:** Google Drive\n   - **Summary:** This document outlines the roadmap for the mobile app in 2024, including a table detailing features, priorities, statuses, and notes.\n\n### Current Focus:\n- The project is primarily focusing on developing features for the mobile app, including high-priority requests like dark mode support.\n\nIf you need more specific information or actions related to the MOBILE project, please let me know!",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [
        {
            "id": "fd21065a-6cdd-4194-a8d7-58eb9d02e441",
            "source": "gmail",
            "title": "Mobile App Project Proposal",
            "summary": "Sarah sent proposal for mobile app development. Attached PDF with detailed requirements. Project deadline is Q2 with budget of $150k. Requesting review and task creation.",
            "content_type": "email",
            "source_created_at": "2025-11-30T10:53:16.683538+00:00",
            "relevance_score": 0.81
        },
        {
            "id": "84e0f49b-ffac-4ab7-a401-ec300fb6a2a3",
            "source": "gmail",
            "title": "Re: Mobile App Project Proposal",
            "summary": "Follow-up discussion about timeline and resources. Sarah confirms deadline flexibility and asks about team allocation.",
            "content_type": "email",
            "source_created_at": "2025-12-01T10:53:16.683538+00:00",
            "relevance_score": 0.805
        },
        {
            "id": "c942ef52-3104-403f-9528-7c23503122c5",
            "source": "gdrive",
            "title": "Mobile_App_Proposal_v2.pdf",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-28T10:53:16.741262+00:00",
            "relevance_score": 0.797
        },
        {
            "id": "f52d52c8-eab1-4d1e-a37c-c96187891ad5",
            "source": "gmail",
            "title": "Feature Request - Dark Mode",
            "summary": "Client requesting dark mode support for mobile app. High priority, deadline end of Q1. Users have been requesting this feature frequently.",
            "content_type": "email",
            "source_created_at": "2025-12-02T10:53:16.683538+00:00",
            "relevance_score": 0.55
        },
        {
            "id": "d1f0190a-2e47-4a88-befe-05b22f2ff7cb",
            "source": "gdrive",
            "title": "Mobile_App_Roadmap_2024.docx",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-23T10:53:16.741262+00:00",
            "relevance_score": 0.53
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 4319,
    "model_used": "gpt-4o-mini"
}

Test M003: Email Address vs Name
json
{
  "user_id": "test_user_001",
  "message": "What did sarah@client.com send me?"
}
Expected:
✅ Entity resolved: sarah@client.com → Sarah Johnson
✅ Same results as Test E001
🎯 Challenge: Handle email format vs name format
Score: 15 points
Output:
{
    "session_id": "e86315a6-af86-4dc4-81c4-e87528ee4217",
    "response": "It appears that there are no emails from **sarah@client.com** in your inbox. If you need further assistance or would like to check something else, please let me know!",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 2244,
    "model_used": "gpt-4o-mini"
}

TEST CATEGORY 3: TEMPORAL REASONING  
Test T002: Date Range Query
json
{
  "user_id": "test_user_001",
  "message": "Show me all emails from November 2025"
}
Expected:
✅ Time scope: November 1-30, 2025
✅ Route to: Gmail only
✅ Context: Emails with source_created_at in November
✅ Response lists: Mobile App Proposal (Nov 30), Sprint Planning (Nov 29), etc.
Score: 15 points
Output:
{
    "session_id": "dec514a5-b535-4624-b536-6ebc21c18435",
    "response": "It seems there are no emails from November 2025 in the available records. The search returned one document related to the Phoenix Project, but no emails were found for that timeframe. \n\nIf you need assistance with something else, please let me know!",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [
        {
            "id": "a2ffbd33-17af-43a5-b0c3-8cf74f83ff7c",
            "source": "gdrive",
            "title": "Phoenix_Architecture_v3.pdf",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-30T10:53:16.741262+00:00",
            "relevance_score": 0.333
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 2365,
    "model_used": "gpt-4o-mini"
}
Test T004: Future Events
json
{
  "user_id": "test_user_001",
  "message": "What meetings do I have coming up?"
}
Expected:
✅ Time scope: Future from now
✅ Route to: Calendar only
✅ Filter: Events with start_time > current_time
✅ Response sorted: Nearest first
✅ Should show: "Product Review" (Dec 6), "Phoenix UAT Kickoff" (Dec 10)
Score: 15 points
Output:
Nothing appearing for calender
TEST CATEGORY 4: MULTI-SOURCE INTEGRATION 
Hard
Test H001: Cross-Reference Query
json
{
  "user_id": "test_user_001",
  "message": "David asked for a status update on the mobile project. What should I tell him?"
}
Expected:
✅ Entities: David Kim, Mobile project
✅ Route to: Gmail (David's email) + Jira (MOBILE tasks) + Calendar (related meetings)
✅ Context: David's email "Status Update Request"
✅ Context: All MOBILE Jira tasks with current status
✅ Context: Sprint planning meeting notes
✅ Response structure:
Acknowledge David's request
Summary of MOBILE project status
Task breakdown (what's done, in progress, blocked)
Timeline/next steps
✅ Action: Draft email to David
🎯 Challenge: Synthesize from 3 sources + plan action
Score: 25 points
Output:
{
    "session_id": "09f9d78e-767a-4009-a6ae-57c278bb0a45",
    "response": "I need more information to prepare the status update for David. What specific details do you want to include? For example, do you want to mention the completion percentage, any blockers, or the expected completion date?",
    "needs_clarification": true,
    "clarification": {
        "question": "What specific details do you want to include in the status update for David?",
        "options": null,
        "required_for": null
    },
    "context_used": [
        {
            "id": "84e0f49b-ffac-4ab7-a401-ec300fb6a2a3",
            "source": "gmail",
            "title": "Re: Mobile App Project Proposal",
            "summary": "Follow-up discussion about timeline and resources. Sarah confirms deadline flexibility and asks about team allocation.",
            "content_type": "email",
            "source_created_at": "2025-12-01T10:53:16.683538+00:00",
            "relevance_score": 0.609
        },
        {
            "id": "c942ef52-3104-403f-9528-7c23503122c5",
            "source": "gdrive",
            "title": "Mobile_App_Proposal_v2.pdf",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-28T10:53:16.741262+00:00",
            "relevance_score": 0.601
        },
        {
            "id": "77921e1d-76e5-4462-88fc-486883f5af69",
            "source": "gmail",
            "title": "Q1 Project Status Update Request",
            "summary": "David from partner company requesting Q1 project status update. Needs completion percentage, blockers, and expected completion date for stakeholder meeting.",
            "content_type": "email",
            "source_created_at": "2025-12-03T04:53:16.683538+00:00",
            "relevance_score": 0.475
        },
        {
            "id": "fc14390e-9ec7-4ff0-97c7-6cb802e3d320",
            "source": "gmail",
            "title": "Phoenix Deployment Schedule",
            "summary": "Update on Phoenix project deployment schedule. Moving to AWS instead of GCP. Go-live date confirmed for February 28. UAT kickoff scheduled for Thursday.",
            "content_type": "email",
            "source_created_at": "2025-12-02T16:53:16.683538+00:00",
            "relevance_score": 0.35
        },
        {
            "id": "fd21065a-6cdd-4194-a8d7-58eb9d02e441",
            "source": "gmail",
            "title": "Mobile App Project Proposal",
            "summary": "Sarah sent proposal for mobile app development. Attached PDF with detailed requirements. Project deadline is Q2 with budget of $150k. Requesting review and task creation.",
            "content_type": "email",
            "source_created_at": "2025-11-30T10:53:16.683538+00:00",
            "relevance_score": 0.35
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 4457,
    "model_used": "gpt-4o-mini"
}

Test H003: Decision Context
json
{
  "user_id": "test_user_001",
  "message": "What decisions were made about Phoenix deployment?"
}
Expected:
✅ Entity: Phoenix
✅ Route to: Gmail + Google Drive + Calendar (meeting notes if available)
✅ Context: Emails discussing deployment
✅ Context: Phoenix Architecture doc
✅ Response extracts: Deployment decisions, timeline, tech stack choices
🎯 Challenge: Extract decision-type information from unstructured content
Score: 25 points
Output:
{
    "session_id": "20f3a9ab-9202-4ebf-921f-425e59f90e5f",
    "response": "Here are the key decisions made regarding the Phoenix deployment:\n\n1. **Deployment Platform**: It was decided to deploy on **AWS** instead of **GCP**.\n2. **Go-Live Date**: The confirmed go-live date is **February 28**.\n3. **UAT Kickoff**: The User Acceptance Testing (UAT) kickoff is scheduled for **Thursday**.\n\nIf you need more detailed information or specific documents related to these decisions, please let me know!",
    "needs_clarification": false,
    "clarification": null,
    "context_used": [
        {
            "id": "436b2026-52ec-4181-9fed-dbc3da05e2fd",
            "source": "gdrive",
            "title": "Platform_Team_Onboarding.docx",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-18T10:53:16.741262+00:00",
            "relevance_score": 0.581
        },
        {
            "id": "0ccbd636-793e-40f1-a002-c2c2fc225b65",
            "source": "calendar",
            "title": "Phoenix Go-Live Planning",
            "summary": null,
            "content_type": "event",
            "source_created_at": "2025-11-27T20:53:16.874049+00:00",
            "relevance_score": 0.558
        },
        {
            "id": "fc14390e-9ec7-4ff0-97c7-6cb802e3d320",
            "source": "gmail",
            "title": "Phoenix Deployment Schedule",
            "summary": "Update on Phoenix project deployment schedule. Moving to AWS instead of GCP. Go-live date confirmed for February 28. UAT kickoff scheduled for Thursday.",
            "content_type": "email",
            "source_created_at": "2025-12-02T16:53:16.683538+00:00",
            "relevance_score": 0.446
        },
        {
            "id": "8e3a775e-3fce-499e-a094-d99e24e41963",
            "source": "gmail",
            "title": "Meeting Notes - Product Review",
            "summary": "Product review meeting notes. Discussed Q1 priorities, approved new design mockups, decided on feature prioritization. Action items assigned to team members.",
            "content_type": "email",
            "source_created_at": "2025-11-28T10:53:16.683538+00:00",
            "relevance_score": 0.267
        },
        {
            "id": "a2ffbd33-17af-43a5-b0c3-8cf74f83ff7c",
            "source": "gdrive",
            "title": "Phoenix_Architecture_v3.pdf",
            "summary": null,
            "content_type": "document",
            "source_created_at": "2025-11-30T10:53:16.741262+00:00",
            "relevance_score": 0.247
        }
    ],
    "pending_actions": [],
    "completed_actions": [],
    "tokens_used": 2798,
    "model_used": "gpt-4o-mini"
}

