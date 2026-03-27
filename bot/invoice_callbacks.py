from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, FSInputFile, InputMediaDocument

from bot.inline_invoice import CALLBACK_PREFIX, build_invoice_keyboard, parse_invoice_callback
from bot.mtproto_reader import (
    fetch_source_message_text,
    find_previous_weighing_same_plate,
    get_mtproto_client,
)
from parser import WeighingData, parse_message
from report import build_pdf
from report.weighing_print_data import WeighingPrintData

logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
async def invoice_button_handler(callback: CallbackQuery) -> None:
    payload = parse_invoice_callback(callback.data or "")
    if payload is None:
        return

    if callback.message is None:
        await callback.answer("Нет сообщения для обновления.", show_alert=True)
        return

    source_chat_id, source_message_id, mode = payload

    bot: Bot = callback.message.bot
    target_chat_id = callback.message.chat.id
    target_message_id = callback.message.message_id

    await callback.answer()

    pdf_path: Optional[str] = None
    try:
        client = get_mtproto_client()
        if client is None:
            await callback.answer("MTProto не запущен на сервере.", show_alert=True)
            return

        source_text = await fetch_source_message_text(
            chat_id=source_chat_id,
            message_id=source_message_id,
        )
        if not source_text:
            await callback.answer("Не удалось прочитать исходное сообщение.", show_alert=True)
            return

        current_weighing: Optional[WeighingData] = parse_message(source_text)
        if current_weighing is None:
            await callback.answer("Не удалось распознать текущие данные взвешивания.", show_alert=True)
            return

        previous_weighing: Optional[WeighingData] = None
        if mode == "additional":
            previous_weighing = await find_previous_weighing_same_plate(
                chat_id=source_chat_id,
                current_message_id=source_message_id,
                current_plate_number=current_weighing.plate_number,
            )
            if previous_weighing is None:
                await callback.answer("Не найдено предыдущее взвешивание для дозагрузки.", show_alert=True)
                return

        print_data = WeighingPrintData.from_weighing_mode(
            current_weighing,
            mode=mode,
            previous_weighing=previous_weighing,
        )

        pdf_path_path = build_pdf(print_data)
        pdf_path = str(pdf_path_path)

        doc_number = print_data.doc_number
        new_caption = f"Накладная № {doc_number} на сумму {print_data.amount}"

        new_keyboard = build_invoice_keyboard(
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            mode=mode,
        )

        media = InputMediaDocument(
            media=FSInputFile(pdf_path, filename=f"nakladn_{doc_number}.pdf"),
        )

        # 1) Обновляем документ (media) + клавиатуру
        await bot.edit_message_media(
            media=media,
            chat_id=target_chat_id,
            message_id=target_message_id,
            reply_markup=new_keyboard,
        )

        # 2) Обновляем caption (так как для additional меняется сумма/НДС)
        await bot.edit_message_caption(
            chat_id=target_chat_id,
            message_id=target_message_id,
            caption=new_caption,
            reply_markup=new_keyboard,
        )

        await callback.answer("Обновлено")
    except Exception:
        logger.exception("Ошибка обновления накладной по callback")
        await callback.answer("Не удалось пересобрать накладную.", show_alert=True)
    finally:
        if pdf_path and os.path.isfile(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

