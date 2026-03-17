"""
eLibroCargoReportBot — бот для расчётов и PDF-отчётов по сообщениям из группы.
Точка входа: запуск long polling.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import get_settings
from parser import parse_message

from bot import router as report_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Ответ на команду /start."""
    name = message.from_user.full_name or "пользователь"
    await message.answer(
        f"Привет, {html.bold(name)}! Я бот {html.bold('eLibroCargoReportBot')}. "
        "Отправь структурированное сообщение в группу-источник — в группу-получатель уйдёт PDF-отчёт."
    )


@dp.message(Command("parse"))
async def cmd_parse(message: Message) -> None:
    """
    Команда для проверки парсера: текст формата «ВЗВЕШИВАНИЕ № …» → структура WeighingData.
    """
    parts = message.text.split(maxsplit=1)
    text = parts[1].strip() if len(parts) > 1 else ""
    if not text:
        await message.answer(
            "Отправьте текст для разбора после команды.\n\n"
            "Формат: первая строка <code>ВЗВЕШИВАНИЕ № номер</code>, далее строки <code>Ключ: значение</code>.\n"
            "Ключи: Номер, Тара, Брутто, Нетто, Груз, Контрагент, Накладная, Цена за тонну, Сумма (тг), "
            "Дата взвешивания, Пользователь, Сообщение отправлено.\n\n"
            "Пример:\n<code>/parse ВЗВЕШИВАНИЕ № 3722\nНомер: 851EM02\nТара: 18360\nБрутто: 45180\n"
            "Нетто: 26820\nГруз: Уголь\nСумма, тг: 429120</code>"
        )
        return
    data = parse_message(text)
    if data is None:
        await message.answer("Не удалось разобрать данные взвешивания. Проверьте формат (ВЗВЕШИВАНИЕ № … и ключи со значениями).")
        return
    dt_fmt = "%Y-%m-%d %H:%M:%S"
    lines = [
        f"№ взвешивания: {data.weighing_number or '—'}",
        f"Номер авто: {data.plate_number or '—'}",
        f"Тара, кг: {data.tara_kg}",
        f"Брутто, кг: {data.brutto_kg}",
        f"Нетто, кг: {data.netto_kg}",
        f"Груз: {data.cargo or '—'}",
        f"Контрагент: {data.counterparty or '—'}",
        f"Накладная: {data.invoice_number or '—'}",
        f"Цена за тонну: {data.price_per_ton}",
        f"Сумма: {data.amount}",
        f"Дата взвешивания: {data.weighing_datetime.strftime(dt_fmt) if data.weighing_datetime else '—'}",
        f"Пользователь: {data.user or '—'}",
        f"Сообщение отправлено: {data.message_sent_at.strftime(dt_fmt) if data.message_sent_at else '—'}",
    ]
    reply = "Распознано взвешивание:\n\n" + "\n".join(lines)
    await message.answer(reply)


# Пайплайн: сообщения из группы-источника → PDF в группу-получатель
dp.include_router(report_router)


async def main() -> None:
    settings = get_settings()
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Запуск eLibroCargoReportBot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
