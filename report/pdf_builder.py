import logging
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional


from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.platypus.tables import TableStyle

from parser.models import WeighingData
from report.calculator import CalculationResult
from report.fonts_cyrillic import (
    CYRILLIC_FONT_BOLD_NAME,
    CYRILLIC_FONT_NAME,
    register_cyrillic_font,
)

logger = logging.getLogger(__name__)


def build_pdf(
    calculation_result: CalculationResult,
    records: List[Any],
    title: str = "Расходная накладная",
    spreadsheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
    weighing: Optional[WeighingData] = None,
    **meta: str,
) -> Path:
    """
    Формирует PDF-документ накладной: шапка с номером и датой,
    реквизиты поставщика и покупателя, таблицу позиций и итоги.
    Возвращает путь к временному файлу PDF (его нужно удалить после отправки).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path = Path(tmp.name)
    tmp.close()

    # Регистрируем шрифт с поддержкой кириллицы (DejaVuSans или Arial, если найден).
    # Используем зарегистрированные имена, чтобы ReportLab корректно применял начертания.
    has_cyrillic_font = register_cyrillic_font()
    font_name = CYRILLIC_FONT_NAME if has_cyrillic_font else "Helvetica"
    font_bold = CYRILLIC_FONT_BOLD_NAME if has_cyrillic_font else "Helvetica-Bold"
    full_line = "____________________"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font_name
    styles["Heading1"].fontName = font_bold
    styles["Heading2"].fontName = font_bold

    story = []

    # Header: накладная № … от …
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
    header_text = f"{title} № {doc_number} от {doc_date} г." if doc_number else f"{title} от {doc_date} г."
    # Заголовок в виде таблицы с одним столбцом
    header_table = Table([[header_text]], colWidths=[doc.width], rowHeights=[20])
    header_table.hAlign = "LEFT"
    header_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 16),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 2.0, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)

    # Реквизиты поставщика и покупателя
    supplier = (
        meta.get("supplier")
        or meta.get("supplier_name")
        or 'Товарищество с ограниченной ответственностью "КазТим Комир"'
    )
    buyer = meta.get("buyer") or meta.get("buyer_name") or ""
    if weighing is not None:
        # Покупатель: контрагент + номер авто
        buyer_parts: list[str] = []
        if weighing.counterparty:
            buyer_parts.append(weighing.counterparty)
        if weighing.plate_number:
            buyer_parts.append(f"авто {weighing.plate_number}")
        buyer = ", ".join(buyer_parts) or buyer
    if supplier:
        story.append(Paragraph(f"Поставщик: {supplier}", styles["Normal"]))
    if buyer:
        story.append(Paragraph(f"Покупатель: {buyer}", styles["Normal"]))
    if supplier or buyer:
        story.append(Spacer(1, 4 * mm))

    # Таблица позиций
    if weighing is not None:
        story.append(_build_items_table(weighing, font_name, font_bold, doc.width))
        story.append(Spacer(1, 4 * mm))

    # Итог по накладной
    total = calculation_result.total
    story.append(
        Paragraph(
            f"<b>Итого: {total}</b>",
            ParagraphStyle(
                "Total",
                parent=styles["Normal"],
                fontName=font_name,
                fontSize=12,
                spaceAfter=6 * mm,
            ),
        )
    )

    # При необходимости: НДС (по умолчанию не рассчитывается)
    # nds_amount = Decimal("0.00")
    # story.append(Paragraph(f"В том числе НДС: {nds_amount}", styles["Normal"]))

    # Подписи
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Отпустил ________________________", styles["Normal"]))
    story.append(Paragraph("Получил _________________________", styles["Normal"]))

    # Дублируем весь контент страницы два раза
    story = story + [Spacer(1, 10 * mm)] + story

    doc.build(story)
    return path


def _build_items_table(
    weighing: WeighingData, font_name: str, font_bold: str, doc_width: float
) -> Table:
    """Создаёт таблицу с позициями накладной по данным WeighingData."""
    data: list[list[str]] = [
        ["Товар", "Тара, тонна", "Нетто, тонна", "Брутто, тонна", "Цена", "Сумма"]
    ]

    def kg_to_t(kg: int) -> str:
        return f"{Decimal(kg) / Decimal('1000'):.3f}" if kg else ""

    data.append(
        [
            weighing.cargo,
            kg_to_t(weighing.tara_kg),
            kg_to_t(weighing.netto_kg),
            kg_to_t(weighing.brutto_kg),
            str(weighing.price_per_ton),
            str(weighing.amount),
        ]
    )
    # Ширины колонок вычисляем пропорционально, чтобы сумма была ровно doc_width
    base = [60, 25, 25, 25, 25, 30]  # как было, в "весах"
    total = sum(base)
    col_widths = [(w / total) * doc_width for w in base]
    table = Table(data, colWidths=col_widths)
    table.hAlign = "LEFT"
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffffff")),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (1, 1), (-2, -1), "RIGHT"),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.black),
            ]
        )
    )
    return table
