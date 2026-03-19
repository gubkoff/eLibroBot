"""
Русское оформление денежных сумм (аналог слоя «money.ru» в коде: не домен, только текст/формат).

- ``format_money_ru_kzt`` — отображение суммы в стиле RU/KZT (тиыны, запятая, пробелы в целой части).
- ``amount_to_words_kzt`` — пропись для KZT («… тенге … тиын»).

Согласование по правилам русского языка: разряд **тысяч** — женский род (одна/две тысячи),
**миллионы** и **младшие триады** (единицы…сотни) — мужской род.

При появлении других локалей/валют можно добавить фасад (язык + валюта), который выбирает
``format_money_*`` / ``amount_to_words_*``; текущие функции с суффиксом ``_ru_kzt`` — явный формат.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

__all__ = ["format_money_ru_kzt", "amount_to_words_kzt", "int_to_words_ru"]

Gender = Literal["m", "f"]

KZT_FRACTION_DIGITS = 2
KZT_FRACTION_SCALE = 10**KZT_FRACTION_DIGITS
KZT_QUANT = Decimal("0.01")
MAX_INT_FOR_WORDS = 99_999_999


def format_money_ru_kzt(value: Decimal) -> str:
    """Сумма/цена в формате RU/KZT: 2 знака после запятой (тиыны), запятая, пробелы в целой части."""
    q = value.quantize(KZT_QUANT, rounding=ROUND_HALF_UP)
    s = format(q, "f")
    int_part, _, frac_part = s.partition(".")
    int_part = int_part or "0"
    chunks = [
        int_part[max(0, i - 3) : i]
        for i in range(len(int_part), 0, -3)
    ]
    grouped = " ".join(reversed(chunks))
    return f"{grouped},{frac_part}"


# Слова для прописного написания суммы (рус.)
_ONES = [
    "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _triad_to_words_ru(n: int, *, gender: Gender = "m") -> list[str]:
    """0..999 -> слова; для gender='f' единицы 1 и 2 — «одна», «две» (разряд тысяч)."""
    if n <= 0:
        return []
    if n > 999:
        raise ValueError("triad out of range")
    out: list[str] = []
    if n >= 100:
        out.append(_HUNDREDS[n // 100])
        n %= 100
    if 20 <= n <= 99:
        out.append(_TENS[n // 10])
        n %= 10
    if 10 <= n <= 19:
        out.append(_ONES[n])
        return [w for w in out if w]
    if n == 0:
        return [w for w in out if w]
    if gender == "f":
        if n == 1:
            out.append("одна")
        elif n == 2:
            out.append("две")
        else:
            out.append(_ONES[n])
    else:
        out.append(_ONES[n])
    return [w for w in out if w]


def _choose_plural(n: int, one: str, few: str, many: str) -> str:
    """Выбор формы по числу: 1/2-4/прочее с учётом 11-14."""
    n = abs(n)
    if 11 <= (n % 100) <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if last in (2, 3, 4):
        return few
    return many


def int_to_words_ru(n: int) -> str:
    """Целое число в пропись по-русски (до 99 999 999) с согласованием родов по разрядам."""
    if n == 0:
        return "ноль"
    if n < 0 or n > MAX_INT_FOR_WORDS:
        raise ValueError(f"n out of range for int_to_words_ru: {n}")
    out: list[str] = []

    millions = n // 1_000_000
    thousands = (n // 1000) % 1000
    rest = n % 1000

    if millions:
        out.extend(_triad_to_words_ru(millions, gender="m"))
        out.append(_choose_plural(millions, "миллион", "миллиона", "миллионов"))

    if thousands:
        out.extend(_triad_to_words_ru(thousands, gender="f"))
        out.append(_choose_plural(thousands, "тысяча", "тысячи", "тысяч"))

    if rest:
        out.extend(_triad_to_words_ru(rest, gender="m"))

    return " ".join(out)


def amount_to_words_kzt(value: Decimal) -> str:
    """Сумма в пропись: «X тенге YY тиын» (тиыны — два знака)."""
    q = value.quantize(KZT_QUANT, rounding=ROUND_HALF_UP)
    scaled = (q * KZT_FRACTION_SCALE).to_integral_value(rounding=ROUND_HALF_UP)
    int_part = int(scaled // 100)
    tyiyn = int(scaled % 100)
    words = int_to_words_ru(int_part)
    return f"{words} тенге {tyiyn:02d} тиын"
