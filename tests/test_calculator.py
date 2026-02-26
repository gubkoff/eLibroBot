"""Тесты калькулятора."""

from decimal import Decimal

import pytest
from datetime import date

from parser.models import Record
from report import calculate, CalculationResult


def test_empty_list():
    """Пустой список — total=0, by_category пустой."""
    result = calculate([])
    assert result.total == Decimal("0")
    assert result.by_category == {}


def test_single_record():
    """Одна запись."""
    records = [Record(date=date(2025, 2, 26), amount=Decimal("100"), category="продукты")]
    result = calculate(records)
    assert result.total == Decimal("100")
    assert result.by_category == {"продукты": Decimal("100")}


def test_multiple_categories():
    """Несколько записей в разных категориях."""
    records = [
        Record(date=date(2025, 2, 26), amount=Decimal("100"), category="продукты"),
        Record(date=date(2025, 2, 27), amount=Decimal("50"), category="транспорт"),
        Record(date=date(2025, 2, 28), amount=Decimal("200"), category="продукты"),
    ]
    result = calculate(records)
    assert result.total == Decimal("350")
    assert result.by_category == {
        "продукты": Decimal("300"),
        "транспорт": Decimal("50"),
    }


def test_same_category_summed():
    """Одна категория — суммы складываются."""
    records = [
        Record(date=date(2025, 2, 26), amount=Decimal("10"), category="кофе"),
        Record(date=date(2025, 2, 27), amount=Decimal("20"), category="кофе"),
    ]
    result = calculate(records)
    assert result.total == Decimal("30")
    assert result.by_category == {"кофе": Decimal("30")}
