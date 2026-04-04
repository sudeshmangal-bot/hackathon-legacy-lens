import logging
from services.dynamodb_service import get_project, update_project
from services.bedrock_service import get_ingestion_job_status
from services.agent_service import associate_kb_to_agent

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "COMPLETE": "INGESTION_COMPLETE",
    "FAILED": "INGESTION_FAILED",
    "STOPPED": "INGESTION_FAILED"
}


def handler(event, context):
    project_id = event["projectId"]
    project = get_project(project_id)

    if not project:
        return {"projectId": project_id, "status": "NOT_FOUND", "done": True}

    current_status = project.get("status")
    if current_status not in ("INGESTION_STARTED",):
        return {"projectId": project_id, "status": current_status, "done": True}

    bedrock_status = get_ingestion_job_status(
        project["knowledgeBaseId"], project["dataSourceId"], project["ingestionJobId"]
    )
    logger.info(f"[POLLER] {project_id}: bedrock_status={bedrock_status}")

    new_status = STATUS_MAP.get(bedrock_status)

    if not new_status:
        # Still in progress
        return {"projectId": project_id, "status": "INGESTION_STARTED", "done": False}

    update_project(project_id, {"status": new_status})

    if bedrock_status == "COMPLETE" and project.get("agentId") and not project.get("kbAssociated"):
        try:
            associate_kb_to_agent(
                project["agentId"],
                project["knowledgeBaseId"],
                f"Knowledge base for {project['projectName']}"
            )
            update_project(project_id, {"kbAssociated": True, "status": "READY"})
            new_status = "READY"
            logger.info(f"[POLLER] {project_id}: KB associated, status=READY")
        except Exception as e:
            logger.error(f"[POLLER] {project_id}: KB association failed: {e}")
            update_project(project_id, {"status": "KB_ASSOCIATION_FAILED"})
            new_status = "KB_ASSOCIATION_FAILED"

    return {"projectId": project_id, "status": new_status, "done": True}
