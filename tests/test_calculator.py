"""Тесты калькулятора: общая сумма и разбивка по категориям."""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from report import calculate, CalculationResult


@dataclass
class _RecordForCalc:
    """Минимальная запись для тестов calculate(): amount и category."""

    amount: Decimal
    category: str


def test_empty_list():
    """Пустой список — total=0, by_category пустой."""
    result = calculate([])
    assert result.total == Decimal("0")
    assert result.by_category == {}


def test_single_record():
    """Одна запись."""
    records = [_RecordForCalc(amount=Decimal("100"), category="продукты")]
    result = calculate(records)
    assert result.total == Decimal("100")
    assert result.by_category == {"продукты": Decimal("100")}


def test_multiple_categories():
    """Несколько записей в разных категориях."""
    records = [
        _RecordForCalc(amount=Decimal("100"), category="продукты"),
        _RecordForCalc(amount=Decimal("50"), category="транспорт"),
        _RecordForCalc(amount=Decimal("200"), category="продукты"),
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
        _RecordForCalc(amount=Decimal("10"), category="кофе"),
        _RecordForCalc(amount=Decimal("20"), category="кофе"),
    ]
    result = calculate(records)
    assert result.total == Decimal("30")
    assert result.by_category == {"кофе": Decimal("30")}
