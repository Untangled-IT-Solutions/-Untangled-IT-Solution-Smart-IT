from bson import ObjectId

from app.domain import now


async def _call(client, headers, method, path, role="Operations Manager", expected=200, **kwargs):
    response = await client.request(method, path, headers=headers[role], **kwargs)
    assert response.status_code == expected, response.text
    return response.json()


def _quote(reference="RFQ-INVOICE-1", status="awaiting_client_approval"):
    return {
        "_id": ObjectId(),
        "reference": reference,
        "customerName": "Customer Contact",
        "company": "Customer Company (Pty) Ltd",
        "email": "billing@example.co.za",
        "address": "1 Customer Road, Johannesburg, 2000",
        "status": status,
        "revision": 0,
        "quotation_snapshot": {
            "reference": reference,
            "currency": "ZAR",
            "vat_percent": "15",
            "subtotal_excl_vat": "1000.00",
            "vat_amount": "150.00",
            "total_incl_vat": "1150.00",
            "created_at": now(),
            "lines": [{
                "sku": "IT-1",
                "description": "Managed IT service",
                "quantity": "1",
                "unit_price_excl_vat": "1000.00",
                "line_total_excl_vat": "1000.00",
            }],
            "internal_pricing": [{"cost_unit_excl_vat": "800.00", "markup_percent": "25"}],
        },
    }


async def test_quote_approval_creates_one_public_invoice_snapshot(api):
    client, db, people, headers = api
    quote = _quote()
    await db.quotes.insert_one(quote)
    payload = {
        "approval_channel": "purchase_order",
        "approver_name": "Authorised Buyer",
        "approver_email": "buyer@example.co.za",
        "purchase_order_number": "PO-100",
        "idempotency_key": "approval-RFQ-INVOICE-1",
    }

    first = await _call(client, headers, "POST", "/api/quotes/RFQ-INVOICE-1/approve", json=payload)
    second = await _call(client, headers, "POST", "/api/quotes/RFQ-INVOICE-1/approve", json=payload)

    assert first["invoice"]["_id"] == second["invoice"]["_id"]
    assert second["idempotent"] is True
    assert await db.invoices.count_documents({"source_quote_id": quote["_id"]}) == 1
    assert first["quote"]["status"] == "awaiting_payment"
    assert first["invoice"]["status"] == "draft"
    assert first["invoice"]["purchase_order_number"] == "PO-100"
    assert "internal_pricing" not in first["invoice"]
    assert "cost_unit_excl_vat" not in first["invoice"]["lines"][0]

    replacement = {
        "lines": [{"description": "Changed after approval", "quantity": 1, "cost_unit_excl_vat": 1}],
    }
    await _call(
        client, headers, "PUT", "/api/quotes/RFQ-INVOICE-1/quotation",
        expected=409, json=replacement,
    )


async def test_invoice_issue_is_permissioned_numbered_and_idempotent(api):
    client, db, people, headers = api
    await db.quotes.insert_one(_quote("RFQ-INVOICE-2"))
    approved = await _call(
        client, headers, "POST", "/api/quotes/RFQ-INVOICE-2/approve",
        json={"approval_channel": "written_acceptance"},
    )
    invoice_id = approved["invoice"]["_id"]

    await _call(
        client, headers, "POST", f"/api/invoices/{invoice_id}/issue",
        role="Business Lead", expected=403, json={"payment_terms_days": 14},
    )
    issued = await _call(
        client, headers, "POST", f"/api/invoices/{invoice_id}/issue",
        role="Operations Manager", json={"payment_terms_days": 14},
    )
    repeated = await _call(
        client, headers, "POST", f"/api/invoices/{invoice_id}/issue",
        role="Director", json={"payment_terms_days": 30},
    )

    assert issued["invoice"]["status"] == "issued"
    assert issued["invoice"]["invoice_number"].startswith("INV-")
    assert issued["invoice"]["due_date"]
    assert repeated["idempotent"] is True
    assert repeated["invoice"]["invoice_number"] == issued["invoice"]["invoice_number"]
    stored_quote = await db.quotes.find_one({"reference": "RFQ-INVOICE-2"})
    assert stored_quote["invoice_number"] == issued["invoice"]["invoice_number"]


async def test_invoice_flow_rejects_unpriced_or_unauthorised_quotes(api):
    client, db, people, headers = api
    await db.quotes.insert_one({
        "_id": ObjectId(), "reference": "RFQ-NO-PRICE", "status": "awaiting_client_approval", "revision": 0,
    })
    await _call(
        client, headers, "POST", "/api/quotes/RFQ-NO-PRICE/approve",
        expected=409, json={"approval_channel": "written_acceptance"},
    )

    staff_quote = _quote("RFQ-STAFF-INVOICE")
    staff_quote["assigned_to"] = {
        "employee_id": people["Staff"]["employee"]["employee_id"],
    }
    await db.quotes.insert_one(staff_quote)
    await _call(
        client, headers, "POST", "/api/quotes/RFQ-STAFF-INVOICE/approve",
        role="Staff", expected=403, json={"approval_channel": "written_acceptance"},
    )
    await _call(
        client, headers, "POST", "/api/quotes/RFQ-STAFF-INVOICE/status",
        role="Staff", expected=409, json={"status": "awaiting_payment"},
    )


async def test_management_can_list_and_fetch_invoices(api):
    client, db, people, headers = api
    await db.quotes.insert_one(_quote("RFQ-INVOICE-LIST"))
    approved = await _call(
        client, headers, "POST", "/api/quotes/RFQ-INVOICE-LIST/approve",
        json={"approval_channel": "signed_quote"},
    )
    invoice_id = approved["invoice"]["_id"]

    await _call(client, headers, "GET", "/api/invoices", role="Staff", expected=403)
    listing = await _call(client, headers, "GET", "/api/invoices", role="Business Lead")
    fetched = await _call(client, headers, "GET", f"/api/invoices/{invoice_id}", role="Director")
    assert listing["count"] == 1
    assert fetched["invoice"]["source_quote_reference"] == "RFQ-INVOICE-LIST"
