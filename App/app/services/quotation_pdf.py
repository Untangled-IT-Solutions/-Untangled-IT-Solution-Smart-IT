"""Branded Untangled IT Solutions quotation PDF generation."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
import re
from typing import Any


COMPANY = {
    "name": "Untangled IT Solutions (Pty) Ltd",
    "registration": "2016/086055/07",
    "vat": "4110280148",
    "csd": "MAAA0584495",
    "address": "9611 Gosiame Street, Ivory Park Section 9, Midrand, Gauteng, 1685",
    "phone": "010 746 2471",
    "email": "accounts@untangledits.co.za",
}
TERMS_URL = "https://untangled.co.za/?page=terms-and-conditions"


def _money(value: Any) -> str:
    try:
        return f"R {Decimal(str(value or 0)):,.2f}"
    except (InvalidOperation, ValueError):
        return "R 0.00"


def _logo_path() -> Path | None:
    from app.utils.config import PROJECT_ROOT

    candidates = (
        PROJECT_ROOT / "app" / "assets" / "Branding" / "logo" / "logo_full.png",
        PROJECT_ROOT / "assets" / "Branding" / "logo" / "logo_full.png",
        PROJECT_ROOT / "app" / "assets" / "logo" / "mainlogo.png",
    )
    return next((path for path in candidates if path.is_file()), None)


def _customer(quote: dict[str, Any]) -> dict[str, str]:
    return {
        "name": str(quote.get("customerName") or quote.get("customer_name") or "Client"),
        "company": str(quote.get("company") or quote.get("companyName") or ""),
        "email": str(quote.get("email") or ""),
        "phone": str(quote.get("phone") or quote.get("mobile") or ""),
        "address": str(quote.get("address") or quote.get("delivery_address") or ""),
    }


def generate_quotation_pdf(quote: dict[str, Any], filename: str) -> str:
    """Generate a customer-facing PDF. Internal supplier cost and markup are omitted."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    target = Path(filename).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = quote.get("quotation_snapshot") or {}
    lines = snapshot.get("lines") or quote.get("quotation") or []
    if not lines:
        raise ValueError("This quote has no saved quotation lines.")

    reference = str(quote.get("reference") or snapshot.get("reference") or "DRAFT")
    reference_xml = escape(reference)
    safe_reference = re.sub(r"[^A-Za-z0-9._-]", "-", reference)
    issue_date = str(snapshot.get("issue_date") or date.today().isoformat())
    validity_days = int(snapshot.get("validity_days") or 14)
    valid_until = str(snapshot.get("valid_until") or (date.fromisoformat(issue_date) + timedelta(days=validity_days)).isoformat())
    subtotal = snapshot.get("subtotal_excl_vat") or quote.get("quotation_subtotal") or 0
    vat_percent = snapshot.get("vat_percent") or 15
    vat_amount = snapshot.get("vat_amount") or 0
    total = snapshot.get("total_incl_vat") or quote.get("quotation_total") or 0
    client = _customer(quote)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("QuoteBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#27313A"))
    small = ParagraphStyle("QuoteSmall", parent=body, fontSize=7.5, leading=9, textColor=colors.HexColor("#58636D"))
    company_style = ParagraphStyle("QuoteCompany", parent=small, alignment=TA_RIGHT, fontSize=7.5, leading=9.5)
    heading = ParagraphStyle("QuoteHeading", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=22, leading=24, textColor=colors.HexColor("#20272D"), alignment=TA_RIGHT)
    doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=14 * mm, bottomMargin=15 * mm, title=f"Quotation {safe_reference}", author=COMPANY["name"])

    logo = _logo_path()
    logo_cell: Any = Paragraph(f"<b>{COMPANY['name']}</b>", styles["Heading2"])
    if logo:
        logo_cell = Image(str(logo), width=70 * mm, height=32 * mm, kind="proportional")
    company_text = Paragraph(
        f"<b>{COMPANY['name']}</b><br/>{COMPANY['address']}<br/>"
        f"Reg: {COMPANY['registration']} &nbsp; VAT: {COMPANY['vat']} &nbsp; CSD: {COMPANY['csd']}<br/>"
        f"{COMPANY['phone']} &nbsp; {COMPANY['email']}", company_style,
    )
    title_block = Table(
        [[Paragraph("QUOTATION", heading)], [company_text]],
        colWidths=[95 * mm],
    )
    title_block.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    header = Table([[logo_cell, title_block]], colWidths=[80 * mm, 95 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    billed_to = "<br/>".join(filter(None, [f"<b>{escape(client['company'] or client['name'])}</b>", escape(client["name"]) if client["company"] else "", escape(client["address"]), escape(client["email"]), escape(client["phone"])]))
    meta = Table([
        [Paragraph("<b>QUOTATION TO</b><br/>" + billed_to, body), Paragraph(
            f"<b>Reference:</b> {reference_xml}<br/><b>Issue date:</b> {escape(issue_date)}<br/>"
            f"<b>Valid until:</b> {escape(valid_until)}<br/><b>Currency:</b> ZAR", body)],
    ], colWidths=[112 * mm, 63 * mm])
    meta.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CDD5DA")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E4E8EB")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8F8")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 8)]))

    data = [["ITEM", "DESCRIPTION", "QTY", "UNIT EXCL. VAT", "TOTAL EXCL. VAT"]]
    for index, line in enumerate(lines, 1):
        description = escape(str(line.get("description") or line.get("name") or "Item"))
        sku = escape(str(line.get("sku") or ""))
        if sku:
            description += f"<br/><font color='#64717B' size='7'>SKU: {sku}</font>"
        data.append([
            str(index), Paragraph(description, body), str(line.get("quantity") or 1),
            _money(line.get("unit_price_excl_vat") or line.get("price") or line.get("amount")),
            _money(line.get("line_total_excl_vat") or line.get("amount")),
        ])
    items = Table(data, repeatRows=1, colWidths=[11 * mm, 79 * mm, 15 * mm, 34 * mm, 36 * mm])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#293238")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DEE2")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9F9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    totals = Table([
        ["Subtotal (excl. VAT)", _money(subtotal)],
        [f"VAT ({vat_percent}%)", _money(vat_amount)],
        ["Total (incl. VAT)", _money(total)],
    ], colWidths=[46 * mm, 36 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica"), ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#7DBE42")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    terms = Paragraph(
        f"Prices are quoted in South African Rand (ZAR). This quotation is valid for "
        f"{validity_days} calendar days, until {escape(valid_until)}.<br/>"
        f"<link href='{TERMS_URL}' color='#718204'><u>View Terms and Conditions</u></link>",
        body,
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6A747C"))
        canvas.drawString(16 * mm, 8 * mm, f"{COMPANY['name']} | Quotation {reference[:80]}")
        canvas.drawRightString(194 * mm, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build([header, Spacer(1, 6 * mm), meta, Spacer(1, 7 * mm), items, Spacer(1, 6 * mm), totals, Spacer(1, 7 * mm), terms], onFirstPage=footer, onLaterPages=footer)
    return str(target)

