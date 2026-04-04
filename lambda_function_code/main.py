import logging
from fastapi import FastAPI
from mangum import Mangum

logging.basicConfig(level=logging.INFO)

from api.routes.project import router as project_router
from poller_handler import handler as poller_handler
from analysis_handler import handler as analysis_handler

app = FastAPI(redirect_slashes=False)

@app.get("/")
def health_check():
    return {"message": "API is running"}

app.include_router(project_router, prefix="/api/project")

_mangum_handler = Mangum(app)
_logger = logging.getLogger(__name__)

def handler(event, context):
    if event.get("task") == "analysis":
        _logger.info(f"[ANALYSIS] Step Functions analysis event received: {event}")
        return analysis_handler(event, context)
    if "projectId" in event:
        _logger.info(f"[POLLER] Step Functions event received: {event}")
        return poller_handler(event, context)
    return _mangum_handler(event, context)
