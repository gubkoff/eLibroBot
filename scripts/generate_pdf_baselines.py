#!/usr/bin/env python3
"""
Генерирует эталонные PDF для регрессии вёрстки (план V3, шаг 002).
  - docs/baseline_pdf_short.pdf — компактный контент, обычно 1 стр., 2 блока, линия разреза.
  - docs/baseline_pdf_long.pdf — очень длинное название груза → fallback на 2 страницы без линии на 2-й.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS = PROJECT_ROOT / "docs"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.models import WeighingData
from report import CalculationResult, build_pdf


def _write_pdf(data: WeighingData, dest: Path) -> None:
    result = CalculationResult(
        total=data.amount,
        by_category={data.cargo[:80]: data.amount},
    )
    tmp = build_pdf(result, records=[], weighing=data)
    try:
        dest.write_bytes(Path(tmp).read_bytes())
    finally:
        Path(tmp).unlink(missing_ok=True)


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    short = WeighingData(
        weighing_number="3722",
        plate_number="851EM02",
        tara_kg=18360,
        brutto_kg=45180,
        netto_kg=26820,
        cargo="Кузнецкий 0-300",
        counterparty="По контракту",
        invoice_number="3722",
        price_per_ton=Decimal("16000"),
        amount=Decimal("429120"),
        weighing_datetime=datetime(2026, 3, 14, 9, 32, 4),
        user="Руфина",
        message_sent_at=datetime(2026, 3, 14, 9, 32, 4),
        adjusted_netto_kg=0,
    )
    _write_pdf(short, DOCS / "baseline_pdf_short.pdf")

    # Длинный груз + много «слов с большой буквы» → переносы и высота строки товара;
    # повтор блока увеличивает шанс переполнения half-frame → режим 2 страницы.
    # Достаточно высокий блок «Товар», чтобы один экземпляр накладной влезал в полную
    # страницу, а два на одной — нет (fallback на 2 страницы). Не раздувать до > ~1 страницы.
    chunk = (
        "Шубар Высокозольный Кузнецкий Грохот Уголь Сорт Партия Марка Секция "
    )
    # ~3× короче «опасного» порога: блок влезает на полную страницу, но не в половину (2 блока → 2 стр.)
    long_cargo = (chunk * 3).strip()
    long = WeighingData(
        weighing_number="9999",
        plate_number="999XX00",
        tara_kg=20000,
        brutto_kg=50000,
        netto_kg=30000,
        cargo=long_cargo,
        counterparty="ООО Длинный контрагент для baseline регрессии документа",
        invoice_number="9999",
        price_per_ton=Decimal("25000"),
        amount=Decimal("750000"),
        weighing_datetime=datetime(2026, 1, 1, 12, 0, 0),
        user="Тест",
        message_sent_at=datetime(2026, 1, 1, 12, 0, 0),
        adjusted_netto_kg=0,
    )
    _write_pdf(long, DOCS / "baseline_pdf_long.pdf")

    print("OK:", DOCS / "baseline_pdf_short.pdf")
    print("OK:", DOCS / "baseline_pdf_long.pdf")


if __name__ == "__main__":
    main()
