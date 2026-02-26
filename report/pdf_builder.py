"""
PDF report generation from calculation result and record list.
Saves to a temporary file and returns path for sending in Telegram.
"""

import logging
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.platypus.tables import TableStyle

from parser.models import Record
from report.calculator import CalculationResult
from report.fonts_cyrillic import (
    CYRILLIC_FONT_BOLD_NAME,
    CYRILLIC_FONT_NAME,
    register_cyrillic_font,
)
from report.sheets_prices import get_category_prices

logger = logging.getLogger(__name__)


def build_pdf(
    calculation_result: CalculationResult,
    records: List[Record],
    title: str = "eLibroCargoReportBot — Report",
    spreadsheet_id: str | None = None,
    credentials_path: str | None = None,
    **meta: str,
) -> Path:
    """
    Builds PDF report: title, generation date, records table,
    summary by category, total, and "Generated: …" footer.
    Returns path to temporary PDF file (delete after sending).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path = Path(tmp.name)
    tmp.close()

    has_cyrillic_font = register_cyrillic_font()
    font_name = CYRILLIC_FONT_NAME if has_cyrillic_font else "Helvetica"
    font_bold = CYRILLIC_FONT_BOLD_NAME if has_cyrillic_font else "Helvetica-Bold"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
    )
    styles = getSampleStyleSheet()
    # Use Cyrillic-capable font when available (so category names etc. render correctly)
    styles["Normal"].fontName = font_name
    styles["Heading1"].fontName = font_bold
    styles["Heading2"].fontName = font_bold

    story = []

    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=16,
        spaceAfter=6 * mm,
    )
    story.append(Paragraph(title, title_style))

    # Report date
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    story.append(Paragraph(f"Report date: {generated_at}", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))

    # Records table
    if records:
        story.append(Paragraph("Records", styles["Heading2"]))
        data = [["Date", "Amount", "Category"]]
        for r in records:
            data.append([str(r.date), str(r.amount), r.category])
        t = Table(data, colWidths=[35 * mm, 30 * mm, 80 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 4 * mm))

    # Prices from Google Sheet (optional; public CSV or service account)
    sheet_prices: dict[str, Decimal] = {}
    sheet_access_failed = False
    sid = spreadsheet_id or meta.get("spreadsheet_id")
    creds = credentials_path or meta.get("credentials_path")
    if sid:
        if creds:
            sheet_prices = get_category_prices(sid, creds)
        else:
            sheet_prices = get_category_prices(sid, None)  # public CSV, no auth
        if not sheet_prices:
            sheet_access_failed = True
    elif spreadsheet_id is None and credentials_path is None:
        try:
            from config import get_settings
            s = get_settings()
            if getattr(s, "SPREADSHEET_ID", None):
                creds_path = getattr(s, "GOOGLE_CREDENTIALS_FILE", None)
                sheet_prices = get_category_prices(s.SPREADSHEET_ID, creds_path)
                if not sheet_prices:
                    sheet_access_failed = True
        except Exception:
            pass

    if sheet_access_failed:
        logger.warning(
            "Google Sheet: config is set but no data loaded. Check logs above for 'Google Sheet: no access'."
        )

    # Block: reference prices from Google Sheet (always show in PDF)
    story.append(Paragraph("Reference prices (Google Sheet)", styles["Heading2"]))
    if sheet_prices:
        sheet_data = [["Name", "Price"]]
        for name, price in sorted(sheet_prices.items(), key=lambda x: x[0]):
            sheet_data.append([name, str(price)])
        t_sheet = Table(sheet_data, colWidths=[100 * mm, 45 * mm])
        t_sheet.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.append(t_sheet)
    else:
        story.append(
            Paragraph(
                "Not available (no access or table not published). "
                "For public access: File → Share → Publish to web → CSV. Or set GOOGLE_CREDENTIALS_FILE for private sheets.",
                ParagraphStyle(
                    "SheetUnavailable",
                    parent=styles["Normal"],
                    fontName=font_name,
                    fontSize=9,
                    textColor=colors.gray,
                ),
            )
        )
    story.append(Spacer(1, 4 * mm))

    # By category summary
    if calculation_result.by_category:
        story.append(Paragraph("By category", styles["Heading2"]))
        if sheet_prices:
            cat_data = [["Category", "Amount", "Price (sheet)"]]
            for cat, amount in sorted(calculation_result.by_category.items(), key=lambda x: -x[1]):
                ref = str(sheet_prices.get(cat, "")) if cat in sheet_prices else ""
                cat_data.append([cat, str(amount), ref])
            t2 = Table(cat_data, colWidths=[70 * mm, 35 * mm, 40 * mm])
        else:
            cat_data = [["Category", "Amount"]]
            for cat, amount in sorted(calculation_result.by_category.items(), key=lambda x: -x[1]):
                cat_data.append([cat, str(amount)])
            t2 = Table(cat_data, colWidths=[100 * mm, 45 * mm])
        t2.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.append(t2)
        story.append(Spacer(1, 4 * mm))

    # Total
    story.append(
        Paragraph(
            f"<b>Total: {calculation_result.total}</b>",
            ParagraphStyle(
                "Total",
                parent=styles["Normal"],
                fontName=font_name,
                fontSize=12,
                spaceAfter=6 * mm,
            ),
        )
    )

    # Footer
    story.append(
        Paragraph(
            f"Generated: {generated_at}",
            ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontName=font_name,
                fontSize=8,
                textColor=colors.gray,
            ),
        )
    )

    doc.build(story)
    return path
