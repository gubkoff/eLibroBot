import logging
import os
import tempfile
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional
from report.text_formatting import format_cargo_for_cell, kg_to_t


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
from report.pdf_layout_constants import (
    CUT_LINE_COLOR_HEX,
    CUT_LINE_DASH_OFF,
    CUT_LINE_DASH_ON,
    CUT_LINE_OFFSET_MM,
    CUT_LINE_WIDTH,
    FRAME_PADDING,
    HEADER_FONT_SIZE,
    HEADER_ROW_HEIGHT,
    HEADER_UNDERLINE_WIDTH,
    ITEMS_BOX_WIDTH,
    ITEMS_CARGO_FONT_SIZE,
    ITEMS_CARGO_LEADING,
    ITEMS_COL_BASE_WIDTHS,
    ITEMS_GRID_WIDTH,
    ITEMS_HEADER_BOTTOM_PADDING,
    ITEMS_HEADER_TOP_PADDING,
    ITEMS_ROW_BOTTOM_PADDING,
    ITEMS_ROW_TOP_PADDING,
    ITEMS_SPACER_AFTER_MM,
    PAGE_MARGIN_BOTTOM_MM,
    PAGE_MARGIN_LEFT_MM,
    PAGE_MARGIN_RIGHT_MM,
    PAGE_MARGIN_TOP_MM,
    PARTIES_FONT_SIZE,
    PARTIES_LABEL_COL_MM,
    PARTIES_ROW_BOTTOM_PADDING,
    PARTIES_ROW_TOP_PADDING,
    PARTIES_SPACER_AFTER_MM,
    PARTIES_SPACER_BEFORE,
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
    TABLE_HEADER_BG_HEX,
    TOTAL_FONT_SIZE,
    TOTAL_ROW_BOTTOM_PADDING,
    TOTAL_ROW_TOP_PADDING,
    TOTAL_SPACER_AFTER_MM,
    TOTAL_TABLE_LABEL_COL_MM,
)
from report.money_ru import amount_to_words_kzt, format_money_ru_kzt

logger = logging.getLogger(__name__)


def _layout_debug_context(
    *,
    title: str,
    weighing: Optional[WeighingData],
    records_count: int,
    duplicate_on_one_page: bool,
    content_width: float,
    content_height: float,
    frame_h: float,
) -> dict[str, Any]:
    """Контекст для диагностики проблем верстки без чувствительных данных."""
    return {
        "title": title,
        "duplicate_on_one_page": duplicate_on_one_page,
        "records_count": records_count,
        "content_width_pt": round(content_width, 2),
        "content_height_pt": round(content_height, 2),
        "half_frame_height_pt": round(frame_h, 2),
        "invoice_number": (weighing.invoice_number if weighing else "") or "",
        "weighing_number": (weighing.weighing_number if weighing else "") or "",
        "cargo_len": len((weighing.cargo if weighing else "") or ""),
        "counterparty_len": len((weighing.counterparty if weighing else "") or ""),
    }


def _resolve_doc_header(
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


def _build_header_table(header_text: str, *, content_width: float, font_bold: str) -> Table:
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


def _build_parties_story(
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


def _build_totals_story(
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
    left_margin = PAGE_MARGIN_LEFT_MM * mm
    right_margin = PAGE_MARGIN_RIGHT_MM * mm
    top_margin = PAGE_MARGIN_TOP_MM * mm
    bottom_margin = PAGE_MARGIN_BOTTOM_MM * mm

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
        leftPadding=FRAME_PADDING,
        rightPadding=FRAME_PADDING,
        topPadding=FRAME_PADDING,
        bottomPadding=FRAME_PADDING,
        id="bottom",
    )
    top_frame = Frame(
        left_margin,
        bottom_margin + frame_h,
        content_width,
        frame_h,
        leftPadding=FRAME_PADDING,
        rightPadding=FRAME_PADDING,
        topPadding=FRAME_PADDING,
        bottomPadding=FRAME_PADDING,
        id="top",
    )

    # Один фрейм на страницу (когда 2 копии не помещаются на одном листе)
    single_frame = Frame(
        left_margin,
        bottom_margin,
        content_width,
        content_height,
        leftPadding=FRAME_PADDING,
        rightPadding=FRAME_PADDING,
        topPadding=FRAME_PADDING,
        bottomPadding=FRAME_PADDING,
        id="single",
    )

    # doc и выбор шаблона определим после сборки block_story (нужно понять, помещается ли блок в половину листа)
    doc: BaseDocTemplate
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font_name
    styles["Heading1"].fontName = font_bold
    styles["Heading2"].fontName = font_bold

    block_story: list[Any] = []

    header_text = _resolve_doc_header(title=title, weighing=weighing, meta=meta)
    block_story.append(
        _build_header_table(
            header_text,
            content_width=content_width,
            font_bold=font_bold,
        )
    )
    block_story.extend(
        _build_parties_story(
            weighing=weighing,
            meta=meta,
            content_width=content_width,
            font_name=font_name,
            font_bold=font_bold,
        )
    )

    # Таблица позиций
    if weighing is not None:
        block_story.append(_build_items_table(weighing, font_name, font_bold, content_width))
        block_story.append(Spacer(1, ITEMS_SPACER_AFTER_MM * mm))

    # Итог по накладной — таблица: первый столбец «Итого», второй — число (оформлено как деньги)
    total = calculation_result.total
    if nds_override is not None:
        nds_amount = nds_override
    else:
        nds_amount = (total / Decimal("116") * Decimal("16")).quantize(Decimal("0.01"))
    items_count = 1 if weighing is not None else len(records) or 0
    block_story.extend(
        _build_totals_story(
            total=total,
            nds_amount=nds_amount,
            items_count=items_count,
            content_width=content_width,
            styles=styles,
            font_name=font_name,
            font_bold=font_bold,
        )
    )
    layout_ctx = _layout_debug_context(
        title=title,
        weighing=weighing,
        records_count=len(records),
        duplicate_on_one_page=duplicate_on_one_page,
        content_width=content_width,
        content_height=content_height,
        frame_h=frame_h,
    )

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
        try:
            doc_one.build(list(block_story))
        except LayoutError:
            logger.exception("LayoutError в single-layout build_pdf", extra=layout_ctx)
            raise
        return path_one

    # Сначала пытаемся сверстать 2 копии на одном листе (верх/низ).
    # Если ReportLab не может уложить контент (LayoutError) — печатаем вторую копию на следующей странице сверху.
    def _draw_cut_line(canvas, _doc) -> None:
        """Пунктирная линия разреза строго посередине страницы (только для режима double)."""
        canvas.saveState()
        try:
            canvas.setStrokeColor(colors.HexColor(CUT_LINE_COLOR_HEX))
            canvas.setLineWidth(CUT_LINE_WIDTH)
            canvas.setDash(CUT_LINE_DASH_ON, CUT_LINE_DASH_OFF)
            # На 5 мм ниже границы между верхним и нижним фреймами
            y = bottom_margin + frame_h - CUT_LINE_OFFSET_MM * mm
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
        logger.warning(
            "Double-layout не поместился, переключаемся на single+pagebreak",
            extra=layout_ctx,
            exc_info=True,
        )
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
        try:
            doc_single.build(story_single)
        except LayoutError:
            logger.exception("LayoutError в fallback single-layout build_pdf", extra=layout_ctx)
            raise
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
        fontSize=ITEMS_CARGO_FONT_SIZE,
        leading=ITEMS_CARGO_LEADING,
    )

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
    base = ITEMS_COL_BASE_WIDTHS
    total = sum(base)
    col_widths = [(w / total) * doc_width for w in base]
    table = Table(data, colWidths=col_widths)
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
