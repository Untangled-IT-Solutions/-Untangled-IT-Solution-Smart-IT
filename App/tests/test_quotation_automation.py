from decimal import Decimal

from openpyxl import Workbook

from app.services.distributor_import import import_distributor_quote


def test_imports_priced_rows_and_attaches_unpriced_configuration(tmp_path):
    path = tmp_path / "supplier.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Supplier quotation"])
    sheet.append(["Part Number", "Description", "QTY", "Unit Price Ex-VAT", "Sub-Total Ex-VAT"])
    sheet.append(["PC-1", "Business laptop", 2, 10000, 20000])
    sheet.append(["RAM-16", "16 GB memory", 1, None, None])
    sheet.append(["SSD-512", "512 GB SSD", 1, None, None])
    workbook.save(path)

    result = import_distributor_quote(str(path))

    assert result["priced_line_count"] == 1
    line = result["lines"][0]
    assert line["sku"] == "PC-1"
    assert Decimal(line["cost_unit_excl_vat"]) == Decimal("10000.00")
    assert line["specifications"] == ["RAM-16: 16 GB memory", "SSD-512: 512 GB SSD"]


def test_import_can_infer_unit_price_from_line_total(tmp_path):
    path = tmp_path / "legacy-layout.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Item Number", "Description", "Quantity", "Line Total (Exc.VAT)"])
    sheet.append(["MON-1", "Monitor", 4, 9200])
    workbook.save(path)

    result = import_distributor_quote(str(path))

    assert Decimal(result["lines"][0]["cost_unit_excl_vat"]) == Decimal("2300.00")
