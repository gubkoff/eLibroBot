"""Тесты доменных правил накладной (текущая реализация, до выноса в service layer).

Эти тесты фиксируют правила, которые сейчас живут в разных местах:
- `parser/parser.py`: расчёт суммы по весу и цене
- `report/pdf_builder.py`: выбор нетто (корректировка приоритетно) и расчёт брутто (тара + корректировка)

Когда появится `report/invoice_rules.py`, эти тесты нужно перевести на него.
"""

from decimal import Decimal

import pytest

from parser import parse_message


def _calc_amount_kzt(weight_kg: int, price_per_ton: Decimal) -> Decimal:
    """Текущая формула: (кг/1000) * цена, округление до 0.01."""
    return ((Decimal(weight_kg) / Decimal("1000")) * price_per_ton).quantize(Decimal("0.01"))


def test_amount_uses_adjusted_weight_when_present():
    """Если есть «Вес с корректировкой», сумма считается по нему (а не по netto)."""
    text = """
ВЗВЕШИВАНИЕ № 1
Тара: 17200
Брутто: 23140
Нетто: 5940
Вес с корректировкой: 6118
Цена за тонну: 19000
""".strip()
    data = parse_message(text)
    assert data is not None
    assert data.adjusted_netto_kg == 6118
    assert data.netto_kg == 5940
    assert data.price_per_ton == Decimal("19000")
    assert data.amount == _calc_amount_kzt(6118, Decimal("19000"))


def test_amount_uses_netto_when_no_adjusted_weight():
    """Если корректировки нет, сумма считается по netto."""
    text = """
ВЗВЕШИВАНИЕ № 1
Нетто: 26820
Цена за тонну: 16000
""".strip()
    data = parse_message(text)
    assert data is not None
    assert data.adjusted_netto_kg == 0
    assert data.amount == _calc_amount_kzt(26820, Decimal("16000"))


def test_amount_keeps_raw_sum_when_price_missing():
    """Если цены нет, сумма берётся из сообщения (raw)."""
    text = """
ВЗВЕШИВАНИЕ № 1
Нетто: 1000
Сумма, тг: 12345
""".strip()
    data = parse_message(text)
    assert data is not None
    assert data.price_per_ton == Decimal("0")
    assert data.amount == Decimal("12345")


def test_brutto_final_rule_is_tara_plus_adjusted():
    """Правило накладной: при корректировке брутто в документе = тара + вес с корректировкой."""
    text = """
ВЗВЕШИВАНИЕ № 1
Тара: 17200
Брутто: 23140
Нетто: 5940
Вес с корректировкой: 6118
Цена за тонну: 19000
""".strip()
    data = parse_message(text)
    assert data is not None
    brutto_for_doc = data.tara_kg + data.adjusted_netto_kg if data.adjusted_netto_kg else data.brutto_kg
    assert brutto_for_doc == 17200 + 6118


def test_netto_final_rule_is_adjusted_or_netto():
    """Правило накладной: нетто в документе = вес с корректировкой, если он есть, иначе netto."""
    text = """
ВЗВЕШИВАНИЕ № 1
Нетто: 5940
Вес с корректировкой: 6118
""".strip()
    data = parse_message(text)
    assert data is not None
    netto_for_doc = data.adjusted_netto_kg or data.netto_kg
    assert netto_for_doc == 6118

    text2 = """
ВЗВЕШИВАНИЕ № 2
Нетто: 5940
""".strip()
    data2 = parse_message(text2)
    assert data2 is not None
    netto_for_doc2 = data2.adjusted_netto_kg or data2.netto_kg
    assert netto_for_doc2 == 5940

