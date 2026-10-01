"""Read priced lines from distributor Excel quotations.

The importer deliberately ignores formulas, macros and unpriced configuration
rows.  It returns plain data that can be reviewed and sent to the Nexus API.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any, Iterable


MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_ROWS = 10_000
MAX_LINES = 500
SHEET_BOUNDARY = "__NEXUS_SHEET_BOUNDARY__"


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


ALIASES = {
    "sku": {"partnumber", "itemnumber", "sku", "productcode", "stockcode"},
    "description": {"description", "productdescription", "itemdescription", "product"},
    "quantity": {"qty", "quantity", "units"},
    "unit_price": {
        "unitprice", "unitpriceexvat", "unitpriceexclvat", "discountedunitprice",
        "priceexvat", "priceexclvat", "sellprice",
    },
    "line_total": {
        "linetotal", "linetotalexcvat", "linetotalexvat", "subtotalexvat",
        "subtotalexclvat", "amount", "amountexvat",
    },
}


@dataclass(frozen=True)
class ImportedLine:
    sku: str
    description: str
    quantity: str
    cost_unit_excl_vat: str
    specifications: list[str]


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("R", "").replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _clean(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if text[:1] in {"=", "+", "-", "@"}:
        text = "'" + text
    return text[:limit]


def _rows_xlsx(path: Path) -> Iterable[list[Any]]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        for sheet in workbook.worksheets:
            yield [SHEET_BOUNDARY]
            for row in sheet.iter_rows(values_only=True):
                yield list(row)
    finally:
        workbook.close()


def _rows_xls(path: Path) -> Iterable[list[Any]]:
    import xlrd

    workbook = xlrd.open_workbook(str(path), on_demand=True)
    try:
        for sheet in workbook.sheets():
            yield [SHEET_BOUNDARY]
            for index in range(sheet.nrows):
                yield sheet.row_values(index)
    finally:
        workbook.release_resources()


def _find_header(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    best: tuple[int, dict[str, int]] | None = None
    for row_index, row in enumerate(rows[:100]):
        mapping: dict[str, int] = {}
        for column, value in enumerate(row):
            normalized = _key(value)
            for field, aliases in ALIASES.items():
                if normalized in aliases and field not in mapping:
                    mapping[field] = column
        score = len(mapping) + int("description" in mapping) + int("quantity" in mapping)
        if ("unit_price" in mapping or "line_total" in mapping) and score >= 4:
            if best is None or score > len(best[1]) + int("description" in best[1]) + int("quantity" in best[1]):
                best = (row_index, mapping)
    if best is None:
        raise ValueError(
            "Could not find pricing columns. Expected description, quantity and unit price or line total."
        )
    return best


def import_distributor_quote(filename: str) -> dict[str, Any]:
    """Return normalized, priced lines from an XLSX or legacy XLS quotation."""
    path = Path(filename).resolve()
    if not path.is_file():
        raise ValueError("The selected distributor quotation does not exist.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Distributor quotation is larger than 20 MB.")
    suffix = path.suffix.lower()
    if suffix not in {".xlsx", ".xls"}:
        raise ValueError("Choose an .xlsx or .xls distributor quotation.")

    source = _rows_xlsx(path) if suffix == ".xlsx" else _rows_xls(path)
    rows: list[list[Any]] = []
    for row in source:
        rows.append(row)
        if len(rows) > MAX_ROWS:
            raise ValueError("Distributor quotation has more than 10,000 rows.")

    header_index, columns = _find_header(rows)
    imported: list[ImportedLine] = []
    current_specs: list[str] | None = None
    for row in rows[header_index + 1 :]:
        if row and row[0] == SHEET_BOUNDARY:
            current_specs = None
            continue
        def cell(field: str):
            column = columns.get(field)
            return row[column] if column is not None and column < len(row) else None

        description = _clean(cell("description"))
        sku = _clean(cell("sku"), 120)
        quantity = _decimal(cell("quantity"))
        unit_price = _decimal(cell("unit_price"))
        line_total = _decimal(cell("line_total"))

        if quantity and quantity > 0 and unit_price is None and line_total is not None:
            unit_price = line_total / quantity
        if description and quantity and quantity > 0 and unit_price is not None and unit_price > 0:
            if len(imported) >= MAX_LINES:
                raise ValueError("Distributor quotation contains more than 500 priced lines.")
            current_specs = []
            imported.append(ImportedLine(
                sku=sku,
                description=description,
                quantity=_decimal_text(quantity),
                cost_unit_excl_vat=str(unit_price.quantize(Decimal("0.01"))),
                specifications=current_specs,
            ))
        elif imported and description and len(current_specs or []) < 20:
            detail = f"{sku}: {description}" if sku else description
            if detail not in current_specs:
                current_specs.append(detail)

    if not imported:
        raise ValueError("No priced product rows were found in the distributor quotation.")
    return {
        "source_filename": path.name,
        "supplier": path.stem[:160],
        "lines": [asdict(line) for line in imported],
        "priced_line_count": len(imported),
    }

