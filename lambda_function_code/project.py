import os
import uuid
import json
import logging
import boto3
from fastapi import APIRouter, HTTPException, Response

from api.models.project import CreateProjectRequest, PresignedUrlRequest, ChatRequest
from services.dynamodb_service import create_project, get_all_projects, get_project, update_project, project_name_exists
from services.knowledge_base_service import create_kb, create_datasource, sync_project_files
from services.agent_service import create_agent_draft
from services.s3_service import generate_presigned_url
from services.bedrock_service import invoke_agent
from services.analysis_service import get_analysis

router = APIRouter()
logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_ROLE_ARN = os.environ.get('KNOWLEDGE_BASE_ROLE_ARN', '')
AGENT_ROLE_ARN = os.environ.get('AGENT_ROLE_ARN', '')
S3_BUCKET = os.environ.get('S3_BUCKET', '')
STEP_FUNCTIONS_ARN = os.environ.get('STEP_FUNCTIONS_ARN', '')
AGENT_ALIAS_ID = os.environ.get('AGENT_ALIAS_ID', 'TSTALIASID')

sfn_client = boto3.client('stepfunctions', region_name='us-east-1')


@router.get("")
def get_projects_route():
    try:
        return get_all_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")


@router.post("", status_code=201)
def create_project_route(request: CreateProjectRequest):
    if project_name_exists(request.project_name):
        raise HTTPException(status_code=409, detail=f"Project '{request.project_name}' already exists")
    try:
        project = create_project(request.project_name, request.analysis_goal, request.file_names)
        project_id = project["projectId"]
        result = {"projectId": project_id, "projectName": project["projectName"], "analysisGoal": project["analysisGoal"]}

        # Step 1: KB
        kb_result = create_kb(request.project_name, project_id, KNOWLEDGE_BASE_ROLE_ARN)
        update_project(project_id, {"knowledgeBaseId": kb_result["knowledgeBaseId"], "status": "KB_CREATED"})
        result["knowledgeBaseId"] = kb_result["knowledgeBaseId"]

        # Step 2: Data Source
        try:
            ds_result = create_datasource(kb_result["knowledgeBaseId"], project_id)
            update_project(project_id, {"dataSourceId": ds_result["dataSourceId"], "status": "DS_CREATED"})
            result["dataSourceId"] = ds_result["dataSourceId"]
        except Exception as e:
            logger.error(f"[PROJECT] {project_id}: DS creation failed: {e}")
            update_project(project_id, {"status": "DS_FAILED"})
            return {**result, "message": "DS creation failed. Call sync to retry.", "status": "DS_FAILED", "error": str(e)}

        # Step 3: Agent
        try:
            agent_result = create_agent_draft(f"agent-{project_id}", AGENT_ROLE_ARN)
            update_project(project_id, {"agentId": agent_result["agentId"], "status": "AGENT_CREATED"})
            result["agentId"] = agent_result["agentId"]
        except Exception as e:
            logger.error(f"[PROJECT] {project_id}: Agent creation failed: {e}")
            update_project(project_id, {"status": "AGENT_FAILED"})
            return {**result, "message": "Agent creation failed. Call sync to retry.", "status": "AGENT_FAILED", "error": str(e)}

        logger.info(f"[PROJECT] Created {project_id}: KB={kb_result['knowledgeBaseId']}, DS={ds_result['dataSourceId']}, Agent={agent_result['agentId']}")
        return {**result, "message": "Project, KB, data source, and agent created", "status": "AGENT_CREATED"}
    except Exception as e:
        logger.error(f"[PROJECT] Creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Project creation failed: {str(e)}")


@router.post("/{project_id}/presigned-urls")
def generate_upload_urls(project_id: str, request: PresignedUrlRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")

    filenames = [f.filename for f in request.files]
    duplicates = {f for f in filenames if filenames.count(f) > 1}
    if duplicates:
        raise HTTPException(status_code=400, detail=f"Duplicate filenames: {', '.join(duplicates)}")

    return {
        "message": "Pre-signed URLs generated",
        "files": [generate_presigned_url(S3_BUCKET, f.filename, f.content_type, project_id) for f in request.files]
    }


@router.get("/{project_id}/analysis")
def get_analysis_result(project_id: str, response: Response):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if project.get("status") not in ("ANALYSIS_COMPLETE", "ANALYSIS_FAILED"):
        response.status_code = 202
        return {"projectId": project_id, "status": project.get("status"), "analysis": None}

    analysis = get_analysis(project_id)
    return {
        "projectId": project_id,
        "status": project.get("status"),
        "analysis": analysis
    }


@router.post("/{project_id}/chat")
def chat_with_agent(project_id: str, request: ChatRequest):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    agent_id = project.get("agentId")
    if not agent_id:
        raise HTTPException(status_code=400, detail="Agent not created for this project. Call sync first.")

    if project.get("status") != "READY":
        raise HTTPException(status_code=400, detail=f"Project is not ready for chat (status: {project.get('status')}). Wait for ingestion to complete.")

    session_id = request.session_id or str(uuid.uuid4())
    try:
        response = invoke_agent(agent_id, AGENT_ALIAS_ID, session_id, f"[Assistant Mode] {request.message}")
        logger.info(f"[CHAT] {project_id}: session={session_id}")
        return {"projectId": project_id, "sessionId": session_id, "response": response}
    except Exception as e:
        logger.error(f"[CHAT] {project_id}: Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/{project_id}/sync")
def sync_project_route(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Recover KB if missing
    if not project.get("knowledgeBaseId"):
        try:
            kb_result = create_kb(project["projectName"], project_id, KNOWLEDGE_BASE_ROLE_ARN)
            update_project(project_id, {"knowledgeBaseId": kb_result["knowledgeBaseId"], "status": "KB_CREATED"})
            project["knowledgeBaseId"] = kb_result["knowledgeBaseId"]
        except Exception as e:
            logger.error(f"[SYNC] {project_id}: KB creation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"KB creation failed: {str(e)}")

    # Recover DS if missing
    if not project.get("dataSourceId"):
        try:
            ds_result = create_datasource(project["knowledgeBaseId"], project_id)
            update_project(project_id, {"dataSourceId": ds_result["dataSourceId"], "status": "DS_CREATED"})
            project["dataSourceId"] = ds_result["dataSourceId"]
        except Exception as e:
            logger.error(f"[SYNC] {project_id}: DS creation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Data source creation failed: {str(e)}")

    # Recover Agent if missing
    if not project.get("agentId"):
        try:
            agent_result = create_agent_draft(f"agent-{project_id}", AGENT_ROLE_ARN)
            update_project(project_id, {"agentId": agent_result["agentId"], "status": "AGENT_CREATED"})
            project["agentId"] = agent_result["agentId"]
        except Exception as e:
            logger.error(f"[SYNC] {project_id}: Agent creation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Agent creation failed: {str(e)}")

    try:
        result = sync_project_files(project)
        if STEP_FUNCTIONS_ARN and result.get("ingestionJobId"):
            sfn_client.start_execution(
                stateMachineArn=STEP_FUNCTIONS_ARN,
                input=json.dumps({"projectId": project_id})
            )
            logger.info(f"[SYNC] {project_id}: Step Functions polling started")
        return result
    except Exception as e:
        logger.error(f"[SYNC] {project_id}: Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
