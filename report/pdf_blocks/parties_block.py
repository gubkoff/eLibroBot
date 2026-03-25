from typing import Any

from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table
from reportlab.platypus.tables import TableStyle

from report.weighing_print_data import WeighingPrintData
from report.pdf_layout_constants import (
    PARTIES_FONT_SIZE,
    PARTIES_LABEL_COL_MM,
    PARTIES_ROW_BOTTOM_PADDING,
    PARTIES_ROW_TOP_PADDING,
    PARTIES_SPACER_AFTER_MM,
    PARTIES_SPACER_BEFORE,
)


def build_parties_story(
    *,
    data: WeighingPrintData,
    content_width: float,
    font_name: str,
    font_bold: str,
) -> list[Any]:
    """Блок поставщик/покупатель со стандартными отступами."""
    supplier = data.supplier
    buyer = data.buyer

    col_label = PARTIES_LABEL_COL_MM * mm
    col_value = content_width - col_label
    parties_data: list[list[str]] = [["Поставщик", supplier]]
    if buyer.strip():
        parties_data.append(["Покупатель", buyer])

    parties_table = Table(parties_data, colWidths=[col_label, col_value])
    parties_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), font_name),
                ("FONTNAME", (1, 0), (1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), PARTIES_FONT_SIZE),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), PARTIES_ROW_TOP_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, -1), PARTIES_ROW_BOTTOM_PADDING),
            ]
        )
    )
    return [
        Spacer(1, PARTIES_SPACER_BEFORE),
        parties_table,
        Spacer(1, PARTIES_SPACER_AFTER_MM * mm),
    ]

