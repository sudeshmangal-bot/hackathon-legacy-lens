# LegacyLens API Documentation

**Base URL:** `https://<lambda-url>.lambda-url.us-east-1.on.aws`

---

## Health Check

### `GET /`

**Response 200:**
```json
{
  "message": "API is running"
}
```

---

## Project APIs

### 1. Create Project

Creates a new project along with a Bedrock Knowledge Base, Data Source, and Agent.

**`POST /api/project`**

**Request Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| project_name | string | ✅ | Unique project name |
| analysis_goal | string | ❌ | e.g. "Workflow Reconstruction" |
| file_names | string[] | ❌ | Expected file names (informational only) |

```json
{
  "project_name": "Legacy Billing Modernization",
  "analysis_goal": "Workflow Reconstruction",
  "file_names": ["report.pdf", "logs.txt"]
}
```

**Response 201 (Success):**
```json
{
  "message": "Project, KB, data source, and agent created",
  "projectId": "proj_a1b2c3",
  "projectName": "Legacy Billing Modernization",
  "analysisGoal": "Workflow Reconstruction",
  "knowledgeBaseId": "HNPPFC4TB3",
  "dataSourceId": "3OYTA9DPVU",
  "agentId": "ABC123",
  "status": "AGENT_CREATED"
}
```

**Response 201 (Partial — Data Source Failed):**
```json
{
  "message": "DS creation failed. Call sync to retry.",
  "projectId": "proj_a1b2c3",
  "projectName": "Legacy Billing Modernization",
  "knowledgeBaseId": "HNPPFC4TB3",
  "status": "DS_FAILED",
  "error": "..."
}
```

**Response 201 (Partial — Agent Failed):**
```json
{
  "message": "Agent creation failed. Call sync to retry.",
  "projectId": "proj_a1b2c3",
  "projectName": "Legacy Billing Modernization",
  "knowledgeBaseId": "HNPPFC4TB3",
  "dataSourceId": "3OYTA9DPVU",
  "status": "AGENT_FAILED",
  "error": "..."
}
```

**Response 409:**
```json
{
  "detail": "Project 'Legacy Billing Modernization' already exists"
}
```

**Response 500:**
```json
{
  "detail": "Project creation failed: ..."
}
```

---

### 2. List All Projects

Returns all projects with their current status and resource IDs.

**`GET /api/project`**

**Response 200:**
```json
[
  {
    "projectId": "proj_a1b2c3",
    "projectName": "Legacy Billing Modernization",
    "analysisGoal": "Workflow Reconstruction",
    "fileNames": ["report.pdf", "logs.txt"],
    "status": "ANALYSIS_COMPLETE",
    "knowledgeBaseId": "HNPPFC4TB3",
    "dataSourceId": "3OYTA9DPVU",
    "agentId": "ABC123",
    "kbAssociated": true,
    "ingestedFiles": [],
    "ingestionJobId": "JOB123",
    "createdAt": "2026-04-04T07:20:48.905068+00:00",
    "updatedAt": "2026-04-04T07:20:49.286869+00:00",
    "isDeleted": false
  }
]
```

---

### 3. Generate Pre-signed Upload URLs

Generates S3 pre-signed URLs for uploading files to a project. Files are uploaded directly from the browser to S3 using these URLs.

**`POST /api/project/{project_id}/presigned-urls`**

**Path Parameters:**
| Parameter | Type | Description |
|---|---|---|
| project_id | string | e.g. `proj_a1b2c3` |

**Request Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| files | FileRequest[] | ✅ | List of files to upload (min 1) |

**FileRequest:**
| Field | Type | Required | Description |
|---|---|---|---|
| filename | string | ✅ | File name with extension |
| content_type | string | ✅ | MIME type (e.g. `application/pdf`) |

```json
{
  "files": [
    {"filename": "report.pdf", "content_type": "application/pdf"},
    {"filename": "logs.txt", "content_type": "text/plain"}
  ]
}
```

**Response 200:**
```json
{
  "message": "Pre-signed URLs generated",
  "files": [
    {
      "filename": "report.pdf",
      "upload_url": "https://bucket.s3.amazonaws.com/projects/proj_a1b2c3/raw_data/report.pdf?...",
      "s3_key": "projects/proj_a1b2c3/raw_data/report.pdf"
    }
  ]
}
```

**Response 400 (No Files):**
```json
{
  "detail": "No files provided"
}
```

**Response 400 (Duplicate Filenames):**
```json
{
  "detail": "Duplicate filenames: report.pdf"
}
```

**Response 404:**
```json
{
  "detail": "Project proj_xyz not found"
}
```

**How to upload using the pre-signed URL (frontend):**
```javascript
await fetch(upload_url, {
  method: "PUT",
  headers: { "Content-Type": content_type },
  body: file
});
```

Pre-signed URLs expire in **5 minutes**.

---

### 4. Sync Project

Compares S3 files against last ingested files and triggers ingestion if files have changed. Also recovers from failed KB, Data Source, or Agent creation before syncing. Once ingestion starts, Step Functions automatically polls until complete, associates KB to agent, and triggers analysis.

**`POST /api/project/{project_id}/sync`**

**Path Parameters:**
| Parameter | Type | Description |
|---|---|---|
| project_id | string | e.g. `proj_a1b2c3` |

**Response 200 (Ingestion Started):**
```json
{
  "message": "Ingestion started",
  "projectId": "proj_a1b2c3",
  "ingestionJobId": "JOB123",
  "filesChanged": true
}
```

**Response 200 (Already In Sync):**
```json
{
  "message": "Already in sync",
  "projectId": "proj_a1b2c3"
}
```

**Response 404:**
```json
{
  "detail": "Project proj_xyz not found"
}
```

**Response 500 (Recovery Failed):**
```json
{
  "detail": "KB creation failed: ..."
}
```

---

### 5. Get Analysis Result

Returns the structured analysis result generated automatically by the agent after ingestion completes. Analysis is stored in a separate `ProjectAnalysis` table with 5 categorized columns.

**`GET /api/project/{project_id}/analysis`**

**Path Parameters:**
| Parameter | Type | Description |
|---|---|---|
| project_id | string | e.g. `proj_a1b2c3` |

**Response 200 (Analysis Complete):**
```json
{
  "projectId": "proj_a1b2c3",
  "status": "ANALYSIS_COMPLETE",
  "analysis": {
    "projectId": "proj_a1b2c3",
    "summary": "The legacy billing system handles...",
    "keyFindings": "- Invoice processing is manual\n- No audit trail exists...",
    "missingInformation": "- No database schema provided\n- Missing SLA documents...",
    "bottlenecksOrIssues": "- Manual approval causes 3-day delays\n- No error handling...",
    "recommendations": "- Automate invoice processing\n- Introduce event-driven architecture...",
    "sessionId": "uuid",
    "createdAt": "2026-04-04T07:20:49.286869+00:00"
  }
}
```

**Response 202 (Analysis Not Yet Ready — keep polling):**
```json
{
  "projectId": "proj_a1b2c3",
  "status": "ANALYSIS_STARTED",
  "analysis": null
}
```

**Response 404:**
```json
{
  "detail": "Project proj_xyz not found"
}
```

**Polling guide:**
| Status Code | Meaning |
|---|---|
| `202` | Analysis not ready yet, keep polling |
| `200` | Analysis complete or failed, stop polling |
| `404` | Project not found, stop polling |

---

### 6. Chat with Agent

Sends a message to the project's Bedrock Agent in Assistant Mode. Use the same `session_id` across multiple messages to maintain conversation context.

**`POST /api/project/{project_id}/chat`**

**Path Parameters:**
| Parameter | Type | Description |
|---|---|---|
| project_id | string | e.g. `proj_a1b2c3` |

**Request Body:**
| Field | Type | Required | Description |
|---|---|---|---|
| message | string | ✅ | User message |
| session_id | string | ❌ | Session ID for conversation continuity. Auto-generated if not provided |

```json
{
  "message": "What are the main workflows in this system?",
  "session_id": "my-session-123"
}
```

**Response 200:**
```json
{
  "projectId": "proj_a1b2c3",
  "sessionId": "my-session-123",
  "response": "Based on the uploaded documents, the main workflows are..."
}
```

**Response 400 (Agent Not Created):**
```json
{
  "detail": "Agent not created for this project. Call sync first."
}
```

**Response 400 (Project Not Ready):**
```json
{
  "detail": "Project is not ready for chat (status: INGESTION_STARTED). Wait for ingestion to complete."
}
```

**Response 404:**
```json
{
  "detail": "Project proj_xyz not found"
}
```

**Response 500:**
```json
{
  "detail": "Chat failed: ..."
}
```

---

## Project Status Reference

The `status` field in the project record tracks the current state:

| Status | Meaning |
|---|---|
| `CREATED` | Project created, KB setup not started |
| `KB_CREATED` | Knowledge base created successfully |
| `KB_FAILED` | Knowledge base creation failed |
| `DS_CREATED` | Data source created successfully |
| `DS_FAILED` | Data source creation failed |
| `AGENT_CREATED` | Agent created successfully |
| `AGENT_FAILED` | Agent creation failed |
| `INGESTION_STARTED` | File ingestion triggered |
| `INGESTION_COMPLETE` | Ingestion finished successfully |
| `INGESTION_FAILED` | Ingestion failed |
| `READY` | KB associated to agent, ready for chat and analysis |
| `KB_ASSOCIATION_FAILED` | KB-agent association failed |
| `ANALYSIS_STARTED` | Automated analysis in progress |
| `ANALYSIS_COMPLETE` | Analysis finished, result stored in ProjectAnalysis table |
| `ANALYSIS_FAILED` | Analysis invocation failed |

---

## Automated Backend Flow (Step Functions)

After `POST /api/project/{id}/sync` is called, the following happens automatically in the background:

```
POST /api/project/{id}/sync
  → Ingestion starts in Bedrock
  → Step Functions starts polling every 15s
  → Ingestion completes → KB associated to agent → status = READY
  → Analysis triggered automatically in Analysis Mode
  → Structured result stored in ProjectAnalysis DynamoDB table
  → status = ANALYSIS_COMPLETE
```

---

## Typical Frontend Flow

```
1. POST /api/project                           → Create project + KB + data source + agent
2. POST /api/project/{id}/presigned-urls        → Get upload URLs
3. PUT  <presigned_url>                         → Upload files directly to S3
4. POST /api/project/{id}/sync                  → Ingest files + triggers automated analysis
5. GET  /api/project                            → Poll until status = ANALYSIS_COMPLETE
6. GET  /api/project/{id}/analysis              → Fetch structured analysis result
7. POST /api/project/{id}/chat                  → Chat with agent in Assistant Mode
```

---

## Error Format

All errors follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

| HTTP Code | Meaning |
|---|---|
| 400 | Bad request (validation error) |
| 404 | Resource not found |
| 409 | Conflict (duplicate) |
| 500 | Server error |
