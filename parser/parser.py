import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from parser.models import WeighingData

logger = logging.getLogger(__name__)

# Нормализованные ключи → внутренние имена полей WeighingData
KEY_ALIASES: dict[str, str] = {
    # номер авто
    "номер": "plate_number",
    "номер авто": "plate_number",
    "авто": "plate_number",
    # масса
    "тара": "tara_kg",
    "брутто": "brutto_kg",
    "нетто": "netto_kg",
    "вес с корректировкой": "adjusted_netto_kg",
    # груз
    "груз": "cargo",
    "товар": "cargo",
    "материал": "cargo",
    # контрагент / покупатель
    "контрагент": "counterparty",
    "покупатель": "counterparty",
    "клиент": "counterparty",
    # накладная
    "накладная": "invoice_number",
    # цена и сумма
    "цена за тонну": "price_per_ton",
    "цена/т": "price_per_ton",
    "цена, тг/т": "price_per_ton",
    "сумма, тг": "amount",
    "сумма": "amount",
    "сумма, kzt": "amount",
    # даты и пользователь
    "дата взвешивания": "weighing_datetime",
    "дата": "weighing_datetime",
    "дата/время": "weighing_datetime",
    "пользователь": "user",
    "сообщение отправлено": "message_sent_at",
}


def _parse_int_field(value: str) -> Optional[int]:
    """Парсит целое число, допускает пробелы как разделители тысяч."""
    s = value.replace(" ", "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        logger.warning("Не удалось распарсить целое число: %r", value)
        return None


def _parse_decimal_field(value: str) -> Optional[Decimal]:
    """Парсит Decimal, допускает пробелы и запятую как разделитель."""
    s = value.replace(" ", "").replace(",", ".").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        logger.warning("Не удалось распарсить Decimal: %r", value)
        return None


def _parse_dt(value: str) -> Optional[datetime]:
    """Парсит дату/время в формате YYYY-MM-DD HH:MM:SS."""
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.warning("Не удалось распарсить дату/время: %r", value)
        return None


def parse_message(text: str) -> Optional[WeighingData]:
    """
    Парсит сообщение формата "ВЗВЕШИВАНИЕ № ..." в структуру WeighingData.

    Ожидаемый пример:

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
      Сообщение отправлено 2026-03-14 09:32:04
    """
    if not text or not text.strip():
        return None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    # Заголовок "ВЗВЕШИВАНИЕ № 3722"
    weighing_number = ""
    m = re.search(r"ВЗВЕШИВАНИЕ\s*№\s*([0-9A-Za-z\-]+)", lines[0])
    if m:
        weighing_number = m.group(1)

    raw_fields: dict[str, str] = {}

    # Остальные строки "Ключ: значение"
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        raw_fields[key.strip()] = value.strip()

    # Нормализация ключей и применение словаря синонимов
    normalized: dict[str, str] = {}
    for raw_key, raw_value in raw_fields.items():
        key_norm = raw_key.strip().lower()
        # Убираем хвосты вида ", тг", ", kzt"
        key_norm = key_norm.replace(", тг", "").replace(", kzt", "").strip()
        field_name = KEY_ALIASES.get(key_norm)
        if not field_name:
            logger.debug("Неизвестный ключ поля взвешивания: %r", raw_key)
            continue
        normalized[field_name] = raw_value.strip()

    plate_number = normalized.get("plate_number", "")
    tara_kg = _parse_int_field(normalized.get("tara_kg", "")) or 0
    brutto_kg = _parse_int_field(normalized.get("brutto_kg", "")) or 0
    netto_kg = _parse_int_field(normalized.get("netto_kg", "")) or 0
    adjusted_netto_kg = _parse_int_field(normalized.get("adjusted_netto_kg", "")) or 0
    cargo = normalized.get("cargo", "")
    counterparty = normalized.get("counterparty", "")

    invoice_raw = normalized.get("invoice_number", "")
    # Убираем возможный префикс "№"
    invoice_number = invoice_raw.replace("№", "").strip() if invoice_raw else ""

    price_per_ton = _parse_decimal_field(normalized.get("price_per_ton", "")) or Decimal("0")
    amount = _parse_decimal_field(normalized.get("amount", "")) or Decimal("0")
    weight_for_amount_kg = adjusted_netto_kg or netto_kg
    if price_per_ton and weight_for_amount_kg:
        amount = (
            (Decimal(weight_for_amount_kg) / Decimal("1000")) * price_per_ton
        ).quantize(Decimal("0.01"))

    weighing_datetime = _parse_dt(normalized.get("weighing_datetime", "")) if "weighing_datetime" in normalized else None
    message_sent_at = _parse_dt(normalized.get("message_sent_at", "")) if "message_sent_at" in normalized else None

    user = normalized.get("user", "")

    return WeighingData(
        weighing_number=weighing_number,
        plate_number=plate_number,
        tara_kg=tara_kg,
        brutto_kg=brutto_kg,
        netto_kg=netto_kg,
        cargo=cargo,
        counterparty=counterparty,
        invoice_number=invoice_number,
        price_per_ton=price_per_ton,
        amount=amount,
        weighing_datetime=weighing_datetime,
        user=user,
        message_sent_at=message_sent_at,
        adjusted_netto_kg=adjusted_netto_kg,
    )


def weighing_to_array(data: WeighingData) -> list:
    """
    Преобразует WeighingData в массив значений в фиксированном порядке.

    Этот массив удобно использовать при построении таблиц или шаблонов PDF.
    Порядок:
      [номер взвешивания, номер авто, тара, брутто, нетто,
       груз, контрагент, номер накладной, цена за тонну, сумма,
       дата взвешивания (строкой), пользователь, дата отправки сообщения (строкой)]
    """
    weigh_dt = (
        data.weighing_datetime.strftime("%Y-%m-%d %H:%M:%S")
        if data.weighing_datetime
        else ""
    )
    sent_dt = (
        data.message_sent_at.strftime("%Y-%m-%d %H:%M:%S")
        if data.message_sent_at
        else ""
    )
    return [
        data.weighing_number,
        data.plate_number,
        data.tara_kg,
        data.brutto_kg,
        data.netto_kg,
        data.cargo,
        data.counterparty,
        data.invoice_number,
        str(data.price_per_ton),
        str(data.amount),
        weigh_dt,
        data.user,
        sent_dt,
    ]
