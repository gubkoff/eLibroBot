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
from pydantic import ValidationError

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
    brutto_display = (
        data.tara_kg + data.adjusted_netto_kg
        if data.adjusted_netto_kg
        else data.brutto_kg
    )
    lines = [
        f"№ взвешивания: {data.weighing_number or '—'}",
        f"Номер авто: {data.plate_number or '—'}",
        f"Тара, кг: {data.tara_kg}",
        f"Брутто, кг: {brutto_display}",
        f"Нетто, кг: {data.netto_kg}",
        f"Вес с корректировкой, кг: {data.adjusted_netto_kg or '—'}",
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


async def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as e:
        logger.critical(
            "Некорректные настройки. Проверьте .env / переменные окружения. Ошибка: %s",
            e,
        )
        raise SystemExit(2) from e
    if not settings.mtproto_source_enabled:
        dp.include_router(report_router)
        logger.info("Чтение из групп-источников: Bot API (как раньше).")
    else:
        logger.info(
            "Чтение из групп-источников: MTProto (Telethon); "
            "сообщения от других ботов видны. PDF в целевую группу шлёт бот."
        )

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Запуск eLibroCargoReportBot (long polling)...")

    if settings.mtproto_source_enabled:
        from bot.mtproto_reader import run_mtproto_client

        await asyncio.gather(
            dp.start_polling(bot),
            run_mtproto_client(bot),
        )
    else:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
