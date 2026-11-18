from typing import Literal
from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, HttpUrl
from local_link_bot import analyze

router = APIRouter()


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    policy: Literal["ismar"]


@router.get("/status/")
@router.get("/status")
def status():
    return {"message": "pong"}


@router.get("/policies")
def policies():
    return [{"id": "ismar", "name": "Data Policy ISMAR v2.0"}]


@router.post("/local-link-bot", response_class=Response, responses={200: {"content": {"text/markdown": {"schema": {"type": "string"}}}}})
def local_link_bot(request: LinkRequest):
    return Response(analyze(str(request.url)), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="report.md"'})
