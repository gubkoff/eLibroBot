"""
Небольшие утилиты для подготовки текста под элементы PDF-верстки.

Разделяем “чистое форматирование” и саму верстку, чтобы не тащить лишнюю логику в pdf_builder.py.
"""

from __future__ import annotations

from decimal import Decimal
from xml.sax.saxutils import escape


def format_cargo_for_cell(text: str) -> str:
    """
    Форматирует название товара для ячейки таблицы ReportLab.

    Если слово начинается с заглавной буквы и оно не первое — вставляем перенос строки.
    Возвращает строку с HTML-переносами `<br/>`, безопасную для `Paragraph`.
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


def format_ton(value: Decimal) -> str:
    """
    Формат тонн: запятая как разделитель, до 3 знаков, без хвостовых нулей.
    """
    s = f"{value:.3f}".replace(".", ",")
    return s.rstrip("0").rstrip(",")


def kg_to_t(kg: int) -> str:
    """
    Килограммы в тонны с локальным форматированием.
    """
    if not kg:
        return ""
    return format_ton(Decimal(kg) / Decimal("1000"))

