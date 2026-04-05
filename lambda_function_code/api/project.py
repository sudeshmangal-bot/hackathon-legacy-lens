from pydantic import BaseModel
from typing import List, Optional


class CreateProjectRequest(BaseModel):
    project_name: str
    analysis_goal: Optional[str] = None
    file_names: Optional[List[str]] = []


class FileRequest(BaseModel):
    filename: str
    content_type: str


class PresignedUrlRequest(BaseModel):
    files: List[FileRequest]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
