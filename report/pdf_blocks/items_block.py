from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.tables import TableStyle

from report.weighing_print_data import WeighingPrintData
from report.money_ru import format_money_ru_kzt
from report.pdf_layout_constants import (
    ITEMS_BOX_WIDTH,
    ITEMS_CARGO_FONT_SIZE,
    ITEMS_CARGO_LEADING,
    ITEMS_COL_BASE_WIDTHS,
    ITEMS_GRID_WIDTH,
    ITEMS_HEADER_BOTTOM_PADDING,
    ITEMS_HEADER_TOP_PADDING,
    ITEMS_ROW_BOTTOM_PADDING,
    ITEMS_ROW_TOP_PADDING,
    TABLE_HEADER_BG_HEX,
)
from report.text_formatting import format_cargo_for_cell, kg_to_t


def build_items_table(
    data: WeighingPrintData, font_name: str, font_bold: str, doc_width: float
) -> Table:
    """Создаёт таблицу с позициями накладной по данным WeighingData."""
    table_data: list[list[str]] = [
        [
            "Товар",
            "Единица\nизмерения",
            "Тара",
            "Нетто",
            "Брутто",
            "Цена",
            "Сумма",
        ]
    ]
    cargo_style = ParagraphStyle(
        "CargoCell",
        fontName=font_name,
        fontSize=ITEMS_CARGO_FONT_SIZE,
        leading=ITEMS_CARGO_LEADING,
    )

    netto_kg = data.adjusted_netto_kg or data.netto_kg
    brutto_kg = (
        data.tara_kg + data.adjusted_netto_kg
        if data.adjusted_netto_kg
        else data.brutto_kg
    )

    table_data.append(
        [
            Paragraph(format_cargo_for_cell(data.cargo), cargo_style),
            "тонна",
            kg_to_t(data.tara_kg),
            kg_to_t(netto_kg),
            kg_to_t(brutto_kg),
            format_money_ru_kzt(data.price_per_ton),
            format_money_ru_kzt(data.amount),
        ]
    )

    base = ITEMS_COL_BASE_WIDTHS
    total = sum(base)
    col_widths = [(w / total) * doc_width for w in base]
    table = Table(table_data, colWidths=col_widths)
    table.hAlign = "LEFT"
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TABLE_HEADER_BG_HEX)),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (2, 1), (-2, -1), "RIGHT"),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), ITEMS_ROW_TOP_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, -1), ITEMS_ROW_BOTTOM_PADDING),
                ("TOPPADDING", (0, 0), (-1, 0), ITEMS_HEADER_TOP_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, 0), ITEMS_HEADER_BOTTOM_PADDING),
                ("GRID", (0, 0), (-1, -1), ITEMS_GRID_WIDTH, colors.gray),
                ("BOX", (0, 0), (-1, -1), ITEMS_BOX_WIDTH, colors.black),
            ]
        )
    )
    return table

