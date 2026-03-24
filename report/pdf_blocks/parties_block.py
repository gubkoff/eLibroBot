from typing import Any, Optional

from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table
from reportlab.platypus.tables import TableStyle

from parser.models import WeighingData
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
    weighing: Optional[WeighingData],
    meta: dict[str, str],
    content_width: float,
    font_name: str,
    font_bold: str,
) -> list[Any]:
    """Блок поставщик/покупатель со стандартными отступами."""
    supplier = (
        meta.get("supplier")
        or meta.get("supplier_name")
        or 'Товарищество с ограниченной ответственностью "КазТим Комир"'
    )
    buyer = meta.get("buyer") or meta.get("buyer_name") or ""
    if weighing is not None:
        buyer_parts: list[str] = []
        if weighing.counterparty:
            buyer_parts.append(weighing.counterparty)
        if weighing.plate_number:
            buyer_parts.append(f"номер авто {weighing.plate_number}")
        buyer = ", ".join(buyer_parts) or buyer

    col_label = PARTIES_LABEL_COL_MM * mm
    col_value = content_width - col_label
    parties_data: list[list[str]] = [["Поставщик", supplier]]
    if buyer:
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

