import os
import uuid
import logging
from services.dynamodb_service import get_project, update_project
from services.bedrock_service import invoke_agent
from services.analysis_service import save_analysis

logger = logging.getLogger(__name__)

AGENT_ALIAS_ID = os.environ.get('AGENT_ALIAS_ID', 'TSTALIASID')

ANALYSIS_PROMPT = """[Analysis Mode]
Analyze all uploaded documents for this project and provide a structured response with exactly these sections:

## Summary
Provide a concise overview of the legacy system or workflow.

## Key Findings
List the most important discoveries from the documents.

## Missing Information
List what critical information is absent or unclear.

## Bottlenecks or Issues
Identify process bottlenecks, inefficiencies, or technical issues.

## Recommendations
Provide actionable recommendations for modernization or improvement."""


def handler(event, context):
    project_id = event["projectId"]
    project = get_project(project_id)

    if not project:
        return {"projectId": project_id, "status": "NOT_FOUND", "done": True}

    if project.get("status") != "READY":
        logger.warning(f"[ANALYSIS] {project_id}: not ready, status={project.get('status')}")
        return {"projectId": project_id, "status": project.get("status"), "done": False}

    agent_id = project.get("agentId")
    if not agent_id:
        logger.error(f"[ANALYSIS] {project_id}: no agentId found")
        return {"projectId": project_id, "status": "AGENT_NOT_FOUND", "done": True}

    try:
        update_project(project_id, {"status": "ANALYSIS_STARTED"})
        session_id = str(uuid.uuid4())
        raw_response = invoke_agent(agent_id, AGENT_ALIAS_ID, session_id, ANALYSIS_PROMPT)
        logger.info(f"[ANALYSIS] {project_id}: analysis complete")

        save_analysis(project_id, raw_response, session_id)
        update_project(project_id, {"status": "ANALYSIS_COMPLETE"})
        return {"projectId": project_id, "status": "ANALYSIS_COMPLETE", "done": True}
    except Exception as e:
        logger.error(f"[ANALYSIS] {project_id}: failed: {e}")
        update_project(project_id, {"status": "ANALYSIS_FAILED"})
        return {"projectId": project_id, "status": "ANALYSIS_FAILED", "done": True}
