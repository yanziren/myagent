from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import HTMLResponse

from auditdesk.evals.catalog import load_cases
from auditdesk.rules.review import Checklist, review_contract
from auditdesk.store.db import (
    connect,
    get_trace,
    list_actions,
    new_trace_id,
    record_action,
    save_trace,
)

_PAGE = Path(__file__).resolve().parent / "static" / "index.html"
_HIGH_IMPACT = {"issue_formal", "override_decision", "send_counterparty"}
_DRAFT = {"draft_note"}
_SAMPLES = {
    "G01": "一份可以通过的",
    "G15": "缺签署",
    "G26": "金额要复核",
}


class ReviewIn(BaseModel):
    contract_text: str
    actor_id: str
    checklist_name: str = "服务合同"
    amount_review_from: int = 50_000


class ActionIn(BaseModel):
    action: str
    actor_id: str
    approver_id: str = ""


class AppState:
    def __init__(self, db_path: str) -> None:
        self.conn = connect(db_path)


def create_app(*, db_path: str) -> FastAPI:
    app = FastAPI(title="合同审核台")
    state = AppState(db_path)

    @app.get("/", response_class=HTMLResponse)
    def desk() -> str:
        return _PAGE.read_text(encoding="utf-8")

    @app.get("/samples")
    def samples() -> list[dict]:
        by_id = {case["id"]: case for case in load_cases()}
        return [
            {"id": case_id, "title": title, "text": by_id[case_id]["text"]}
            for case_id, title in _SAMPLES.items()
        ]

    @app.post("/reviews")
    def post_review(body: ReviewIn) -> dict:
        text = body.contract_text
        if not text.strip():
            raise HTTPException(status_code=400, detail="合同正文是空的")
        if not body.actor_id.strip():
            raise HTTPException(status_code=400, detail="要写下审核人")
        result = review_contract(
            text,
            checklist=Checklist(
                name=body.checklist_name,
                amount_review_from=body.amount_review_from,
            ),
        )
        trace_id = new_trace_id()
        payload = result.model_dump()
        save_trace(
            state.conn,
            trace_id=trace_id,
            actor_id=body.actor_id.strip(),
            contract_text=text,
            decision=result.decision,
            payload=payload,
        )
        return {"trace_id": trace_id, **payload}

    @app.get("/traces/{trace_id}")
    def replay(trace_id: str) -> dict:
        row = get_trace(state.conn, trace_id)
        if row is None:
            raise HTTPException(status_code=404, detail="找不到这条记录")
        payload = json.loads(row["payload"])
        return {
            "trace_id": row["trace_id"],
            "actor_id": row["actor_id"],
            "contract_text": row["contract_text"],
            "created_at": row["created_at"],
            "actions": list_actions(state.conn, trace_id),
            **payload,
        }

    @app.post("/traces/{trace_id}/actions")
    def post_action(trace_id: str, body: ActionIn) -> dict:
        row = get_trace(state.conn, trace_id)
        if row is None:
            raise HTTPException(status_code=404, detail="找不到这条记录")
        action = body.action
        if action not in _HIGH_IMPACT and action not in _DRAFT:
            raise HTTPException(status_code=400, detail="不认识这个动作")
        approver = body.approver_id.strip()
        actor = body.actor_id.strip()
        if action in _HIGH_IMPACT and (not approver or approver == actor):
            raise HTTPException(status_code=403, detail="这个动作要另一个人点头")
        record_action(
            state.conn,
            trace_id=trace_id,
            action=action,
            actor_id=actor,
            approver_id=approver,
            status="recorded",
        )
        return {"trace_id": trace_id, "action": action, "status": "recorded"}

    return app
