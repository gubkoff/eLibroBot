"""
Правила накладной: преобразование сырых данных взвешивания в `InvoiceData`.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from parser.models import WeighingData
from report.invoice_models import InvoiceData

__all__ = ["weighing_to_invoice"]


def _compute_nds_from_amount(amount: Decimal) -> Decimal:
    return (amount / Decimal("116") * Decimal("16")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def weighing_to_invoice(data: WeighingData, *, supplier_default: str) -> InvoiceData:
    """
    Собирает ``InvoiceData`` для PDF и бизнес-логики из результата парсера.

    ``supplier_default`` — поставщик по умолчанию, если в сообщении не задан свой.
    """
    adj = data.adjusted_netto_kg or None
    if adj:
        netto_final = int(adj)
        netto_src = "adjusted"
    else:
        netto_final = data.netto_kg
        netto_src = "raw"

    if adj:
        brutto_final = data.tara_kg + int(adj)
        brutto_src = "tara_plus_adjusted"
    else:
        brutto_final = data.brutto_kg
        brutto_src = "raw"

    amount = data.amount
    nds = _compute_nds_from_amount(amount)

    buyer_parts: list[str] = []
    if data.counterparty:
        buyer_parts.append(data.counterparty)
    if data.plate_number:
        buyer_parts.append(f"номер авто {data.plate_number}")
    buyer_line = ", ".join(buyer_parts)

    return InvoiceData(
        weighing_number=data.weighing_number,
        invoice_number=data.invoice_number,
        plate_number=data.plate_number,
        cargo=data.cargo,
        counterparty=data.counterparty,
        weighing_datetime=data.weighing_datetime,
        message_sent_at=data.message_sent_at,
        user=data.user or "",
        tara_kg=data.tara_kg,
        brutto_kg_raw=data.brutto_kg,
        netto_kg_raw=data.netto_kg,
        adjusted_netto_kg=adj,
        netto_kg_final=netto_final,
        brutto_kg_final=brutto_final,
        netto_source=netto_src,
        brutto_source=brutto_src,
        price_per_ton_raw=data.price_per_ton,
        amount_raw=amount,
        amount_calc=amount,
        amount_final=amount,
        amount_source="raw",
        nds_amount=nds,
        supplier_name=(supplier_default or "").strip(),
        buyer_line=buyer_line,
    )
