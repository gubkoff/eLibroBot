"""Тесты парсера сообщений."""

import pytest
from datetime import date
from decimal import Decimal

from parser import parse_message, Record


def test_parse_single_line_iso_date():
    """Одна строка в формате YYYY-MM-DD сумма категория."""
    result = parse_message("2025-02-26 100 продукты")
    assert len(result) == 1
    assert result[0].date == date(2025, 2, 26)
    assert result[0].amount == Decimal("100")
    assert result[0].category == "продукты"


def test_parse_single_line_dot_date():
    """Одна строка в формате DD.MM.YYYY сумма категория."""
    result = parse_message("26.02.2025 250 транспорт")
    assert len(result) == 1
    assert result[0].date == date(2025, 2, 26)
    assert result[0].amount == Decimal("250")
    assert result[0].category == "транспорт"


def test_parse_multiple_lines():
    """Несколько валидных строк."""
    text = """
2025-02-26 100 продукты
2025-02-27 50  кофе
26.02.2025 300 услуги
"""
    result = parse_message(text)
    assert len(result) == 3
    assert result[0].category == "продукты"
    assert result[1].category == "кофе"
    assert result[2].amount == Decimal("300")


def test_parse_amount_with_decimal():
    """Сумма с десятичной частью (точка или запятая)."""
    result = parse_message("2025-02-26 99.50 продукты")
    assert len(result) == 1
    assert result[0].amount == Decimal("99.50")
    result2 = parse_message("2025-02-26 99,25 товары")
    assert len(result2) == 1
    assert result2[0].amount == Decimal("99.25")


def test_parse_category_multiple_words():
    """Категория из нескольких слов."""
    result = parse_message("2025-02-26 100 продукты питания")
    assert len(result) == 1
    assert result[0].category == "продукты питания"


def test_parse_invalid_line_skipped():
    """Невалидная строка пропускается, остальные парсятся."""
    text = """
2025-02-26 100 продукты
not-a-date 50 категория
2025-02-27 200 другое
"""
    result = parse_message(text)
    assert len(result) == 2
    assert result[0].category == "продукты"
    assert result[1].category == "другое"


def test_parse_empty_string():
    """Пустая строка — пустой список."""
    assert parse_message("") == []
    assert parse_message("   \n  ") == []


def test_parse_too_few_parts_skipped():
    """Строка без категории пропускается."""
    result = parse_message("2025-02-26 100")
    assert len(result) == 0
