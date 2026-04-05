import os
import logging

from services.s3_service import create_vector_bucket, create_vector_index, delete_vector_index, delete_vector_bucket, list_s3_files
from services.bedrock_service import (
    create_knowledge_base, create_data_source, delete_knowledge_base,
    start_ingestion_job, get_knowledge_base_status, get_data_source_status
)
from services.dynamodb_service import update_project

logger = logging.getLogger(__name__)

S3_BUCKET = os.environ.get('S3_BUCKET', '')


def _safe_name(value: str):
    return value.lower().replace("_", "-")


def create_kb(project_name: str, project_id: str, role_arn: str):
    safe = _safe_name(project_id)
    vector_bucket_name = f"kb-vectors-{safe}"
    index_name = f"kb-index-{safe}"
    created = {"vector_bucket": False, "vector_index": False, "kb": False}
    kb_id = None

    try:
        bucket_arn = create_vector_bucket(vector_bucket_name)
        created["vector_bucket"] = True

        create_vector_index(vector_bucket_name, index_name)
        created["vector_index"] = True

        kb_response = create_knowledge_base(project_name, role_arn, bucket_arn, index_name)
        kb = kb_response['knowledgeBase']
        kb_id = kb['knowledgeBaseId']
        created["kb"] = True

        return {
            'knowledgeBaseId': kb_id,
            'knowledgeBaseArn': kb['knowledgeBaseArn'],
            'vectorBucketArn': bucket_arn,
            'indexName': index_name
        }
    except Exception as e:
        logger.error(f"[KB] Failed at {created}, role_arn={role_arn}: {e}", exc_info=True)
        if created["kb"] and kb_id:
            try: delete_knowledge_base(kb_id)
            except Exception as ex: logger.warning(f"[KB] Cleanup delete_knowledge_base failed: {ex}")
        if created["vector_index"]:
            try: delete_vector_index(vector_bucket_name, index_name)
            except Exception as ex: logger.warning(f"[KB] Cleanup delete_vector_index failed: {ex}")
        if created["vector_bucket"]:
            try: delete_vector_bucket(vector_bucket_name)
            except Exception as ex: logger.warning(f"[KB] Cleanup delete_vector_bucket failed: {ex}")
        raise


def create_datasource(kb_id: str, project_id: str):
    parts = f"{S3_BUCKET}/projects/{project_id}/raw_data".split('/', 1)
    bucket_arn = f"arn:aws:s3:::{parts[0]}"
    prefix = parts[1] + '/' if len(parts) > 1 else None

    ds_response = create_data_source(kb_id, f"ds-{_safe_name(kb_id)}", bucket_arn, prefix)
    return {'dataSourceId': ds_response['dataSource']['dataSourceId']}


def sync_project_files(project: dict):
    project_id = project['projectId']
    kb_id = project['knowledgeBaseId']
    ds_id = project['dataSourceId']

    kb_status = get_knowledge_base_status(kb_id)
    if kb_status != 'ACTIVE':
        raise Exception(f"Knowledge base is not ready (status: {kb_status}). Try again later.")

    ds_status = get_data_source_status(kb_id, ds_id)
    if ds_status != 'AVAILABLE':
        raise Exception(f"Data source is not ready (status: {ds_status}). Try again later.")

    prefix = f"projects/{project_id}/raw_data/"
    current_files = list_s3_files(S3_BUCKET, prefix)
    ingested_files = project.get('ingestedFiles', [])

    if current_files == ingested_files:
        return {"message": "Already in sync", "projectId": project_id}

    response = start_ingestion_job(kb_id, ds_id)
    ingestion_job_id = response['ingestionJob']['ingestionJobId']

    update_project(project_id, {
        'status': 'INGESTION_STARTED',
        'ingestionJobId': ingestion_job_id,
        'ingestedFiles': current_files
    })

    logger.info(f"[SYNC] {project_id}: ingestion started, job={ingestion_job_id}, files={len(current_files)}")
    return {
        "message": "Ingestion started",
        "projectId": project_id,
        "ingestionJobId": ingestion_job_id,
        "filesChanged": len(current_files) != len(ingested_files)
    }
