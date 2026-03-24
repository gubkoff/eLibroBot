from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.platypus import Table
from reportlab.platypus.tables import TableStyle

from parser.models import WeighingData
from report.pdf_layout_constants import (
    HEADER_FONT_SIZE,
    HEADER_ROW_HEIGHT,
    HEADER_UNDERLINE_WIDTH,
)


def resolve_doc_header(
    *,
    title: str,
    weighing: Optional[WeighingData],
    meta: dict[str, str],
) -> str:
    """Возвращает строку заголовка накладной: № и дата."""
    doc_number = ""
    doc_date = ""
    if weighing is not None:
        doc_number = weighing.invoice_number or weighing.weighing_number
        if weighing.weighing_datetime:
            doc_date = weighing.weighing_datetime.strftime("%d.%m.%Y")
        elif weighing.message_sent_at:
            doc_date = weighing.message_sent_at.strftime("%d.%m.%Y")
    if not doc_number:
        doc_number = meta.get("doc_number", "")
    if not doc_date:
        doc_date = meta.get("doc_date") or datetime.now().strftime("%d.%m.%Y")
    return f"{title} № {doc_number} от {doc_date} г." if doc_number else f"{title} от {doc_date} г."


def build_header_table(header_text: str, *, content_width: float, font_bold: str) -> Table:
    """Таблица-заголовок с нижней линией."""
    header_table = Table([[header_text]], colWidths=[content_width], rowHeights=[HEADER_ROW_HEIGHT])
    header_table.hAlign = "LEFT"
    header_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), HEADER_FONT_SIZE),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), HEADER_UNDERLINE_WIDTH, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return header_table

