from decimal import Decimal
from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table
from reportlab.platypus.tables import TableStyle

from report.money_ru import amount_to_words_kzt, format_money_ru_kzt
from report.pdf_layout_constants import (
    SIGNS_FONT_SIZE,
    SIGNS_ROW_BOTTOM_PADDING,
    SIGNS_ROW_TOP_PADDING,
    SIGNS_SPACER_BEFORE_MM,
    SUMMARY_AMOUNT_LEADING,
    SUMMARY_BASE_FONT_SIZE,
    SUMMARY_ROW_BOTTOM_PADDING,
    SUMMARY_ROW_TOP_PADDING,
    SUMMARY_SPACER_AFTER_MM,
    SUMMARY_TABLE_FONT_SIZE,
    TOTAL_FONT_SIZE,
    TOTAL_ROW_BOTTOM_PADDING,
    TOTAL_ROW_TOP_PADDING,
    TOTAL_SPACER_AFTER_MM,
    TOTAL_TABLE_LABEL_COL_MM,
)


def build_totals_story(
    *,
    total: Decimal,
    nds_amount: Decimal,
    items_count: int,
    content_width: float,
    styles: Any,
    font_name: str,
    font_bold: str,
) -> list[Any]:
    """Итоги, сумма прописью и подписи."""
    total_data = [
        ["Итого:", format_money_ru_kzt(total)],
        ["В том числе НДС:", format_money_ru_kzt(nds_amount)],
    ]
    total_table_label_width = TOTAL_TABLE_LABEL_COL_MM * mm
    total_table = Table(
        total_data,
        colWidths=[total_table_label_width, content_width - total_table_label_width],
    )
    total_table.hAlign = "LEFT"
    total_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), font_bold),
                ("FONTNAME", (1, 0), (1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), TOTAL_FONT_SIZE),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), TOTAL_ROW_TOP_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, -1), TOTAL_ROW_BOTTOM_PADDING),
            ]
        )
    )

    total_formatted = format_money_ru_kzt(total)
    row1_text = f"<u>Всего наименований {items_count}, на сумму {total_formatted} KZT</u>"
    row2_text = amount_to_words_kzt(total).capitalize()
    summary_style = ParagraphStyle(
        "SummaryRow",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=SUMMARY_BASE_FONT_SIZE,
    )
    amount_words_style = ParagraphStyle(
        "AmountWordsRow",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=SUMMARY_BASE_FONT_SIZE,
        leading=SUMMARY_AMOUNT_LEADING,
    )
    summary_data = [
        [Paragraph(row1_text, summary_style)],
        [Paragraph(row2_text, amount_words_style)],
    ]
    summary_table = Table(summary_data, colWidths=[content_width])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), SUMMARY_TABLE_FONT_SIZE),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), SUMMARY_ROW_TOP_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, -1), SUMMARY_ROW_BOTTOM_PADDING),
            ]
        )
    )

    signs_data = [["Отпустил ________________________", "Получил ________________________"]]
    signs_table = Table(signs_data, colWidths=[content_width / 2, content_width / 2])
    signs_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), SIGNS_FONT_SIZE),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), SIGNS_ROW_TOP_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, -1), SIGNS_ROW_BOTTOM_PADDING),
            ]
        )
    )

    return [
        total_table,
        Spacer(1, TOTAL_SPACER_AFTER_MM * mm),
        summary_table,
        Spacer(1, SUMMARY_SPACER_AFTER_MM * mm),
        Spacer(1, SIGNS_SPACER_BEFORE_MM * mm),
        signs_table,
    ]

