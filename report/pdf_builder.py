import logging
import os
import tempfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional


from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus.doctemplate import LayoutError
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    KeepInFrame,
    PageBreak,
    PageTemplate,
    Spacer,
    TopPadder,
)

from parser.models import WeighingData
from report.calculator import CalculationResult
from report.invoice_models import InvoiceData
from report.pdf_blocks import (
    build_header_table,
    build_items_table,
    build_parties_story,
    build_totals_story,
    resolve_doc_header,
)
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
    ITEMS_SPACER_AFTER_MM,
    PAGE_MARGIN_BOTTOM_MM,
    PAGE_MARGIN_LEFT_MM,
    PAGE_MARGIN_RIGHT_MM,
    PAGE_MARGIN_TOP_MM,
)

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

    header_text = resolve_doc_header(title=title, weighing=weighing, meta=meta)
    block_story.append(
        build_header_table(
            header_text,
            content_width=content_width,
            font_bold=font_bold,
        )
    )
    block_story.extend(
        build_parties_story(
            weighing=weighing,
            meta=meta,
            content_width=content_width,
            font_name=font_name,
            font_bold=font_bold,
        )
    )

    # Таблица позиций
    if weighing is not None:
        block_story.append(build_items_table(weighing, font_name, font_bold, content_width))
        block_story.append(Spacer(1, ITEMS_SPACER_AFTER_MM * mm))

    # Итог по накладной — таблица: первый столбец «Итого», второй — число (оформлено как деньги)
    total = calculation_result.total
    if nds_override is not None:
        nds_amount = nds_override
    else:
        nds_amount = (total / Decimal("116") * Decimal("16")).quantize(Decimal("0.01"))
    items_count = 1 if weighing is not None else len(records) or 0
    block_story.extend(
        build_totals_story(
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
