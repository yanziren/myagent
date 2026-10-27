from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import HTMLResponse

from claimdesk.agent.desk import handle
from claimdesk.domain.models import DeskRequest, Suggestion
from claimdesk.domain.seed import World, default_world
from claimdesk.rules.eligibility import evaluate_eligibility
from claimdesk.store.db import connect, save_eligibility, save_intake
from claimdesk.workflow.intake import run_intake


class ActorRequest(BaseModel):
    actor_id: str


class InvestigationRequest(BaseModel):
    claim_id: str
    actor_id: str
    intent: str = "investigate"


class InvestigationAccepted(BaseModel):
    job_id: str


EligibilityRequest = ActorRequest
IntakeRequest = ActorRequest


class AppState:
    def __init__(self, world: World, conn: sqlite3.Connection) -> None:
        self.world = world
        self.conn = conn


_STATIC = Path(__file__).resolve().parent / "static"


def create_app(
    *,
    db_path: str,
    world: World | None = None,
    model=None,
) -> FastAPI:
    app = FastAPI(title="claimdesk", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    state = AppState(world=world or default_world(), conn=connect(db_path))

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html(request: Request) -> HTMLResponse:
        root_path = request.scope.get("root_path", "").rstrip("/")
        return get_swagger_ui_html(
            openapi_url=f"{root_path}{app.openapi_url}",
            title=f"{app.title} - Swagger UI",
            swagger_js_url=f"{root_path}/static/swagger-ui/swagger-ui-bundle.js",
            swagger_css_url=f"{root_path}/static/swagger-ui/swagger-ui.css",
        )

    @app.post("/claims/{claim_id}/eligibility", response_model=Suggestion)
    def post_eligibility(claim_id: str, body: EligibilityRequest) -> Suggestion:
        try:
            claim = state.world.claim_of(claim_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="claim not found") from exc
        policy = state.world.policy_of(claim_id)
        suggestion = evaluate_eligibility(
            claim,
            policy,
            state.world.active_waiting_days(),
        )
        save_eligibility(
            state.conn,
            claim_id=claim_id,
            actor_id=body.actor_id,
            suggestion=suggestion,
        )
        return suggestion

    @app.post("/claims/{claim_id}/intake", response_model=Suggestion)
    def post_intake(claim_id: str, body: IntakeRequest) -> Suggestion:
        try:
            state.world.claim_of(claim_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="claim not found") from exc
        suggestion = run_intake(state.world, claim_id)
        save_intake(
            state.conn,
            claim_id=claim_id,
            actor_id=body.actor_id,
            suggestion=suggestion,
        )
        return suggestion

    @app.post("/investigations", response_model=InvestigationAccepted)
    def post_investigation(body: InvestigationRequest) -> InvestigationAccepted:
        try:
            state.world.claim_of(body.claim_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="claim not found") from exc
        result = handle(
            state.world,
            DeskRequest(
                claim_id=body.claim_id,
                intent=body.intent,
                actor_id=body.actor_id,
            ),
            model,
            conn=state.conn,
        )
        if result.job_id is None:
            raise HTTPException(status_code=400, detail="not an investigation")
        return InvestigationAccepted(job_id=result.job_id)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        row = state.conn.execute(
            "SELECT id, status FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {"job_id": row["id"], "status": row["status"], "progress": row["status"]}

    return app


def _runtime_app() -> FastAPI:
    import os

    root = Path(__file__).resolve().parents[2]
    db_path = Path(os.environ.get("CLAIMDESK_DB", root / "data" / "claims.sqlite"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_app(db_path=str(db_path))


app = _runtime_app()
