from typing import Annotated, Literal
from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, HttpUrl, StringConstraints
from local_link_bot import analyze
from alvise_graph import query_graph

router = APIRouter()


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    policy: Literal["ismar"]


class GraphQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


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


@router.post("/alvise-graph/query", response_class=Response, responses={200: {"content": {"text/markdown": {"schema": {"type": "string"}}}}})
def alvise_graph_query(request: GraphQuestion):
    return Response(query_graph(request.question), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="answer.md"'})
