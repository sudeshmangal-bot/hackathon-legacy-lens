import re
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
analysis_table = dynamodb.Table('ProjectAnalysis')


def _parse_analysis(raw: str) -> dict:
    sections = {
        "summary": "",
        "keyFindings": "",
        "missingInformation": "",
        "bottlenecksOrIssues": "",
        "recommendations": ""
    }
    patterns = {
        "summary": r"##\s*Summary\s*(.*?)(?=##|$)",
        "keyFindings": r"##\s*Key Findings\s*(.*?)(?=##|$)",
        "missingInformation": r"##\s*Missing Information\s*(.*?)(?=##|$)",
        "bottlenecksOrIssues": r"##\s*Bottlenecks or Issues\s*(.*?)(?=##|$)",
        "recommendations": r"##\s*Recommendations\s*(.*?)(?=##|$)"
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        if match:
            sections[key] = match.group(1).strip()
    return sections


def save_analysis(project_id: str, raw_response: str, session_id: str):
    parsed = _parse_analysis(raw_response)
    item = {
        'projectId': project_id,
        'sessionId': session_id,
        'summary': parsed['summary'],
        'keyFindings': parsed['keyFindings'],
        'missingInformation': parsed['missingInformation'],
        'bottlenecksOrIssues': parsed['bottlenecksOrIssues'],
        'recommendations': parsed['recommendations'],
        'createdAt': datetime.now(timezone.utc).isoformat()
    }
    analysis_table.put_item(Item=item)
    return item


def get_analysis(project_id: str):
    response = analysis_table.get_item(Key={'projectId': project_id})
    return response.get('Item')
