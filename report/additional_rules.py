from __future__ import annotations

from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

from parser.models import WeighingData

__all__ = ["apply_additional_formula", "effective_brutto_kg"]


def effective_brutto_kg(data: WeighingData) -> int:
    """
    Брутто сообщения с учётом текущего правила:
    если есть вес с корректировкой, используем тара + корректировка, иначе raw брутто.
    """
    if data.adjusted_netto_kg:
        return int(data.tara_kg + data.adjusted_netto_kg)
    return int(data.brutto_kg)


def apply_additional_formula(current: WeighingData, previous: WeighingData) -> WeighingData:
    """
    Применяет формулу режима additional:
    - Тара = брутто предыдущего взвешивания
    - Нетто = вес с корректировкой текущего, иначе нетто текущего
    - Брутто = Тара + Нетто
    - Сумма = (Нетто / 1000) * Цена
    """
    tara_kg = effective_brutto_kg(previous)
    netto_kg = int(current.adjusted_netto_kg or current.netto_kg)
    brutto_kg = int(tara_kg + netto_kg)
    amount = (
        (Decimal(netto_kg) / Decimal("1000")) * current.price_per_ton
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return replace(
        current,
        tara_kg=tara_kg,
        netto_kg=netto_kg,
        brutto_kg=brutto_kg,
        amount=amount,
    )

