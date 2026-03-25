"""Smoke-тесты генерации PDF на крайних кейсах верстки."""

from datetime import datetime
from decimal import Decimal

from parser.models import WeighingData
from report.pdf_builder import build_pdf
from report.weighing_print_data import WeighingPrintData


def _make_weighing(*, cargo: str, counterparty: str, amount: Decimal) -> WeighingData:
    return WeighingData(
        weighing_number="SMOKE-1",
        plate_number="A123BC01",
        tara_kg=18360,
        brutto_kg=45180,
        netto_kg=26820,
        cargo=cargo,
        counterparty=counterparty,
        invoice_number="SMK-001",
        price_per_ton=Decimal("16000"),
        amount=amount,
        weighing_datetime=datetime(2026, 3, 14, 9, 32, 4),
        user="Тестер",
        message_sent_at=datetime(2026, 3, 14, 9, 32, 5),
        adjusted_netto_kg=0,
    )


def test_build_pdf_smoke_long_text_fields() -> None:
    """Длинные cargo/counterparty не должны ронять верстку."""
    cargo = (
        "Строительный Песок Мытый Фракция 0-5 Партия А2026 "
        "Длинное Наименование Для Проверки Переносов"
    )
    counterparty = (
        "ТОО Очень Длинный Контрагент для проверки переноса строк в реквизитах "
        "и устойчивости таблицы покупателя в PDF макете"
    )
    weighing = _make_weighing(cargo=cargo, counterparty=counterparty, amount=Decimal("429120"))
    pdf_path = build_pdf(
        WeighingPrintData.from_weighing(weighing, duplicate_on_one_page=True),
    )
    try:
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000
    finally:
        pdf_path.unlink(missing_ok=True)


def test_build_pdf_smoke_large_block_with_split_fallback() -> None:
    """
    Тяжелый кейс: очень длинные поля и большая сумма (длинная сумма прописью).
    Проверяем, что build_pdf отрабатывает и выдаёт PDF даже при fallback разбиении.
    """
    # Используем длинные НО строчные слова: иначе format_cargo_for_cell вставляет <br/> перед
    # каждым словом с заглавной буквы и можно получить гарантированно невмещаемую строку.
    cargo = " ".join(["оченьдлинныйтовар"] * 28)
    counterparty = " ".join(["оченьдлинныйконтрагент"] * 35)
    amount = Decimal("99999999.99")
    weighing = _make_weighing(cargo=cargo, counterparty=counterparty, amount=amount)
    pdf_path = build_pdf(
        WeighingPrintData.from_weighing(weighing, duplicate_on_one_page=True),
    )
    try:
        assert pdf_path.exists()
        # Для тяжелого кейса ожидаем заметно не-пустой PDF.
        assert pdf_path.stat().st_size > 1500
    finally:
        pdf_path.unlink(missing_ok=True)

