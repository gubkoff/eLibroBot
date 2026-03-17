"""
Расчёты по списку записей: общая сумма и разбивка по категориям.
Элементы списка должны иметь атрибуты amount (Decimal) и category (str).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class CalculationResult:
    """Результат расчёта: общая сумма и суммы по категориям."""

    total: Decimal
    by_category: dict[str, Decimal]


def calculate(records: list[Any]) -> CalculationResult:
    """
    Считает общую сумму и суммы по категориям.
    У каждого элемента records должны быть атрибуты amount и category.
    При пустом списке возвращает total=0 и пустой by_category.
    """
    if not records:
        return CalculationResult(total=Decimal("0"), by_category={})
    by_category: dict[str, Decimal] = {}
    total = Decimal("0")
    for r in records:
        total += r.amount
        by_category[r.category] = by_category.get(r.category, Decimal("0")) + r.amount
    return CalculationResult(total=total, by_category=by_category)
