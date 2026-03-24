import logging
import os
import tempfile
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional
from report.text_formatting import format_cargo_for_cell


from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus.doctemplate import LayoutError
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    KeepInFrame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TopPadder,
)
from reportlab.platypus.tables import TableStyle

from parser.models import WeighingData
from report.calculator import CalculationResult
from report.invoice_models import InvoiceData
from report.fonts_cyrillic import (
    CYRILLIC_FONT_BOLD_NAME,
    CYRILLIC_FONT_NAME,
    register_cyrillic_font,
)
from report.money_ru import amount_to_words_kzt, format_money_ru_kzt

logger = logging.getLogger(__name__)


def build_pdf(
    calculation_result: CalculationResult,
    records: List[Any],
    title: str = "Расходная накладная",
    spreadsheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
    weighing: Optional[WeighingData] = None,
    *,
    nds_override: Optional[Decimal] = None,
    duplicate_on_one_page: bool = True,
    **meta: str,
) -> Path:
    """
    Формирует PDF-документ накладной: шапка с номером и датой,
    реквизиты поставщика и покупателя, таблицу позиций и итоги.
    Возвращает путь к временному файлу PDF (его нужно удалить после отправки).
    """

    # Регистрируем шрифт с поддержкой кириллицы (DejaVuSans или Arial, если найден).
    # Используем зарегистрированные имена, чтобы ReportLab корректно применял начертания.
    has_cyrillic_font = register_cyrillic_font()
    font_name = CYRILLIC_FONT_NAME if has_cyrillic_font else "Helvetica"
    font_bold = CYRILLIC_FONT_BOLD_NAME if has_cyrillic_font else "Helvetica-Bold"

    # Поля A4 (мм): 15 мм со всех сторон
    left_margin = 15 * mm
    right_margin = 15 * mm
    top_margin = 15 * mm
    bottom_margin = 25 * mm

    page_width, page_height = A4
    content_width = page_width - left_margin - right_margin
    content_height = page_height - top_margin - bottom_margin

    # Два вертикальных фрейма: верхний — 1-я копия, нижний — 2-я копия (прижата к низу через TopPadder)
    frame_h = content_height / 2
    bottom_frame = Frame(
        left_margin,
        bottom_margin,
        content_width,
        frame_h,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="bottom",
    )
    top_frame = Frame(
        left_margin,
        bottom_margin + frame_h,
        content_width,
        frame_h,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="top",
    )

    # Один фрейм на страницу (когда 2 копии не помещаются на одном листе)
    single_frame = Frame(
        left_margin,
        bottom_margin,
        content_width,
        content_height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="single",
    )

    # doc и выбор шаблона определим после сборки block_story (нужно понять, помещается ли блок в половину листа)
    doc: BaseDocTemplate
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font_name
    styles["Heading1"].fontName = font_bold
    styles["Heading2"].fontName = font_bold

    block_story: list[Any] = []

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
    header_table = Table([[header_text]], colWidths=[content_width], rowHeights=[20])
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
    block_story.append(header_table)

    # Реквизиты поставщика и покупателя — таблица: столбец 1 — описание, столбец 2 — текст
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
    col_label = 23 * mm
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
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    block_story.append(Spacer(1, 10))
    block_story.append(parties_table)
    block_story.append(Spacer(1, 4 * mm))

    # Таблица позиций
    if weighing is not None:
        block_story.append(_build_items_table(weighing, font_name, font_bold, content_width))
        block_story.append(Spacer(1, 4 * mm))

    # Итог по накладной — таблица: первый столбец «Итого», второй — число (оформлено как деньги)
    total = calculation_result.total
    if nds_override is not None:
        nds_amount = nds_override
    else:
        nds_amount = (total / Decimal("116") * Decimal("16")).quantize(Decimal("0.01"))
    total_data = [
        ["Итого:", format_money_ru_kzt(total)],
        ["В том числе НДС:", format_money_ru_kzt(nds_amount)],
    ]
    total_table_label_width = 155 * mm;
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
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    block_story.append(total_table)
    block_story.append(Spacer(1, 5 * mm))

    # Всего наименований и сумма прописью — таблица под итогом
    items_count = 1 if weighing is not None else len(records) or 0
    total_formatted = format_money_ru_kzt(total)
    row1_text = f"<u>Всего наименований {items_count}, на сумму {total_formatted} KZT</u>"
    row2_text = amount_to_words_kzt(total).capitalize()
    summary_style = ParagraphStyle(
        "SummaryRow",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
    )
    amount_words_style = ParagraphStyle(
        "AmountWordsRow",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=10,
        leading=12,
    )
    # Paragraph автоматически перенесёт “сумму прописью” на новую строку при нехватке ширины.
    summary_data = [
        [Paragraph(row1_text, summary_style)],
        [Paragraph(row2_text, amount_words_style)],
    ]
    summary_table = Table(summary_data, colWidths=[content_width])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    block_story.append(summary_table)
    block_story.append(Spacer(1, 10 * mm))

    # Подписи: таблица — отпустил (левый столбец), получил (правый)
    block_story.append(Spacer(1, 6 * mm))
    signs_data = [["Отпустил ________________________", "Получил ________________________"]]
    signs_table = Table(signs_data, colWidths=[content_width / 2, content_width / 2])
    signs_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    block_story.append(signs_table)

    if not duplicate_on_one_page:
        tmp_one = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        path_one = Path(tmp_one.name)
        tmp_one.close()
        doc_one = BaseDocTemplate(
            str(path_one),
            pagesize=A4,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
            pageTemplates=[
                PageTemplate(id="single", frames=[single_frame]),
            ],
        )
        doc_one.build(list(block_story))
        return path_one

    # Сначала пытаемся сверстать 2 копии на одном листе (верх/низ).
    # Если ReportLab не может уложить контент (LayoutError) — печатаем вторую копию на следующей странице сверху.
    def _draw_cut_line(canvas, _doc) -> None:
        """Пунктирная линия разреза строго посередине страницы (только для режима double)."""
        canvas.saveState()
        try:
            canvas.setStrokeColor(colors.HexColor("#999999"))
            canvas.setLineWidth(0.6)
            canvas.setDash(3, 3)
            # На 5 мм ниже границы между верхним и нижним фреймами
            y = bottom_margin + frame_h - 5 * mm
            canvas.line(left_margin, y, page_width - right_margin, y)
        finally:
            canvas.restoreState()

    class _SinglePageOnlyCanvas(Canvas):
        """Canvas, запрещающий появление 2+ страниц (для режима double)."""

        def showPage(self) -> None:
            # На второй странице (и далее) прекращаем сборку, чтобы переключиться на single-layout без линии.
            if self.getPageNumber() >= 2:
                raise LayoutError("Double layout produced more than one page")
            return super().showPage()

    tmp_double = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path_double = Path(tmp_double.name)
    tmp_double.close()
    doc_double = BaseDocTemplate(
        str(path_double),
        pagesize=A4,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        pageTemplates=[
            PageTemplate(
                id="double",
                frames=[top_frame, bottom_frame],
                onPage=_draw_cut_line,
            ),
        ],
    )
    story_double: list[Any] = []
    story_double.extend(block_story)
    story_double.append(FrameBreak())
    story_double.append(
        TopPadder(
            KeepInFrame(
                content_width,
                frame_h,
                list(block_story),
                mode="shrink",
                hAlign="LEFT",
                vAlign="TOP",
            )
        )
    )

    try:
        doc_double.build(story_double, canvasmaker=_SinglePageOnlyCanvas)
        return path_double
    except LayoutError:
        if os.path.isfile(path_double):
            try:
                os.remove(path_double)
            except OSError:
                logger.warning("Не удалось удалить временный PDF (double) %s", path_double)
        doc_single = BaseDocTemplate(
            str(path_double),
            pagesize=A4,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
            pageTemplates=[
                PageTemplate(id="single", frames=[single_frame]),
            ],
        )
        story_single = list(block_story) + [PageBreak()] + list(block_story)
        doc_single.build(story_single)
        return path_double


def _build_items_table(
    weighing: WeighingData, font_name: str, font_bold: str, doc_width: float
) -> Table:
    """Создаёт таблицу с позициями накладной по данным WeighingData."""
    data: list[list[str]] = [
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
        fontSize=10,
        leading=11,
    )

    def _format_ton(value: Decimal) -> str:
        """Тонны: запятая как разделитель, до 3 знаков, без хвостовых нулей."""
        s = f"{value:.3f}".replace(".", ",")
        s = s.rstrip("0").rstrip(",")
        return s

    def kg_to_t(kg: int) -> str:
        """Килограммы в тонны: запятая как разделитель, 3 знака после запятой, пробел в целой части."""
        if not kg:
            return ""
        return _format_ton(Decimal(kg) / Decimal("1000"))

    netto_kg = weighing.adjusted_netto_kg or weighing.netto_kg
    brutto_kg = (
        weighing.tara_kg + weighing.adjusted_netto_kg
        if weighing.adjusted_netto_kg
        else weighing.brutto_kg
    )

    data.append(
        [
            Paragraph(format_cargo_for_cell(weighing.cargo), cargo_style),
            "тонна",
            kg_to_t(weighing.tara_kg),
            kg_to_t(netto_kg),
            kg_to_t(brutto_kg),
            format_money_ru_kzt(weighing.price_per_ton),
            format_money_ru_kzt(weighing.amount),
        ]
    )
    # Ширины колонок вычисляем пропорционально, чтобы сумма была ровно doc_width
    base = [55, 20, 16, 16, 16, 26, 26]
    total = sum(base)
    col_widths = [(w / total) * doc_width for w in base]
    table = Table(data, colWidths=col_widths)
    table.hAlign = "LEFT"
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffffff")),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (2, 1), (-2, -1), "RIGHT"),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 11),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.black),
            ]
        )
    )
    return table


def _invoice_to_weighing_for_table(inv: InvoiceData) -> WeighingData:
    """Минимальный ``WeighingData`` для существующей таблицы позиций (итоговые веса из invoice)."""
    return WeighingData(
        weighing_number=inv.weighing_number,
        plate_number=inv.plate_number,
        tara_kg=inv.tara_kg,
        brutto_kg=inv.brutto_kg_final,
        netto_kg=inv.netto_kg_final,
        cargo=inv.cargo,
        counterparty="",
        invoice_number=inv.invoice_number,
        price_per_ton=inv.price_per_ton_raw,
        amount=inv.amount_final,
        weighing_datetime=inv.weighing_datetime,
        user=inv.user or "",
        message_sent_at=inv.message_sent_at,
        adjusted_netto_kg=0,
    )


def build_pdf_invoice(
    invoice: InvoiceData,
    *,
    title: str = "Расходная накладная",
    duplicate_on_one_page: bool = True,
    **meta: str,
) -> Path:
    """
    PDF-накладная по ``InvoiceData`` (после ``weighing_to_invoice``).

    ``duplicate_on_one_page=False`` — одна копия на одной странице.
    """
    w = _invoice_to_weighing_for_table(invoice)
    merged: dict[str, str] = {str(k): str(v) for k, v in meta.items()}
    sup = (invoice.supplier_name or "").strip()
    if sup:
        merged["supplier"] = sup
    buyer_line = (invoice.buyer_line or "").strip()
    if buyer_line:
        merged["buyer"] = buyer_line
    else:
        w = replace(w, counterparty=invoice.counterparty)

    return build_pdf(
        CalculationResult(
            total=invoice.amount_final,
            by_category={invoice.cargo: invoice.amount_final},
        ),
        records=[],
        title=title,
        weighing=w,
        nds_override=invoice.nds_amount,
        duplicate_on_one_page=duplicate_on_one_page,
        **merged,
    )
