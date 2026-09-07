from fastapi import FastAPI
from pydantic import BaseModel

from app.runner import Runner
from tools.registry import Toolbox
from tools.business_tools import build_toolbox
from app.config import settings

app = FastAPI(title="AI Automation Agent", version="1.0.0")
toolbox = Toolbox(build_toolbox())
runner = Runner(toolbox)


class MessageRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": settings.provider if settings.openai_api_key else "local",
        "tools": toolbox.names(),
    }


@app.get("/tools")
def tools():
    return {"tools": toolbox.names(), "schemas": toolbox.schemas()}


@app.post("/agent")
def agent(req: MessageRequest):
    return runner.run(req.message)


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    import json
    import os

    path = os.path.join(settings.runs_dir, f"{run_id}.json")
    if not os.path.exists(path):
        return {"error": "run not found"}
    return json.load(open(path))