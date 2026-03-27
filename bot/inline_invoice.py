from __future__ import annotations

from typing import Literal, Optional, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

InvoiceMode = Literal["normal", "additional"]
CallbackPayload = Tuple[int, int, InvoiceMode]
CALLBACK_PREFIX = "invoice"
CALLBACK_SEPARATOR = ":"


def build_invoice_keyboard(
    *,
    source_chat_id: int,
    source_message_id: int,
    mode: InvoiceMode,
) -> InlineKeyboardMarkup:
    """
    Inline-кнопки режима накладной под сообщением с PDF.

    Внутренние режимы: normal/additional
    Текст для пользователя: Стандарт/Дозагрузка
    """
    standard_style = "primary" if mode == "normal" else None
    additional_style = "primary" if mode == "additional" else None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Стандарт",
                    callback_data=_build_callback_data(
                        source_chat_id=source_chat_id,
                        source_message_id=source_message_id,
                        mode="normal",
                    ),
                    style=standard_style,
                ),
                InlineKeyboardButton(
                    text="Дозагрузка",
                    callback_data=_build_callback_data(
                        source_chat_id=source_chat_id,
                        source_message_id=source_message_id,
                        mode="additional",
                    ),
                    style=additional_style,
                ),
            ],
        ]
    )


def _build_callback_data(
    *,
    source_chat_id: int,
    source_message_id: int,
    mode: InvoiceMode,
) -> str:
    return (
        f"{CALLBACK_PREFIX}{CALLBACK_SEPARATOR}{source_chat_id}"
        f"{CALLBACK_SEPARATOR}{source_message_id}{CALLBACK_SEPARATOR}{mode}"
    )


def parse_invoice_callback(data: str) -> Optional[CallbackPayload]:
    """
    invoice:{source_chat_id}:{source_message_id}:{mode}
    где mode = normal|additional (целевой режим после нажатия).
    """
    if not data:
        return None
    parts = data.split(CALLBACK_SEPARATOR)
    if len(parts) != 4 or parts[0] != CALLBACK_PREFIX:
        return None
    try:
        source_chat_id = int(parts[1])
        source_message_id = int(parts[2])
    except ValueError:
        return None
    mode_raw = parts[3]
    if mode_raw not in ("normal", "additional"):
        return None
    mode: InvoiceMode = mode_raw
    return (source_chat_id, source_message_id, mode)

