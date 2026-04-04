import uuid
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
projects_table = dynamodb.Table('Project')


def create_project(project_name: str, analysis_goal: str, file_names: list):
    project_id = f"proj_{uuid.uuid4().hex[:6]}"
    item = {
        'projectId': project_id,
        'projectName': project_name,
        'analysisGoal': analysis_goal,
        'fileNames': file_names,
        'status': 'CREATED',
        'knowledgeBaseId': None,
        'dataSourceId': None,
        'agentId': None,
        'ingestedFiles': [],
        'ingestionJobId': None,
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'isDeleted': False
    }
    projects_table.put_item(Item=item)
    return item


def get_all_projects():
    response = projects_table.scan()
    return response.get('Items', [])


def project_name_exists(project_name: str):
    response = projects_table.scan(
        FilterExpression='projectName = :name',
        ExpressionAttributeValues={':name': project_name}
    )
    return len(response.get('Items', [])) > 0


def get_project(project_id: str):
    response = projects_table.get_item(Key={'projectId': project_id})
    return response.get('Item')


def update_project(project_id: str, updates: dict):
    updates['updatedAt'] = datetime.now(timezone.utc).isoformat()
    expr_parts = []
    attr_values = {}
    attr_names = {}
    for i, (key, val) in enumerate(updates.items()):
        placeholder = f":v{i}"
        name_placeholder = f"#k{i}"
        expr_parts.append(f"{name_placeholder} = {placeholder}")
        attr_values[placeholder] = val
        attr_names[name_placeholder] = key
    projects_table.update_item(
        Key={'projectId': project_id},
        UpdateExpression='SET ' + ', '.join(expr_parts),
        ExpressionAttributeValues=attr_values,
        ExpressionAttributeNames=attr_names
    )
