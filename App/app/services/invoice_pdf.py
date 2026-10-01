"""Branded customer-facing invoice PDF generation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from typing import Any

from app.services.quotation_pdf import COMPANY, _logo_path


def _money(value: Any) -> str:
    try:
        return f"R {Decimal(str(value or 0)):,.2f}"
    except (InvalidOperation, ValueError):
        return "R 0.00"


def generate_invoice_pdf(invoice: dict[str, Any], filename: str) -> str:
    """Render a draft or issued invoice without internal supplier pricing."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    lines = invoice.get("lines") or []
    if not lines:
        raise ValueError("This invoice has no line items.")
    target = Path(filename).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    status = str(invoice.get("status") or "draft").lower()
    number = str(invoice.get("invoice_number") or f"DRAFT-{str(invoice.get('_id') or '')[-8:]}")
    title = "TAX INVOICE" if status == "issued" else "INVOICE DRAFT"
    issue_date = str(invoice.get("issue_date") or "Not issued")
    due_date = str(invoice.get("due_date") or "Set when issued")
    quote_reference = str(invoice.get("source_quote_reference") or "")
    purchase_order = str(invoice.get("purchase_order_number") or "")
    customer = invoice.get("customer") or {}

    styles = getSampleStyleSheet()
    body = ParagraphStyle("InvoiceBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#27313A"))
    small = ParagraphStyle("InvoiceSmall", parent=body, fontSize=7.5, leading=9, textColor=colors.HexColor("#58636D"))
    company_style = ParagraphStyle("InvoiceCompany", parent=small, alignment=TA_RIGHT, fontSize=7.5, leading=9.5)
    heading = ParagraphStyle("InvoiceHeading", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=21, leading=23, textColor=colors.HexColor("#20272D"), alignment=TA_RIGHT)
    doc = SimpleDocTemplate(
        str(target), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=15 * mm, title=f"{title} {number}", author=COMPANY["name"],
    )

    logo = _logo_path()
    logo_cell: Any = Paragraph(f"<b>{COMPANY['name']}</b>", styles["Heading2"])
    if logo:
        logo_cell = Image(str(logo), width=70 * mm, height=32 * mm, kind="proportional")
    company_text = Paragraph(
        f"<b>{COMPANY['name']}</b><br/>{COMPANY['address']}<br/>"
        f"Reg: {COMPANY['registration']} &nbsp; VAT: {COMPANY['vat']} &nbsp; CSD: {COMPANY['csd']}<br/>"
        f"{COMPANY['phone']} &nbsp; {COMPANY['email']}", company_style,
    )
    title_block = Table([[Paragraph(title, heading)], [company_text]], colWidths=[95 * mm])
    title_block.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    header = Table([[logo_cell, title_block]], colWidths=[80 * mm, 95 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    billed_to = "<br/>".join(filter(None, [
        f"<b>{escape(str(customer.get('company') or customer.get('name') or 'Customer'))}</b>",
        escape(str(customer.get("name") or "")) if customer.get("company") else "",
        escape(str(customer.get("address") or "")), escape(str(customer.get("email") or "")),
        f"VAT: {escape(str(customer.get('vat_number')))}" if customer.get("vat_number") else "",
    ]))
    meta_lines = [
        f"<b>Invoice:</b> {escape(number)}", f"<b>Issue date:</b> {escape(issue_date)}",
        f"<b>Due date:</b> {escape(due_date)}", f"<b>Quote:</b> {escape(quote_reference)}",
    ]
    if purchase_order:
        meta_lines.append(f"<b>Customer PO:</b> {escape(purchase_order)}")
    meta = Table([
        [Paragraph("<b>INVOICE TO</b><br/>" + billed_to, body), Paragraph("<br/>".join(meta_lines), body)],
    ], colWidths=[108 * mm, 67 * mm])
    meta.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CDD5DA")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E4E8EB")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8F8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    data = [["ITEM", "DESCRIPTION", "QTY", "UNIT EXCL. VAT", "TOTAL EXCL. VAT"]]
    for index, line in enumerate(lines, 1):
        description = escape(str(line.get("description") or line.get("name") or "Item"))
        sku = escape(str(line.get("sku") or ""))
        if sku:
            description += f"<br/><font color='#64717B' size='7'>SKU: {sku}</font>"
        data.append([
            str(index), Paragraph(description, body), str(line.get("quantity") or 1),
            _money(line.get("unit_price_excl_vat")), _money(line.get("line_total_excl_vat")),
        ])
    items = Table(data, repeatRows=1, colWidths=[11 * mm, 79 * mm, 15 * mm, 34 * mm, 36 * mm])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#293238")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DEE2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9F9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    totals = Table([
        ["Subtotal (excl. VAT)", _money(invoice.get("subtotal_excl_vat"))],
        [f"VAT ({invoice.get('vat_percent') or 15}%)", _money(invoice.get("vat_amount"))],
        ["Total (incl. VAT)", _money(invoice.get("total_incl_vat"))],
    ], colWidths=[46 * mm, 36 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 1), "Helvetica"), ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#7DBE42")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    notice = "Draft only. This document is not an issued Tax Invoice." if status != "issued" else "Amounts are payable in South African Rand (ZAR). Please use the invoice number as the payment reference."

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6A747C"))
        canvas.drawString(16 * mm, 8 * mm, f"{COMPANY['name']} | {title} {number[:60]}")
        canvas.drawRightString(194 * mm, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build([
        header, Spacer(1, 6 * mm), meta, Spacer(1, 7 * mm), items,
        Spacer(1, 6 * mm), totals, Spacer(1, 7 * mm), Paragraph(notice, body),
    ], onFirstPage=footer, onLaterPages=footer)
    return str(target)
