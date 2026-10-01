from conftest import PASSWORD


async def _call(client, headers, method, path, role="Operations Manager", expected=200, **kwargs):
    response = await client.request(method, path, headers=headers[role], **kwargs)
    assert response.status_code == expected, response.text
    return response.json()


async def test_quotation_uses_exact_markup_vat_and_revision_history(api):
    client, db, people, headers = api
    await db.quotes.insert_one({
        "reference": "RFQ-100",
        "customerName": "Example Client",
        "status": "assigned",
        "revision": None,
    })
    payload = {
        "source_filename": "supplier.xlsx",
        "supplier": "Example Distributor",
        "validity_days": 14,
        "vat_percent": "15",
        "lines": [{
            "sku": "PC-1",
            "description": "Business laptop",
            "quantity": "2",
            "cost_unit_excl_vat": "10000.00",
            "markup_percent": "25",
            "specifications": ["16 GB RAM"],
        }],
    }

    result = await _call(client, headers, "PUT", "/api/quotes/RFQ-100/quotation", json=payload)
    snapshot = result["quote"]["quotation_snapshot"]
    assert snapshot["subtotal_excl_vat"] == "25000.00"
    assert snapshot["vat_amount"] == "3750.00"
    assert snapshot["total_incl_vat"] == "28750.00"
    assert snapshot["lines"][0]["unit_price_excl_vat"] == "12500.00"
    assert snapshot["validity_days"] == 14
    assert result["quote"]["status"] == "quoted"

    payload["lines"][0]["cost_unit_excl_vat"] = "12000.00"
    second = await _call(client, headers, "PUT", "/api/quotes/RFQ-100/quotation", json=payload)
    assert len(second["quote"]["quotation_history"]) == 1
    assert second["quote"]["quotation_history"][0]["total_incl_vat"] == "28750.00"


async def test_only_management_can_save_supplier_pricing(api):
    client, db, people, headers = api
    await db.quotes.insert_one({
        "reference": "RFQ-STAFF",
        "status": "assigned",
        "assigned_to": {"employee_id": people["Staff"]["employee"]["employee_id"]},
        "revision": None,
    })
    payload = {"lines": [{"description": "Item", "quantity": 1, "cost_unit_excl_vat": 100}]}
    await _call(client, headers, "PUT", "/api/quotes/RFQ-STAFF/quotation", role="Staff", expected=403, json=payload)


async def test_quote_status_api_accepts_desktop_workflow_states(api):
    client, db, people, headers = api
    await db.quotes.insert_one({
        "reference": "RFQ-STATUS",
        "status": "assigned",
        "assigned_to": {"employee_id": people["Staff"]["employee"]["employee_id"]},
        "revision": None,
    })
    result = await _call(
        client, headers, "POST", "/api/quotes/RFQ-STATUS/status",
        role="Staff", json={"status": "awaiting_details"},
    )
    assert result["quote"]["status"] == "awaiting_details"
