"""Exact quotation pricing calculations shared by API routes and tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.domain import SAST, now


CENT = Decimal("0.01")


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def build_snapshot(reference: str, body, created_by: str) -> dict[str, Any]:
    """Create a deterministic quote snapshot while keeping supplier cost internal."""
    public_lines = []
    internal_lines = []
    subtotal = Decimal("0.00")
    for source in body.lines:
        quantity = Decimal(str(source.quantity))
        cost = money(source.cost_unit_excl_vat)
        markup = Decimal(str(source.markup_percent))
        unit_price = money(cost * (Decimal("1") + markup / Decimal("100")))
        line_total = money(unit_price * quantity)
        subtotal += line_total
        public = {
            "sku": source.sku.strip(),
            "description": source.description.strip(),
            "quantity": decimal_text(quantity),
            "unit_price_excl_vat": str(unit_price),
            "line_total_excl_vat": str(line_total),
            "specifications": [item.strip() for item in source.specifications if item.strip()][:20],
        }
        public_lines.append(public)
        internal_lines.append({
            **public,
            "cost_unit_excl_vat": str(cost),
            "markup_percent": decimal_text(markup),
        })

    delivery = money(body.delivery_fee_excl_vat)
    subtotal = money(subtotal + delivery)
    vat_percent = Decimal(str(body.vat_percent))
    vat_amount = money(subtotal * vat_percent / Decimal("100"))
    total = money(subtotal + vat_amount)
    issued = now().astimezone(SAST).date()
    return {
        "reference": reference,
        "issue_date": issued.isoformat(),
        "validity_days": body.validity_days,
        "valid_until": (issued + timedelta(days=body.validity_days)).isoformat(),
        "currency": "ZAR",
        "vat_percent": decimal_text(vat_percent),
        "subtotal_excl_vat": str(subtotal),
        "vat_amount": str(vat_amount),
        "total_incl_vat": str(total),
        "delivery_fee_excl_vat": str(delivery),
        "source_filename": body.source_filename.strip(),
        "supplier": body.supplier.strip(),
        "notes": body.notes.strip(),
        "lines": public_lines,
        "internal_pricing": internal_lines,
        "created_by": created_by,
        "created_at": now(),
    }

