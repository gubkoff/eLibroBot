#!/usr/bin/env python3
"""
Вспомогательный скрипт для локальной генерации накладной в PDF
без запуска Telegram-бота. Берёт один пример WeighingData и
создаёт debug_nakladnaya.pdf в корне проекта.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.models import WeighingData
from report import build_pdf_invoice, weighing_to_invoice

_DEFAULT_SUPPLIER = 'Товарищество с ограниченной ответственностью "КазТим Комир"'


def main() -> None:
    # Пример данных взвешивания (можно менять под реальные значения)
    data = WeighingData(
        weighing_number="3722",
        plate_number="851EM02",
        tara_kg=18360,
        brutto_kg=45180,
        netto_kg=4444445,
        cargo="Шубар(высокозольный) 0-40 Кузнецкий 0-300",
        counterparty="По контракту",
        invoice_number="3722",
        price_per_ton=Decimal("16000"),
        amount=Decimal("99999999"),
        amount_raw=Decimal("99999999"),
        weighing_datetime=datetime(2026, 3, 14, 9, 32, 4),
        user="Руфина",
        message_sent_at=datetime(2026, 3, 14, 9, 32, 4),
        adjusted_netto_kg=0,
    )

    inv = weighing_to_invoice(data, supplier_default=_DEFAULT_SUPPLIER)
    tmp_pdf = build_pdf_invoice(inv)

    out_path = Path("debug_nakladnaya.pdf")
    out_path.write_bytes(Path(tmp_pdf).read_bytes())
    print(f"PDF сохранён в {out_path.resolve()}")


if __name__ == "__main__":
    main()

