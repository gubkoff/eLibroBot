"""
Парсинг текста сообщения в список Record.

Формат строки: дата сумма категория
- Разделители: пробел, запятая, табуляция (подряд идущие считаются одним разделителем).
- Дата: YYYY-MM-DD или DD.MM.YYYY.
- Сумма: число (целое или с точкой/запятой).
- Категория: остаток строки (может быть из нескольких слов).
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List

from parser.models import Record

logger = logging.getLogger(__name__)

# Поддерживаемые форматы даты (первая версия)
DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y"]


def _parse_date(s: str) -> date | None:
    """Парсит строку даты. Возвращает None при ошибке."""
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> Decimal | None:
    """Парсит строку суммы в Decimal. Принимает запятую или точку как десятичный разделитель."""
    s = s.strip().replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_line(line: str) -> Record | None:
    """
    Парсит одну строку в Record.
    Ожидаемый формат: дата сумма категория (разделители — пробелы, запятая, табуляция).
    """
    line = line.strip()
    if not line:
        return None
    # Разбиваем по пробелам/запятым/табуляции (подряд идущие — один разделитель)
    parts = re.split(r"[\s,\t]+", line, maxsplit=2)
    if len(parts) < 3:
        logger.warning("Пропуск строки (нужны минимум дата, сумма, категория): %r", line)
        return None
    date_str, amount_str, category = parts[0], parts[1], parts[2].strip()
    if not category:
        logger.warning("Пропуск строки (пустая категория): %r", line)
        return None
    parsed_date = _parse_date(date_str)
    if parsed_date is None:
        logger.warning("Пропуск строки (неверный формат даты %r): %r", date_str, line)
        return None
    parsed_amount = _parse_amount(amount_str)
    if parsed_amount is None:
        logger.warning("Пропуск строки (неверная сумма %r): %r", amount_str, line)
        return None
    return Record(
        date=parsed_date,
        amount=parsed_amount,
        category=category,
        raw_text=line,
    )


def parse_message(text: str) -> List[Record]:
    """
    Разбирает текст сообщения в список Record.
    Каждая непустая строка должна быть в формате: дата сумма категория.
    Невалидные строки пропускаются с записью в лог.
    """
    if not text or not text.strip():
        return []
    records: List[Record] = []
    for line in text.splitlines():
        record = _parse_line(line)
        if record is not None:
            records.append(record)
    return records
