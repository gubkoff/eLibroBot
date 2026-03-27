"""
Общий пайплайн: текст из группы-источника → парсинг → PDF → отправка ботом в группу-получатель.
Используется и из aiogram (Bot API), и из Telethon (MTProto), если включён чтение через пользователя.
"""

from __future__ import annotations

import logging
import os
from typing import Awaitable, Callable, Optional

from aiogram import Bot
from aiogram.types import FSInputFile

from config import get_settings
from parser import WeighingData, parse_message
from report import build_pdf
from report.weighing_print_data import WeighingPrintData
from bot.inline_invoice import build_invoice_keyboard

logger = logging.getLogger(__name__)

OptionalReply = Optional[Callable[[str], Awaitable[None]]]


async def run_weighing_pipeline(
    *,
    text: str,
    source_chat_id: int,
    source_message_id: int | None = None,
    enable_inline_buttons: bool = False,
    source_chat_title: Optional[str],
    bot: Bot,
    reply: OptionalReply = None,
) -> None:
    """
    :param reply: если задан (aiogram), ошибки/парсинг уходят ответом в чат; для MTProto обычно None — только лог.
    """
    settings = get_settings()
    logger.info(
        "Получено сообщение из чата id=%s title=%r",
        source_chat_id,
        source_chat_title,
    )
    pdf_path: Optional[str] = None
    try:
        data: Optional[WeighingData] = parse_message(text or "")
        if data is None:
            msg = (
                "Не удалось разобрать данные взвешивания. Проверьте формат сообщения."
            )
            if reply:
                await reply(msg)
            else:
                logger.info(
                    "Парсер не распознал сообщение (chat_id=%s), пропуск.",
                    source_chat_id,
                )
            return

        pdf_path = build_pdf(WeighingPrintData.from_weighing(data))
        doc_number = data.invoice_number or data.weighing_number
        caption = f"Накладная № {doc_number} на сумму {data.amount}"
        reply_markup = None
        if source_message_id is not None and enable_inline_buttons:
            reply_markup = build_invoice_keyboard(
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
                mode="normal",
            )
        await bot.send_document(
            chat_id=settings.TARGET_GROUP_ID,
            document=FSInputFile(pdf_path, filename=f"nakladn_{doc_number}.pdf"),
            caption=caption,
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.exception("Ошибка в пайплайне отчёта: %s", e)
        err_text = str(e)
        if reply:
            try:
                if (
                    "not enough rights" in err_text.lower()
                    or "send documents" in err_text.lower()
                ):
                    await reply(
                        "Ошибка: у бота нет прав отправлять сообщения в группу-получатель. "
                        "Сделайте бота администратором группы-получателя с правом «Отправка сообщений»."
                    )
                else:
                    await reply(
                        "Ошибка при формировании отчёта:\n" + err_text
                    )
            except Exception:
                logger.warning(
                    "Не удалось отправить сообщение об ошибке (chat_id=%s).",
                    source_chat_id,
                    exc_info=True,
                )
        else:
            logger.warning(
                "Ошибка пайплайна без reply (MTProto): chat_id=%s — %s",
                source_chat_id,
                err_text,
            )
    finally:
        if pdf_path is not None and os.path.isfile(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError as err:
                logger.warning("Не удалось удалить временный PDF %s: %s", pdf_path, err)
