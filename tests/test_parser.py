"""Тесты парсера сообщений формата «ВЗВЕШИВАНИЕ № …» → WeighingData."""

from datetime import datetime
from decimal import Decimal

from parser import parse_message, WeighingData


WEIGHING_SAMPLE = """
ВЗВЕШИВАНИЕ № 3722
Номер: 851EM02
Тара: 18360
Брутто: 45180
Нетто: 26820
Груз: Кузнецкий 0-300
Контрагент: По контракту
Накладная: №3722
Цена за тонну: 16000
Сумма, тг: 429120
Дата взвешивания: 2026-03-14 09:32:04
Пользователь: Руфина
Сообщение отправлено: 2026-03-14 09:32:04
""".strip()


def test_parse_full_weighing():
    """Полный валидный текст — один WeighingData с заполненными полями."""
    result = parse_message(WEIGHING_SAMPLE)
    assert result is not None
    assert isinstance(result, WeighingData)
    assert result.weighing_number == "3722"
    assert result.plate_number == "851EM02"
    assert result.tara_kg == 18360
    assert result.brutto_kg == 45180
    assert result.netto_kg == 26820
    assert result.cargo == "Кузнецкий 0-300"
    assert result.counterparty == "По контракту"
    assert result.invoice_number == "3722"
    assert result.price_per_ton == Decimal("16000")
    assert result.amount == Decimal("429120")
    assert result.weighing_datetime == datetime(2026, 3, 14, 9, 32, 4)
    assert result.user == "Руфина"
    assert result.message_sent_at == datetime(2026, 3, 14, 9, 32, 4)


def test_parse_minimal_weighing():
    """Минимум: заголовок ВЗВЕШИВАНИЕ и пара полей."""
    text = """
ВЗВЕШИВАНИЕ № 100
Груз: Уголь
Сумма: 50000
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.weighing_number == "100"
    assert result.cargo == "Уголь"
    assert result.amount == Decimal("50000")
    assert result.tara_kg == 0
    assert result.netto_kg == 0
    assert result.price_per_ton == Decimal("0")
    assert result.weighing_datetime is None


def test_parse_weighing_number_from_header():
    """Номер взвешивания из первой строки."""
    result = parse_message("ВЗВЕШИВАНИЕ № 999\nГруз: X\nСумма: 1")
    assert result is not None
    assert result.weighing_number == "999"

    result2 = parse_message("ВЗВЕШИВАНИЕ № ABC-1\nГруз: X\nСумма: 1")
    assert result2 is not None
    assert result2.weighing_number == "ABC-1"


def test_parse_key_aliases():
    """Синонимы ключей: Товар→cargo, Покупатель→counterparty, Цена/т и т.д."""
    text = """
ВЗВЕШИВАНИЕ № 1
Товар: Щебень
Покупатель: ООО Рога
Цена/т: 2000
Сумма, kzt: 100 500,50
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.cargo == "Щебень"
    assert result.counterparty == "ООО Рога"
    assert result.price_per_ton == Decimal("2000")
    assert result.amount == Decimal("100500.50")


def test_parse_adjusted_weight():
    """«Вес с корректировкой» парсится в adjusted_netto_kg и может отличаться от netto_kg."""
    text = """
ВЗВЕШИВАНИЕ № 3766
Номер: 683BQ09
Тара: 17200
Брутто: 23140
Нетто: 5940
Вес с корректировкой: 6118
Груз: Шубарколь 60-300 Грохот
Контрагент: физическое лицо
Накладная: №3766
Цена за тонну: 19000
Сумма, тг: 116242
Дата взвешивания: 2026-03-16 14:53:44
Пользователь: Руфина
Сообщение отправлено 2026-03-16 14:53:44
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.netto_kg == 5940
    assert result.adjusted_netto_kg == 6118


def test_parse_int_with_spaces():
    """Целые числа с пробелами как разделителями тысяч."""
    text = """
ВЗВЕШИВАНИЕ № 1
Тара: 18 360
Брутто: 45 180
Нетто: 26 820
Груз: X
Сумма: 429 120
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.tara_kg == 18360
    assert result.brutto_kg == 45180
    assert result.netto_kg == 26820
    assert result.amount == Decimal("429120")


def test_parse_decimal_comma():
    """Сумма/цена с запятой как десятичным разделителем."""
    text = """
ВЗВЕШИВАНИЕ № 1
Груз: X
Цена за тонну: 16 000,50
Сумма: 50 483,00
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.price_per_ton == Decimal("16000.50")
    assert result.amount == Decimal("50483.00")


def test_amount_calculated_from_weight_and_price_when_sum_missing():
    """Если сумма отсутствует, но есть вес и цена — amount рассчитывается автоматически."""
    text = """
ВЗВЕШИВАНИЕ № 1
Нетто: 26820
Цена за тонну: 16000
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.amount == Decimal("429120.00")


def test_parse_empty_string():
    """Пустая строка или только пробелы — None."""
    assert parse_message("") is None
    assert parse_message("   \n  \n  ") is None


def test_parse_no_colon_lines_ignored():
    """Строки без «Ключ: значение» не ломают парсер."""
    text = """
ВЗВЕШИВАНИЕ № 1
Груз: Уголь
просто текст без двоеточия
Сумма: 1000
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.cargo == "Уголь"
    assert result.amount == Decimal("1000")


def test_parse_unknown_keys_skipped():
    """Неизвестные ключи пропускаются, известные парсятся."""
    text = """
ВЗВЕШИВАНИЕ № 1
Груз: Уголь
КакойтоПоле: игнор
Сумма: 999
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.cargo == "Уголь"
    assert result.amount == Decimal("999")


def test_parse_invoice_number_strips_no():
    """В номере накладной убирается префикс №."""
    text = """
ВЗВЕШИВАНИЕ № 1
Накладная: №3722
Груз: X
Сумма: 1
""".strip()
    result = parse_message(text)
    assert result is not None
    assert result.invoice_number == "3722"
