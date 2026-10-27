from __future__ import annotations

from claimdesk.guards.approval import ApprovalBook, approval_view


def post_json(path: str, body: dict, book: ApprovalBook) -> dict:
    if path != "/approvals":
        raise ValueError(f"unknown path: {path}")
    ticket_id = str(body.get("ticket_id", "")).strip()
    if not ticket_id or ticket_id not in book.tickets:
        return {"error": "ticket not found", "ticket_id": ticket_id}
    return approval_view(book.tickets[ticket_id])
