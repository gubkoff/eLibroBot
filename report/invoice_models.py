"""
Доменная модель данных для PDF-накладной (после парсера и правил).

Отделяет «сырьё» весовой, вычисленные поля и метаданные источников.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

# Источники для прозрачности (без Enum — меньше импортов у потребителей)
AmountSource = Literal["raw", "calc"]
NettoSource = Literal["raw", "adjusted"]
BruttoSource = Literal["raw", "tara_plus_adjusted"]


@dataclass
class InvoiceData:
    """Данные для генерации накладной: идентификация, веса, деньги, НДС, предупреждения."""

    # --- Идентификация и реквизиты текста
    weighing_number: str
    invoice_number: str
    plate_number: str
    cargo: str
    counterparty: str
    weighing_datetime: Optional[datetime] = None
    message_sent_at: Optional[datetime] = None
    user: str = ""

    # --- Веса, кг (как в сообщении)
    tara_kg: int = 0
    brutto_kg_raw: int = 0
    netto_kg_raw: int = 0
    adjusted_netto_kg: Optional[int] = None

    # --- Веса для отображения в накладной
    netto_kg_final: int = 0
    brutto_kg_final: int = 0
    netto_source: NettoSource = "raw"
    brutto_source: BruttoSource = "raw"

    # --- Деньги
    price_per_ton_raw: Decimal = field(default_factory=lambda: Decimal("0"))
    amount_raw: Decimal = field(default_factory=lambda: Decimal("0"))
    amount_calc: Decimal = field(default_factory=lambda: Decimal("0"))
    amount_final: Decimal = field(default_factory=lambda: Decimal("0"))
    amount_source: AmountSource = "raw"
    amount_mismatch: bool = False
    amount_delta: Decimal = field(default_factory=lambda: Decimal("0"))

    # --- НДС (база обычно = amount_final)
    nds_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    total_for_nds: Optional[Decimal] = None

    # --- Печать реквизитов (вынести из PDF)
    supplier_name: str = ""
    buyer_line: str = ""

    warnings: list[str] = field(default_factory=list)

    def effective_total_for_nds(self) -> Decimal:
        """База для расчёта НДС: явно заданная или amount_final."""
        if self.total_for_nds is not None:
            return self.total_for_nds
        return self.amount_final
