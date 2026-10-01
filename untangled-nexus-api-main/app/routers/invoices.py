"""Controlled quote approval and invoice lifecycle operations."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.domain import MANAGEMENT, SAST, audit, change, name, now, require_roles
from app.security import require_session, safe_object_id, serialize_id


router = APIRouter(tags=["invoices"])
INVOICE_ISSUERS = {"Director", "Operations Manager", "Super Admin"}
APPROVAL_CHANNELS = {"website", "signed_quote", "purchase_order", "written_acceptance"}


class QuoteApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_channel: str = Field(default="written_acceptance", max_length=40)
    approver_name: str = Field(default="", max_length=160)
    approver_email: str = Field(default="", max_length=254)
    purchase_order_number: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(default="", max_length=160)


class InvoiceIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_terms_days: int = Field(default=14, ge=0, le=180)
    purchase_order_number: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=1000)


def _reference_filter(reference: str) -> dict[str, Any]:
    value = str(reference or "").strip()
    if not value:
        raise HTTPException(422, "Reference is required.")
    return {"reference": {"$regex": "^" + re.escape(value) + "$", "$options": "i"}}


def _invoice_filter(invoice_id: str) -> dict[str, Any]:
    value = str(invoice_id or "").strip()
    if not value:
        raise HTTPException(422, "Invoice ID is required.")
    object_id = safe_object_id(value)
    return {"_id": {"$in": [value, object_id] if object_id else [value]}}


def _customer_snapshot(quote: dict[str, Any]) -> dict[str, str]:
    return {
        "name": str(quote.get("customerName") or quote.get("customer_name") or "").strip(),
        "company": str(quote.get("company") or quote.get("companyName") or "").strip(),
        "email": str(quote.get("email") or "").strip(),
        "phone": str(quote.get("phone") or quote.get("mobile") or "").strip(),
        "address": str(quote.get("billing_address") or quote.get("address") or quote.get("delivery_address") or "").strip(),
        "vat_number": str(quote.get("customer_vat_number") or quote.get("vat_number") or "").strip(),
    }


def _invoice_document(quote: dict[str, Any], ctx: dict, invoice_id: ObjectId) -> dict[str, Any]:
    snapshot = quote["quotation_snapshot"]
    approval = quote.get("approval") or {}
    timestamp = now()
    return {
        "_id": invoice_id,
        "source_quote_id": quote["_id"],
        "source_quote_reference": str(quote.get("reference") or ""),
        "source_quote_revision": quote.get("revision"),
        "source_quotation_created_at": snapshot.get("created_at"),
        "status": "draft",
        "currency": snapshot.get("currency") or "ZAR",
        "customer": _customer_snapshot(quote),
        "lines": list(snapshot.get("lines") or []),
        "subtotal_excl_vat": snapshot.get("subtotal_excl_vat") or "0.00",
        "vat_percent": snapshot.get("vat_percent") or "15",
        "vat_amount": snapshot.get("vat_amount") or "0.00",
        "total_incl_vat": snapshot.get("total_incl_vat") or "0.00",
        "approval": approval,
        "purchase_order_number": approval.get("purchase_order_number") or "",
        "created_by": name(ctx["employee"]),
        "created_by_employee_id": ctx["employee"]["_id"],
        "created_at": timestamp,
        "updated_at": timestamp,
        "revision": 0,
        "history": [audit(ctx, "invoice_draft_created", str(quote.get("reference") or ""))],
    }


async def _ensure_invoice(ctx: dict, quote: dict) -> dict[str, Any]:
    invoice_id = quote.get("invoice_id")
    if not invoice_id:
        raise HTTPException(409, "The accepted quote is missing its invoice link.")
    object_id = safe_object_id(invoice_id) or invoice_id
    document = _invoice_document(quote, ctx, object_id)
    try:
        await ctx["db"]["invoices"].update_one(
            {"_id": object_id}, {"$setOnInsert": document}, upsert=True,
        )
    except DuplicateKeyError:
        pass
    invoice = await ctx["db"]["invoices"].find_one({"source_quote_id": quote["_id"]})
    if not invoice:
        raise HTTPException(503, "Invoice creation could not be completed. Retry approval.")
    return invoice


@router.post("/api/quotes/{reference}/approve")
async def approve_quote(reference: str, body: QuoteApproval, ctx: dict = Depends(require_session)):
    """Lock the current quotation revision and create one recoverable invoice draft."""
    require_roles(ctx, MANAGEMENT)
    channel = body.approval_channel.strip().lower().replace(" ", "_")
    if channel not in APPROVAL_CHANNELS:
        raise HTTPException(422, "Unsupported approval channel.")

    quote = await ctx["db"]["quotes"].find_one(_reference_filter(reference))
    if not quote:
        raise HTTPException(404, "Quote not found.")
    if not isinstance(quote.get("quotation_snapshot"), dict):
        raise HTTPException(409, "Prepare and save a quotation before recording approval.")

    if quote.get("invoice_id"):
        invoice = await _ensure_invoice(ctx, quote)
        return {"success": True, "idempotent": True, "quote": serialize_id(quote), "invoice": serialize_id(invoice)}

    if str(quote.get("status") or "").lower() not in {"quoted", "awaiting_client_approval", "awaiting_client"}:
        raise HTTPException(409, "This quote is not awaiting customer approval.")

    invoice_id = ObjectId()
    approval = {
        "channel": channel,
        "approver_name": body.approver_name.strip(),
        "approver_email": body.approver_email.strip().lower(),
        "purchase_order_number": body.purchase_order_number.strip(),
        "note": body.note.strip(),
        "idempotency_key": body.idempotency_key.strip(),
        "accepted_at": now(),
        "captured_by": name(ctx["employee"]),
        "captured_by_employee_id": ctx["employee"]["_id"],
    }
    try:
        quote = await change(
            ctx["db"]["quotes"], quote,
            {
                "status": "awaiting_payment",
                "approval": approval,
                "accepted_quotation_snapshot": quote["quotation_snapshot"],
                "invoice_id": invoice_id,
                "invoice_status": "draft",
                "updatedAt": now(),
            },
            audit(ctx, "customer_approval_recorded", channel),
        )
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        quote = await ctx["db"]["quotes"].find_one(_reference_filter(reference))
        if not quote or not quote.get("invoice_id"):
            raise

    invoice = await _ensure_invoice(ctx, quote)
    return {"success": True, "idempotent": False, "quote": serialize_id(quote), "invoice": serialize_id(invoice)}


@router.get("/api/invoices")
async def list_invoices(limit: int = Query(100, ge=1, le=200), ctx: dict = Depends(require_session)):
    require_roles(ctx, MANAGEMENT)
    rows = await ctx["db"]["invoices"].find({}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"success": True, "invoices": serialize_id(rows), "count": len(rows)}


@router.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, ctx: dict = Depends(require_session)):
    require_roles(ctx, MANAGEMENT)
    invoice = await ctx["db"]["invoices"].find_one(_invoice_filter(invoice_id))
    if not invoice:
        raise HTTPException(404, "Invoice not found.")
    return {"success": True, "invoice": serialize_id(invoice)}


@router.post("/api/invoices/{invoice_id}/issue")
async def issue_invoice(invoice_id: str, body: InvoiceIssue, ctx: dict = Depends(require_session)):
    """Issue a draft once; repeated requests return the existing issued invoice."""
    require_roles(ctx, INVOICE_ISSUERS)
    collection = ctx["db"]["invoices"]
    invoice = await collection.find_one(_invoice_filter(invoice_id))
    if not invoice:
        raise HTTPException(404, "Invoice not found.")
    if invoice.get("status") == "issued":
        return {"success": True, "idempotent": True, "invoice": serialize_id(invoice)}
    if invoice.get("status") != "draft":
        raise HTTPException(409, "Only a draft invoice can be issued.")
    customer = invoice.get("customer") or {}
    if not (customer.get("name") or customer.get("company")) or not customer.get("address"):
        raise HTTPException(409, "Customer billing name and address are required before issue.")
    if not invoice.get("lines"):
        raise HTTPException(409, "Invoice has no line items.")

    issued_on = now().astimezone(SAST).date()
    counter = await ctx["db"]["counters"].find_one_and_update(
        {"_id": f"invoice:{issued_on.year}"},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    invoice_number = f"INV-{issued_on.year}-{int(counter['value']):05d}"
    event = audit(ctx, "invoice_issued", body.note.strip())
    updated = await collection.find_one_and_update(
        {"_id": invoice["_id"], "status": "draft"},
        {
            "$set": {
                "status": "issued",
                "invoice_number": invoice_number,
                "issue_date": issued_on.isoformat(),
                "payment_terms_days": body.payment_terms_days,
                "due_date": (issued_on + timedelta(days=body.payment_terms_days)).isoformat(),
                "purchase_order_number": body.purchase_order_number.strip() or invoice.get("purchase_order_number") or "",
                "issued_by": name(ctx["employee"]),
                "issued_by_employee_id": ctx["employee"]["_id"],
                "issued_at": now(),
                "updated_at": now(),
            },
            "$inc": {"revision": 1},
            "$push": {"history": event},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        current = await collection.find_one({"_id": invoice["_id"]})
        if current and current.get("status") == "issued":
            return {"success": True, "idempotent": True, "invoice": serialize_id(current)}
        raise HTTPException(409, "Invoice changed; reload and retry.")

    await ctx["db"]["quotes"].update_one(
        {"_id": invoice["source_quote_id"]},
        {
            "$set": {
                "invoice_status": "issued",
                "invoice_number": invoice_number,
                "invoice_issue_date": issued_on.isoformat(),
                "invoice_due_date": updated["due_date"],
                "updatedAt": now(),
            },
            "$inc": {"revision": 1},
            "$push": {"history": audit(ctx, "linked_invoice_issued", invoice_number)},
        },
    )
    return {"success": True, "idempotent": False, "invoice": serialize_id(updated)}
