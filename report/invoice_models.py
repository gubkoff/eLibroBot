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

    # Номер взвешивания из заголовка сообщения весовой (внутренний ID сессии).
    weighing_number: str
    # Номер накладной для шапки документа (может совпадать с weighing_number).
    invoice_number: str
    # Госномер ТС из сообщения; участвует в контексте сделки и в строке покупателя.
    plate_number: str
    # Наименование груза/товара для таблицы позиций в PDF.
    cargo: str
    # Контрагент как в сыром сообщении (канон источника; buyer_line может быть производной строкой).
    counterparty: str
    # Дата/время взвешивания с весов (для шапки «от … г.»).
    weighing_datetime: Optional[datetime] = None
    # Момент получения сообщения в Telegram — аудит и таймлайн, не обязательно для печати.
    message_sent_at: Optional[datetime] = None
    # Пользователь/отправитель в источнике (поддержка, отчёты; в PDF обычно не идёт).
    user: str = ""

    # --- Веса, кг (как в сообщении — для сверки и споров)

    # Тара в килограммах из сообщения; используется в таблице накладной.
    tara_kg: int = 0
    # Брутто из текста до применения правил (доказательная база).
    brutto_kg_raw: int = 0
    # Нетто из текста до применения правил (доказательная база).
    netto_kg_raw: int = 0
    # Скорректированное нетто из сообщения, если указано; иначе None — берётся сырое нетто.
    adjusted_netto_kg: Optional[int] = None

    # --- Веса для отображения в накладной (после правил)

    # Нетто, которое печатается в PDF.
    netto_kg_final: int = 0
    # Брутто, которое печатается в PDF.
    brutto_kg_final: int = 0
    # Откуда взялось итоговое нетто: сырое из сообщения или скорректированное.
    netto_source: NettoSource = "raw"
    # Откуда взялось итоговое брутто: из сообщения или тара + скорректированное нетто.
    brutto_source: BruttoSource = "raw"

    # --- Деньги

    # Цена за тонну из сообщения (колонка «Цена» в таблице).
    price_per_ton_raw: Decimal = field(default_factory=lambda: Decimal("0"))
    # Сумма из текста сообщения (до выбора финальной суммы правилами).
    amount_raw: Decimal = field(default_factory=lambda: Decimal("0"))
    # Сумма, пересчитанная по весу и цене (контроль против amount_raw).
    amount_calc: Decimal = field(default_factory=lambda: Decimal("0"))
    # Итоговая сумма документа: итоги, пропись, база НДС по умолчанию.
    amount_final: Decimal = field(default_factory=lambda: Decimal("0"))
    # Источник финальной суммы: взяли из текста или из расчёта.
    amount_source: AmountSource = "raw"
    # True, если raw и расчётные суммы расходятся (удобный флаг для UI без пересчёта).
    amount_mismatch: bool = False
    # Величина расхождения сумм на момент формирования снимка (для текстов и логов).
    amount_delta: Decimal = field(default_factory=lambda: Decimal("0"))

    # --- НДС (база обычно = amount_final)

    # Сумма НДС для блока «В том числе НДС» в PDF.
    nds_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    # Иная база для НДС, если по бизнес-правилам она не совпадает с amount_final; None = не задано.
    total_for_nds: Optional[Decimal] = None

    # --- Печать реквизитов (вынести из PDF-слоя)

    # Наименование поставщика для блока «Поставщик» (часто из настроек/дефолта).
    supplier_name: str = ""
    # Одна строка «Покупатель» для верстки; может совпадать с контрагентом+авто из правил.
    buyer_line: str = ""

    # Предупреждения правил без отмены выпуска документа (бот, логи).
    warnings: list[str] = field(default_factory=list)

    def effective_total_for_nds(self) -> Decimal:
        """База для расчёта/проверки НДС: явно заданная total_for_nds или amount_final."""
        if self.total_for_nds is not None:
            return self.total_for_nds
        return self.amount_final
