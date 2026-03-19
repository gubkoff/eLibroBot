"""
Хендлер сообщений из группы-источника: парсинг → расчёт → PDF → отправка в группу-получатель.
"""

import logging
import os
from typing import Optional

from aiogram import Router
from aiogram.types import FSInputFile, Message

from config import get_settings
from parser import WeighingData, parse_message
from report import CalculationResult, build_pdf

from bot.filters import source_group_message

logger = logging.getLogger(__name__)

router = Router()


@router.message(source_group_message)
async def pipeline_handler(message: Message) -> None:
    """
    Пайплайн по сообщению из группы-источника:
    parse_message (WeighingData) → формирование накладной → build_pdf → отправка в группу-получатель.
    Регистрируется с фильтром source_group_message, поэтому сюда попадают только
    текстовые сообщения из SOURCE_GROUP_ID(S) (не команды).
    """
    settings = get_settings()
    pdf_path = None
    try:
        data: Optional[WeighingData] = parse_message(message.text or "")
        if data is None:
            await message.reply("Не удалось разобрать данные взвешивания. Проверьте формат сообщения.")
            return

        pdf_path = build_pdf(
            CalculationResult(total=data.amount, by_category={data.cargo: data.amount}),
            records=[],  # данные берутся из weighing
            weighing=data,
        )
        doc_number = data.invoice_number or data.weighing_number
        caption = f"Накладная № {doc_number} на сумму {data.amount}"
        await message.bot.send_document(
            chat_id=settings.TARGET_GROUP_ID,
            document=FSInputFile(pdf_path, filename=f"nakladn_{doc_number}.pdf"),
            caption=caption,
        )
    except Exception as e:
        logger.exception("Ошибка в пайплайне отчёта: %s", e)
        try:
            err_text = str(e)
            if "not enough rights" in err_text.lower() or "send documents" in err_text.lower():
                await message.reply(
                    "Ошибка: у бота нет прав отправлять сообщения в группу-получатель. "
                    "Сделайте бота администратором группы-получателя с правом «Отправка сообщений»."
                )
            else:
                await message.reply(
                    "Ошибка при формировании отчёта:\n"
                    f"{err_text}"
                )
        except Exception:
            logger.warning(
                "Не удалось отправить сообщение об ошибке пользователю (chat_id=%s, message_id=%s).",
                getattr(message.chat, "id", None),
                getattr(message, "message_id", None),
                exc_info=True,
            )
    finally:
        if pdf_path is not None and os.path.isfile(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError as err:
                logger.warning("Не удалось удалить временный PDF %s: %s", pdf_path, err)
