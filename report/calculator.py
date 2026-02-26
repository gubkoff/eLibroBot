"""
Расчёты по списку Record: общая сумма и разбивка по категориям.
Результат передаётся в pdf_builder для генерации отчёта.
"""

from dataclasses import dataclass
from decimal import Decimal

from parser.models import Record


@dataclass
class CalculationResult:
    """Результат расчёта по записям: общая сумма и суммы по категориям."""

    total: Decimal
    by_category: dict[str, Decimal]


def calculate(records: list[Record]) -> CalculationResult:
    """
    Считает общую сумму и суммы по категориям.
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
