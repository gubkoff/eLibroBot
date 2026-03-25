import logging
import os
import tempfile
from pathlib import Path
from typing import Any


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

from report.pdf_blocks import (
    build_header_table,
    build_items_table,
    build_parties_story,
    build_totals_story,
    resolve_doc_header,
)
from report.weighing_print_data import DEFAULT_SUPPLIER, WeighingPrintData
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


class _SinglePageOnlyCanvas(Canvas):
    """Canvas, запрещающий появление 2+ страниц (для режима double)."""

    def showPage(self) -> None:
        # На второй странице (и далее) прекращаем сборку, чтобы переключиться на single-layout без линии.
        if self.getPageNumber() >= 2:
            raise LayoutError("Double layout produced more than one page")
        return super().showPage()


def _draw_cut_line_factory(
    *,
    left_margin: float,
    right_margin: float,
    bottom_margin: float,
    frame_h: float,
    page_width: float,
):
    """Фабрика обработчика onPage для пунктирной линии разреза."""

    def _draw_cut_line(canvas, _doc) -> None:
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

    return _draw_cut_line


def _layout_debug_context(
    *,
    data: WeighingPrintData,
    content_width: float,
    content_height: float,
    frame_h: float,
) -> dict[str, Any]:
    """Контекст для диагностики проблем верстки без чувствительных данных."""
    return {
        "title": data.title,
        "duplicate_on_one_page": data.duplicate_on_one_page,
        "items_count": data.items_count,
        "content_width_pt": round(content_width, 2),
        "content_height_pt": round(content_height, 2),
        "half_frame_height_pt": round(frame_h, 2),
        "doc_number": data.doc_number,
        "cargo_len": len(data.cargo or ""),
        "buyer_len": len(data.buyer or ""),
    }


def build_pdf(data: WeighingPrintData) -> Path:
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

    # Поля A4 (мм)
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

    header_text = resolve_doc_header(data=data)
    block_story.append(
        build_header_table(
            header_text,
            content_width=content_width,
            font_bold=font_bold,
        )
    )
    block_story.extend(
        build_parties_story(
            data=data,
            content_width=content_width,
            font_name=font_name,
            font_bold=font_bold,
        )
    )

    # Таблица позиций
    block_story.append(build_items_table(data, font_name, font_bold, content_width))
    block_story.append(Spacer(1, ITEMS_SPACER_AFTER_MM * mm))

    # Итог по накладной — таблица: первый столбец «Итого», второй — число (оформлено как деньги)
    block_story.extend(
        build_totals_story(
            data=data,
            content_width=content_width,
            styles=styles,
            font_name=font_name,
            font_bold=font_bold,
        )
    )
    layout_ctx = _layout_debug_context(
        data=data,
        content_width=content_width,
        content_height=content_height,
        frame_h=frame_h,
    )

    if not data.duplicate_on_one_page:
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
                onPage=_draw_cut_line_factory(
                    left_margin=left_margin,
                    right_margin=right_margin,
                    bottom_margin=bottom_margin,
                    frame_h=frame_h,
                    page_width=page_width,
                ),
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
