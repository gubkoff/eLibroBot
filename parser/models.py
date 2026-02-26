"""Модели данных парсера."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Record:
    """Одна запись из сообщения: дата, сумма, категория."""

    date: date
    amount: Decimal
    category: str
    raw_text: str = ""
