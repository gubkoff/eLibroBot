"""
Хендлер сообщений из группы-источника: парсинг → расчёт → PDF → отправка в группу-получатель.
"""

import logging
import os

from aiogram import Router
from aiogram.types import FSInputFile, Message

from config import get_settings
from parser import parse_message
from report import build_pdf, calculate

from bot.filters import source_group_message

logger = logging.getLogger(__name__)

router = Router()


@router.message(source_group_message)
async def pipeline_handler(message: Message) -> None:
    """
    Пайплайн по сообщению из группы-источника:
    parse_message → calculate → build_pdf → send_document → удаление файла.
    Регистрируется с фильтром source_group_message, поэтому сюда попадают только
    текстовые сообщения из SOURCE_GROUP_ID (не команды).
    """
    settings = get_settings()
    pdf_path = None
    try:
        records = parse_message(message.text or "")
        if not records:
            await message.reply("Нет данных для отчёта. Формат строки: дата сумма категория (например 2025-02-26 100 продукты).")
            return
        result = calculate(records)
        pdf_path = build_pdf(result, records=records)
        caption = f"Отчёт по сообщению ({len(records)} записей, итого {result.total})"
        await message.bot.send_document(
            chat_id=settings.TARGET_GROUP_ID,
            document=FSInputFile(pdf_path, filename="report.pdf"),
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
                await message.reply(f"Ошибка при формировании отчёта: {err_text}")
        except Exception:
            pass
    finally:
        if pdf_path is not None and os.path.isfile(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError as err:
                logger.warning("Не удалось удалить временный PDF %s: %s", pdf_path, err)
