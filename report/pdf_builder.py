"""
PDF report generation from calculation result and record list.
Saves to a temporary file and returns path for sending in Telegram.
"""

import tempfile
from datetime import datetime
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


def build_pdf(
    calculation_result: CalculationResult,
    records: List[Record],
    title: str = "eLibroCargoReportBot — Report",
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

    # By category summary
    if calculation_result.by_category:
        story.append(Paragraph("By category", styles["Heading2"]))
        cat_data = [["Category", "Amount"]]
        for cat, amount in sorted(calculation_result.by_category.items(), key=lambda x: -x[1]):
            cat_data.append([cat, str(amount)])
        t2 = Table(cat_data, colWidths=[100 * mm, 45 * mm])
        t2.setStyle(
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
