"""Authenticated quote and order operations for the Nexus desktop client.

The public website continues to create commerce records through Node.  Nexus
reads and updates those same MongoDB collections only through this API.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.domain import (
    MANAGEMENT,
    OPERATIONS,
    audit,
    change,
    employee_by_reference,
    name,
    now,
    own,
    refs,
    require_roles,
    role,
)
from app.security import is_active, require_session, serialize_id
from app.quotation import build_snapshot

router = APIRouter(tags=["quotes"])

QUOTE_STATES = {
    "received", "pending", "assigned", "accepted", "in_progress", "in_review",
    "returned", "quoted", "completed", "cancelled", "awaiting_details",
    "awaiting_client_approval", "awaiting_client", "awaiting_payment", "paid",
    "out_for_delivery",
}
ORDER_STATES = {
    "pending", "confirmed", "processing", "in_progress", "ready", "shipped",
    "delivered", "completed", "cancelled",
}


class Assignment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    employee_id: Any = None
    employeeId: Any = None
    assigned_to: Any = None

    @property
    def target(self):
        if self.employee_id is not None:
            return self.employee_id
        if self.employeeId is not None:
            return self.employeeId
        return self.assigned_to


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str = Field(min_length=1, max_length=80)


class QuoteReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    replyMessage: str = Field(min_length=1, max_length=20000)


class DirectorReview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    general_reply: str = Field(default="", max_length=20000)
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class QuotationLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(default="", max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    quantity: Decimal = Field(gt=0, le=100000)
    cost_unit_excl_vat: Decimal = Field(ge=0, le=100000000)
    markup_percent: Decimal = Field(default=Decimal("25"), ge=0, le=500)
    specifications: list[str] = Field(default_factory=list, max_length=20)


class QuotationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[QuotationLine] = Field(min_length=1, max_length=500)
    validity_days: int = Field(default=14, ge=1, le=90)
    vat_percent: Decimal = Field(default=Decimal("15"), ge=0, le=30)
    delivery_fee_excl_vat: Decimal = Field(default=Decimal("0"), ge=0, le=100000000)
    source_filename: str = Field(default="", max_length=255)
    supplier: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=2000)


def scope(ctx):
    if role(ctx) in MANAGEMENT:
        return {}
    values = refs(ctx["employee"])
    return {
        "$or": [
            {key: {"$in": values}}
            for key in (
                "assigned_to", "assignedTo", "assigned_to.employee_id",
                "assigned_to.id", "assigned_employee_id", "assignee_id",
            )
        ]
    }


def assigned(ctx, record):
    candidate = record.get("assigned_to") or record.get("assignedTo")
    if isinstance(candidate, dict):
        return any(
            own(ctx, candidate.get(key))
            for key in ("employee_id", "id", "_id")
        )
    return any(
        own(ctx, record.get(key))
        for key in ("assigned_to", "assignedTo", "assigned_employee_id", "assignee_id")
    )


def reference_filter(reference):
    value = str(reference or "").strip()
    if not value:
        raise HTTPException(422, "Reference is required.")
    return {"reference": {"$regex": "^" + re.escape(value) + "$", "$options": "i"}}


async def load_record(ctx, collection, reference, *, require_access=True):
    record = await ctx["db"][collection].find_one(reference_filter(reference))
    if not record:
        raise HTTPException(404, f"{collection[:-1].title()} not found.")
    if require_access and role(ctx) not in MANAGEMENT and not assigned(ctx, record):
        raise HTTPException(403, f"This {collection[:-1]} is not assigned to you.")
    return record


def assignment_payload(employee):
    if not employee:
        return None
    return {
        "id": str(employee["_id"]),
        "employee_id": employee.get("employee_id") or str(employee["_id"]),
        "name": name(employee),
        "full_name": name(employee),
        "email": employee.get("email") or employee.get("email_address") or "",
    }


async def listing(ctx, collection, limit):
    rows = await ctx["db"][collection].find(scope(ctx)).sort("createdAt", -1).limit(limit).to_list(limit)
    return {"success": True, collection: serialize_id(rows), "count": len(rows)}


@router.get("/api/quotes")
async def list_quotes(limit: int = Query(50, ge=1, le=200), ctx: dict = Depends(require_session)):
    return await listing(ctx, "quotes", limit)


@router.get("/api/orders")
async def list_orders(limit: int = Query(50, ge=1, le=200), ctx: dict = Depends(require_session)):
    return await listing(ctx, "orders", limit)


async def track(ctx, collection, reference, email):
    if not reference or not email:
        raise HTTPException(422, "reference and email are required.")
    query = {
        "$and": [
            scope(ctx),
            reference_filter(reference),
            {"email": {"$regex": "^" + re.escape(email.strip()) + "$", "$options": "i"}},
        ]
    }
    row = await ctx["db"][collection].find_one(query)
    if not row:
        raise HTTPException(404, "Record not found.")
    return {"success": True, collection[:-1]: serialize_id(row)}


@router.get("/api/quotes/track")
async def track_quote(ref: str | None = None, reference: str | None = None, email: str | None = None, ctx: dict = Depends(require_session)):
    return await track(ctx, "quotes", ref or reference, email)


@router.get("/api/orders/track")
async def track_order(ref: str | None = None, reference: str | None = None, email: str | None = None, ctx: dict = Depends(require_session)):
    return await track(ctx, "orders", ref or reference, email)


async def assign_record(ctx, collection, reference, body):
    require_roles(ctx, OPERATIONS)
    record = await load_record(ctx, collection, reference, require_access=False)
    target = body.target
    employee = None
    if target is not None and str(target).strip().lower() not in {"", "none", "unassigned"}:
        employee = await employee_by_reference(ctx["db"], target)
        if not is_active(employee.get("status")):
            raise HTTPException(422, "Cannot assign an inactive employee.")
    assigned_to = assignment_payload(employee)
    updates = {
        "assigned_to": assigned_to,
        "assignedTo": assigned_to,
        "assigned_employee_id": employee["_id"] if employee else None,
        "status": "assigned" if employee else "pending",
        "updatedAt": now(),
    }
    updated = await change(
        ctx["db"][collection], record, updates,
        audit(ctx, "assigned" if employee else "unassigned", name(employee) if employee else ""),
    )
    return {"success": True, collection[:-1]: serialize_id(updated)}


@router.put("/api/admin/quotes/{reference}/assignment")
@router.post("/api/quotes/{reference}/assign")
async def assign_quote(reference: str, body: Assignment, ctx: dict = Depends(require_session)):
    return await assign_record(ctx, "quotes", reference, body)


@router.put("/api/admin/orders/{reference}/assignment")
@router.post("/api/orders/{reference}/assign")
async def assign_order(reference: str, body: Assignment, ctx: dict = Depends(require_session)):
    return await assign_record(ctx, "orders", reference, body)


async def update_status(ctx, collection, reference, body):
    record = await load_record(ctx, collection, reference)
    status = body.status.strip().lower().replace(" ", "_")
    allowed = QUOTE_STATES if collection == "quotes" else ORDER_STATES
    if status not in allowed:
        raise HTTPException(422, "Unsupported status.")
    if collection == "quotes" and status == "awaiting_payment":
        raise HTTPException(409, "Use the customer approval action so Nexus creates the linked invoice draft.")
    if collection == "quotes" and status == "paid":
        require_roles(ctx, MANAGEMENT)
    updated = await change(
        ctx["db"][collection], record,
        {"status": status, "updatedAt": now()},
        audit(ctx, f"status_changed_to_{status}"),
    )
    return {"success": True, collection[:-1]: serialize_id(updated)}


@router.post("/api/admin/quotes/{reference}/status")
@router.put("/api/admin/quotes/{reference}/status")
@router.patch("/api/admin/quotes/{reference}/status")
@router.post("/api/quotes/{reference}/status")
@router.put("/api/quotes/{reference}/status")
@router.patch("/api/quotes/{reference}/status")
async def update_quote_status(reference: str, body: StatusUpdate, ctx: dict = Depends(require_session)):
    return await update_status(ctx, "quotes", reference, body)


@router.put("/api/quotes/{reference}/quotation")
async def save_quotation(reference: str, body: QuotationDraft, ctx: dict = Depends(require_session)):
    """Save an auditable quotation revision using server-calculated totals."""
    require_roles(ctx, MANAGEMENT)
    record = await load_record(ctx, "quotes", reference, require_access=False)
    if record.get("invoice_id") or record.get("accepted_quotation_snapshot"):
        raise HTTPException(409, "This quotation revision is locked because the customer approved it.")
    snapshot = build_snapshot(reference, body, name(ctx["employee"]))
    history = list(record.get("quotation_history") or [])
    previous = record.get("quotation_snapshot")
    if isinstance(previous, dict):
        history.append(previous)
    history = history[-20:]
    public_lines = [
        {
            "sku": line["sku"],
            "description": line["description"],
            "quantity": line["quantity"],
            "unit_price_excl_vat": line["unit_price_excl_vat"],
            "amount": line["line_total_excl_vat"],
        }
        for line in snapshot["lines"]
    ]
    updated = await change(
        ctx["db"]["quotes"], record,
        {
            "quotation_snapshot": snapshot,
            "quotation_history": history,
            "quotation": public_lines,
            "quotation_subtotal": snapshot["subtotal_excl_vat"],
            "quotation_vat": snapshot["vat_amount"],
            "quotation_total": snapshot["total_incl_vat"],
            "paymentAmount": float(snapshot["total_incl_vat"]),
            "paymentRequired": True,
            "quote_valid_until": snapshot["valid_until"],
            "status": "quoted",
            "updatedAt": now(),
        },
        audit(ctx, "quotation_saved", f"{len(snapshot['lines'])} priced line(s)"),
    )
    return {"success": True, "quote": serialize_id(updated)}


class OrderStatusUpdate(StatusUpdate):
    reference: str = Field(min_length=1, max_length=200)


@router.patch("/api/orders/status")
async def update_order_status_by_body(body: OrderStatusUpdate, ctx: dict = Depends(require_session)):
    return await update_status(ctx, "orders", body.reference, body)


@router.patch("/api/orders/{reference}/status")
async def update_order_status(reference: str, body: StatusUpdate, ctx: dict = Depends(require_session)):
    return await update_status(ctx, "orders", reference, body)


@router.put("/api/admin/quotes/{reference}")
async def reply_to_quote(reference: str, body: QuoteReply, ctx: dict = Depends(require_session)):
    record = await load_record(ctx, "quotes", reference)
    updated = await change(
        ctx["db"]["quotes"], record,
        {"replyMessage": body.replyMessage.strip(), "repliedAt": now(), "replied_by": name(ctx["employee"]), "updatedAt": now()},
        audit(ctx, "reply_sent"),
    )
    return {"success": True, "quote": serialize_id(updated)}


def pending_review(record, ctx):
    return {
        "status": "pending",
        "requested_at": now(),
        "requested_by": {"username": ctx["user"].get("username"), "full_name": name(ctx["employee"])},
        "reviewed_at": None,
        "director": None,
        "general_reply": "",
        "items": [
            {
                "item_id": str(item.get("id") or item.get("_id") or ""),
                "item_name": item.get("name") or "Item",
                "qty_requested": item.get("qty", 1),
                "availability": "",
                "comment": "",
            }
            for item in (record.get("items") or []) if isinstance(item, dict)
        ],
    }


@router.post("/api/admin/quotes/{reference}/director-review/request")
@router.post("/api/quotes/{reference}/director-review")
async def request_director_review(reference: str, ctx: dict = Depends(require_session)):
    record = await load_record(ctx, "quotes", reference)
    review = pending_review(record, ctx)
    updates = {"director_review": review, "status": "in_review", "updatedAt": now()}
    previous = record.get("director_review")
    if isinstance(previous, dict) and previous.get("status") == "reviewed":
        updates["director_review_history"] = [*(record.get("director_review_history") or []), previous]
    updated = await change(ctx["db"]["quotes"], record, updates, audit(ctx, "sent_to_director"))
    return {"success": True, "quote": serialize_id(updated)}


@router.get("/api/quotes/{reference}/director-review")
async def get_director_review(reference: str, ctx: dict = Depends(require_session)):
    record = await load_record(ctx, "quotes", reference)
    return {"success": True, "director_review": serialize_id(record.get("director_review") or {})}


@router.put("/api/admin/quotes/{reference}/director-review")
@router.post("/api/quotes/{reference}/director-review/submit")
async def submit_director_review(reference: str, body: DirectorReview, ctx: dict = Depends(require_session)):
    require_roles(ctx, {"Director", "Super Admin"})
    record = await load_record(ctx, "quotes", reference, require_access=False)
    existing = record.get("director_review") if isinstance(record.get("director_review"), dict) else {}
    if existing.get("status") != "pending":
        raise HTTPException(409, "This quote is not awaiting a director review.")
    review = {
        **existing,
        "status": "reviewed",
        "reviewed_at": now(),
        "director": {"username": ctx["user"].get("username"), "full_name": name(ctx["employee"])},
        "general_reply": body.general_reply.strip(),
        "items": body.items,
    }
    updated = await change(
        ctx["db"]["quotes"], record,
        {"director_review": review, "status": "assigned", "updatedAt": now()},
        audit(ctx, "director_review_submitted", body.general_reply[:120]),
    )
    return {"success": True, "quote": serialize_id(updated)}
