from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class WeighingData:
    """Структурированные данные одного взвешивания из сообщения весовой."""

    weighing_number: str  # номер взвешивания из заголовка "ВЗВЕШИВАНИЕ № ..."
    plate_number: str  # номер авто
    tara_kg: int
    brutto_kg: int
    netto_kg: int
    cargo: str
    counterparty: str
    invoice_number: str
    price_per_ton: Decimal
    amount: Decimal
    weighing_datetime: Optional[datetime]
    user: str
    message_sent_at: Optional[datetime]