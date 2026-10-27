from __future__ import annotations

import sqlite3
from typing import Literal

from pydantic import BaseModel

from claimdesk.store.db import append_audit, set_job_status

CORE_WRITE_LIMIT = 5000


class ApprovalRequired(PermissionError):
    """High-impact action blocked until an approver records consent in audit."""


TicketStatus = Literal["pending", "approved", "rejected", "audited"]


class Ticket(BaseModel):
    id: str
    status: TicketStatus
    action: str
    recipient: str = ""
    body: str = ""
    reason: str = ""
    amount: int = 0
    claim_id: str = ""
    job_id: str | None = None


class ApprovalBook:
    def __init__(self) -> None:
        self.tickets: dict[str, Ticket] = {}
        self.audit: list[dict[str, str | int]] = []
        self.sent: list[str] = []
        self.core_writes: list[dict] = []
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"APR-{self._counter}"

    def _record_audit(
        self,
        *,
        action: str,
        amount: int,
        target: str,
        approver: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        row = {
            "action": action,
            "amount": amount,
            "target": target,
            "approver": approver,
        }
        self.audit.append(row)
        if conn is not None:
            append_audit(
                conn,
                action=action,
                amount=amount,
                target=target,
                approver=approver,
            )

    def save_draft(
        self,
        *,
        body: str,
        claim_id: str,
        actor_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> Ticket:
        ticket_id = self._next_id()
        ticket = Ticket(
            id=ticket_id,
            status="audited",
            action="save_draft",
            body=body,
            claim_id=claim_id,
        )
        self.tickets[ticket_id] = ticket
        self._record_audit(
            action="save_draft",
            amount=0,
            target=claim_id,
            approver=actor_id,
            conn=conn,
        )
        return ticket

    def propose_sms(
        self,
        *,
        recipient: str,
        body: str,
        reason: str,
        amount: int,
        claim_id: str,
        job_id: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> Ticket:
        ticket_id = self._next_id()
        ticket = Ticket(
            id=ticket_id,
            status="pending",
            action="send_sms",
            recipient=recipient,
            body=body,
            reason=reason,
            amount=amount,
            claim_id=claim_id,
            job_id=job_id,
        )
        self.tickets[ticket_id] = ticket
        self._record_audit(
            action="send_sms",
            amount=amount,
            target=recipient,
            approver="",
            conn=conn,
        )
        if conn is not None and job_id:
            set_job_status(conn, job_id, "blocked")
        return ticket

    def send_sms(
        self,
        ticket_id: str | None,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        del conn
        if ticket_id is None or ticket_id not in self.tickets:
            raise ApprovalRequired("缺少已批准的短信审批单")
        ticket = self.tickets[ticket_id]
        if ticket.action != "send_sms":
            raise ApprovalRequired("审批单动作不是 send_sms")
        if ticket.status != "approved":
            raise ApprovalRequired("短信尚未批准，不能发送")
        if ticket.body not in self.sent:
            self.sent.append(ticket.body)
        return ticket.body

    def reject(self, ticket_id: str) -> Ticket:
        ticket = self.tickets[ticket_id]
        ticket.status = "rejected"
        self.tickets[ticket_id] = ticket
        return ticket

    def edit(self, ticket_id: str, body: str) -> Ticket:
        ticket = self.tickets[ticket_id]
        if ticket.status != "pending":
            raise ValueError("只有 pending 状态的审批单可以修改正文")
        ticket.body = body
        self.tickets[ticket_id] = ticket
        return ticket

    def approve(
        self,
        ticket_id: str,
        approver_id: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> Ticket:
        ticket = self.tickets[ticket_id]
        if ticket.status != "pending":
            raise ValueError("只有 pending 状态的审批单可以批准")
        ticket.status = "approved"
        self.tickets[ticket_id] = ticket
        self._record_audit(
            action=ticket.action,
            amount=ticket.amount,
            target=ticket.recipient or ticket.claim_id,
            approver=approver_id,
            conn=conn,
        )
        if ticket.action == "send_sms" and ticket.body not in self.sent:
            self.sent.append(ticket.body)
        if conn is not None and ticket.job_id:
            set_job_status(conn, ticket.job_id, "accepted")
        return ticket

    def finalize(
        self,
        claim_id: str,
        amount: int,
        *,
        job_id: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> Ticket:
        if amount > CORE_WRITE_LIMIT:
            ticket_id = self._next_id()
            ticket = Ticket(
                id=ticket_id,
                status="pending",
                action="write_core",
                amount=amount,
                claim_id=claim_id,
                job_id=job_id,
            )
            self.tickets[ticket_id] = ticket
            self._record_audit(
                action="write_core",
                amount=amount,
                target=claim_id,
                approver="",
                conn=conn,
            )
            if conn is not None and job_id:
                set_job_status(conn, job_id, "blocked")
            return ticket

        payload = {"claim_id": claim_id, "amount": amount}
        self.core_writes.append(payload)
        ticket_id = self._next_id()
        ticket = Ticket(
            id=ticket_id,
            status="audited",
            action="write_core",
            amount=amount,
            claim_id=claim_id,
        )
        self.tickets[ticket_id] = ticket
        self._record_audit(
            action="write_core",
            amount=amount,
            target=claim_id,
            approver="system",
            conn=conn,
        )
        return ticket


def approval_view(ticket: Ticket) -> dict:
    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "action": ticket.action,
        "recipient": ticket.recipient,
        "body": ticket.body,
        "reason": ticket.reason,
        "amount": ticket.amount,
        "claim_id": ticket.claim_id,
    }
