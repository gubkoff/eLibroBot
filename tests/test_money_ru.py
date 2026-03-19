"""Русское оформление сумм: report.money_ru."""

from decimal import Decimal

import pytest

from report.money_ru import amount_to_words_kzt, format_money_ru_kzt, int_to_words_ru


def test_format_money_ru_kzt_grouping_and_tyiyn():
    assert format_money_ru_kzt(Decimal("1234567.89")) == "1 234 567,89"
    assert format_money_ru_kzt(Decimal("0.10")) == "0,10"
    assert format_money_ru_kzt(Decimal("1.005")) == "1,01"
    assert format_money_ru_kzt(Decimal("-1.005")) == "-1,01"


def test_int_to_words_ru_thousand_two():
    s = int_to_words_ru(1002)
    assert "одна" in s
    assert "тысяча" in s
    assert s.endswith("два")


def test_int_to_words_ru_two_thousand():
    assert int_to_words_ru(2000) == "две тысячи"


def test_int_to_words_ru_zero():
    assert int_to_words_ru(0) == "ноль"

def test_int_to_words_ru_raises_out_of_range():
    with pytest.raises(ValueError):
        int_to_words_ru(-1)
    with pytest.raises(ValueError):
        int_to_words_ru(100_000_000)


def test_amount_to_words_kzt():
    s = amount_to_words_kzt(Decimal("5000.00"))
    assert "тенге" in s
    assert "00 тиын" in s
    assert amount_to_words_kzt(Decimal("1.005")).endswith("01 тиын")
