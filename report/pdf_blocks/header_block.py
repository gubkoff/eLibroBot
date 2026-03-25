from reportlab.lib import colors
from reportlab.platypus import Table
from reportlab.platypus.tables import TableStyle

from report.weighing_print_data import WeighingPrintData
from report.pdf_layout_constants import (
    HEADER_FONT_SIZE,
    HEADER_ROW_HEIGHT,
    HEADER_UNDERLINE_WIDTH,
)


def resolve_doc_header(
    data: WeighingPrintData,
) -> str:
    """Возвращает строку заголовка накладной: № и дата."""
    return (
        f"{data.title} № {data.doc_number} от {data.doc_date} г."
        if data.doc_number
        else f"{data.title} от {data.doc_date} г."
    )


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

