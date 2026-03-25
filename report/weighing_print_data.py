from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parser.models import WeighingData


DEFAULT_SUPPLIER = 'Товарищество с ограниченной ответственностью "КазТим Комир"'
DEFAULT_UNIT = "тонна"


class WeighingPrintData(BaseModel):
    """
    Полный набор данных для печати одной накладной в PDF.

    PDF-слой должен зависеть только от этого контракта и не «догадываться» о значениях из других моделей.
    """

    model_config = ConfigDict(extra="forbid")

    # Header
    title: str = "Расходная накладная"
    doc_number: str
    doc_date: str  # DD.MM.YYYY

    # Parties
    supplier: str = DEFAULT_SUPPLIER
    buyer: str = ""

    # Items (single row)
    cargo: str
    unit: str = DEFAULT_UNIT
    tara_kg: int
    netto_kg: int
    brutto_kg: int
    adjusted_netto_kg: int = 0
    price_per_ton: Decimal
    amount: Decimal

    # Totals
    total: Decimal
    nds_amount: Decimal
    items_count: int = 1

    # Layout
    duplicate_on_one_page: bool = True

    @field_validator(
        "title",
        "doc_number",
        "doc_date",
        "supplier",
        "cargo",
        "unit",
    )
    @classmethod
    def _strip_non_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Field must be non-empty")
        return v

    @field_validator("buyer")
    @classmethod
    def _strip_buyer(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("tara_kg", "netto_kg", "brutto_kg", "adjusted_netto_kg", "items_count")
    @classmethod
    def _non_negative_ints(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Must be >= 0")
        return v

    @classmethod
    def from_weighing(
        cls,
        weighing: WeighingData,
        *,
        title: str = "Расходная накладная",
        supplier: str = DEFAULT_SUPPLIER,
        duplicate_on_one_page: bool = True,
        nds_override: Optional[Decimal] = None,
    ) -> "WeighingPrintData":
        doc_number = (weighing.invoice_number or weighing.weighing_number or "").strip()
        doc_date = ""
        if weighing.weighing_datetime is not None:
            doc_date = weighing.weighing_datetime.strftime("%d.%m.%Y")
        elif weighing.message_sent_at is not None:
            doc_date = weighing.message_sent_at.strftime("%d.%m.%Y")
        else:
            doc_date = date.today().strftime("%d.%m.%Y")

        buyer_parts: list[str] = []
        if weighing.counterparty:
            buyer_parts.append(weighing.counterparty)
        if weighing.plate_number:
            buyer_parts.append(f"номер авто {weighing.plate_number}")
        buyer = ", ".join([p.strip() for p in buyer_parts if p.strip()])

        total = weighing.amount
        if nds_override is not None:
            nds_amount = nds_override
        else:
            nds_amount = (total / Decimal("116") * Decimal("16")).quantize(Decimal("0.01"))

        return cls(
            title=title,
            doc_number=doc_number,
            doc_date=doc_date,
            supplier=supplier,
            buyer=buyer,
            cargo=weighing.cargo,
            unit=DEFAULT_UNIT,
            tara_kg=weighing.tara_kg,
            netto_kg=weighing.netto_kg,
            brutto_kg=weighing.brutto_kg,
            adjusted_netto_kg=weighing.adjusted_netto_kg or 0,
            price_per_ton=weighing.price_per_ton,
            amount=weighing.amount,
            total=total,
            nds_amount=nds_amount,
            items_count=1,
            duplicate_on_one_page=duplicate_on_one_page,
        )

