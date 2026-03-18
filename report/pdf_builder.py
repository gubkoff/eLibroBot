import logging
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional
from xml.sax.saxutils import escape


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


def _format_money(value: Decimal) -> str:
    """Сумма/цена: 2 знака после запятой (тиыны), запятая как разделитель, пробел в целой части."""
    s = f"{value:.2f}"
    int_part, _, frac_part = s.partition(".")
    int_part = int_part or "0"
    chunks = [
        int_part[max(0, i - 3) : i]
        for i in range(len(int_part), 0, -3)
    ]
    grouped = " ".join(reversed(chunks))
    return f"{grouped},{frac_part}"


# Слова для прописного написания суммы (рус.)
_ONES = [
    "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _triad_to_words_ru(n: int, *, gender: str = "m") -> list[str]:
    """0..999 -> слова. gender: 'm' (один/два) или 'f' (одна/две)."""
    if n <= 0:
        return []
    if n > 999:
        raise ValueError("triad out of range")
    out: list[str] = []
    if n >= 100:
        out.append(_HUNDREDS[n // 100])
        n %= 100
    if 20 <= n <= 99:
        out.append(_TENS[n // 10])
        n %= 10
    if 10 <= n <= 19:
        out.append(_ONES[n])
        return [w for w in out if w]
    if n == 0:
        return [w for w in out if w]
    if gender == "f":
        if n == 1:
            out.append("одна")
        elif n == 2:
            out.append("две")
        else:
            out.append(_ONES[n])
    else:
        out.append(_ONES[n])
    return [w for w in out if w]


def _choose_plural(n: int, one: str, few: str, many: str) -> str:
    """Выбор формы по числу: 1/2-4/прочее с учётом 11-14."""
    n = abs(n)
    if 11 <= (n % 100) <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if last in (2, 3, 4):
        return few
    return many


def _int_to_words_ru(n: int) -> str:
    """Целое число в пропись по-русски (до 99 999 999)."""
    if n == 0:
        return "ноль"
    if n < 0 or n > 99_999_999:
        return str(n)
    out: list[str] = []

    millions = n // 1_000_000
    thousands = (n // 1000) % 1000
    rest = n % 1000

    if millions:
        out.extend(_triad_to_words_ru(millions, gender="m"))
        out.append(_choose_plural(millions, "миллион", "миллиона", "миллионов"))

    if thousands:
        if thousands == 1:
            # По требованию: 1002 -> «тысяча две» (без «одна»)
            out.append("тысяча")
        else:
            out.extend(_triad_to_words_ru(thousands, gender="f"))
            out.append(_choose_plural(thousands, "тысяча", "тысячи", "тысяч"))

    if rest:
        if thousands == 1 and rest == 2:
            out.append("две")
        else:
            out.extend(_triad_to_words_ru(rest, gender="m"))

    return " ".join(out)


def _amount_to_words(value: Decimal) -> str:
    """Сумма в пропись: «X тенге YY тиын» (тиыны — два знака)."""
    value = value.quantize(Decimal("0.01"))
    int_part = int(value)
    tyiyn = int(round((value - int_part) * 100))
    words = _int_to_words_ru(int_part)
    return f"{words} тенге {tyiyn:02d} тиын"


def _format_cargo_for_cell(text: str) -> str:
    """
    Форматирует название товара для ячейки таблицы:
    если слово начинается с заглавной буквы и оно не первое — вставляем перенос строки.
    Возвращает строку с HTML-переносами <br/>, безопасную для Paragraph.
    """
    text = (text or "").strip()
    if not text:
        return ""
    parts = text.split()
    out: list[str] = []
    for i, w in enumerate(parts):
        w_escaped = escape(w)
        if i > 0 and w and w[0].isupper():
            out.append("<br/>" + w_escaped)
        else:
            out.append(w_escaped)
    return " ".join(out)


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
    
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=15 * mm,
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
    col_label = 63 * mm
    col_value = doc.width - col_label
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
    story.append(Spacer(1, 10))
    story.append(parties_table)
    story.append(Spacer(1, 4 * mm))

    # Таблица позиций
    if weighing is not None:
        story.append(_build_items_table(weighing, font_name, font_bold, doc.width))
        story.append(Spacer(1, 4 * mm))

    # Итог по накладной — таблица: первый столбец «Итого», второй — число (оформлено как деньги)
    total = calculation_result.total
    nds_amount = (total / Decimal("116") * Decimal("16")).quantize(Decimal("0.01"))
    total_data = [
        ["Итого:", _format_money(total)],
        ["В том числе НДС:", _format_money(nds_amount)],
    ]
    total_table_label_width = 165 * mm;
    total_table = Table(total_data, colWidths=[total_table_label_width, doc.width - total_table_label_width])
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
    story.append(total_table)
    story.append(Spacer(1, 5 * mm))

    # Всего наименований и сумма прописью — таблица под итогом
    items_count = 1 if weighing is not None else len(records) or 0
    total_formatted = _format_money(total)
    row1_text = f"<u>Всего наименований {items_count}, на сумму {total_formatted} KZT</u>"
    row2_text = _amount_to_words(total).capitalize()
    summary_style = ParagraphStyle(
        "SummaryRow",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
    )
    summary_data = [[Paragraph(row1_text, summary_style)], [row2_text]]
    summary_table = Table(summary_data, colWidths=[doc.width])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTNAME", (0, 1), (-1, 1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTSIZE", (0, 1), (-1, 1), 10),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 10 * mm))

    # Подписи: таблица — отпустил (левый столбец), получил (правый)
    story.append(Spacer(1, 6 * mm))
    signs_data = [["Отпустил ________________________", "Получил ________________________"]]
    signs_table = Table(signs_data, colWidths=[doc.width / 2, doc.width / 2])
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
    story.append(signs_table)

    # Дублируем весь контент страницы два раза
    story = story + [Spacer(1, 50 * mm)] + story

    doc.build(story)
    return path


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
            Paragraph(_format_cargo_for_cell(weighing.cargo), cargo_style),
            "тонна",
            kg_to_t(weighing.tara_kg),
            kg_to_t(netto_kg),
            kg_to_t(brutto_kg),
            _format_money(weighing.price_per_ton),
            _format_money(weighing.amount),
        ]
    )
    # Ширины колонок вычисляем пропорционально, чтобы сумма была ровно doc_width
    base = [55, 20, 16, 20, 20, 20, 27]
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
