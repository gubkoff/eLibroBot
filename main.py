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
    Временная команда для проверки парсера в Telegram.
    Использование: /parse дата сумма категория (можно несколько строк).
    """
    parts = message.text.split(maxsplit=1)
    text = parts[1].strip() if len(parts) > 1 else ""
    if not text:
        await message.answer(
            "Отправьте текст для разбора после команды.\n\n"
            "Формат строки: дата сумма категория\n"
            "Разделители: пробел, запятая, табуляция.\n"
            "Дата: YYYY-MM-DD или DD.MM.YYYY.\n\n"
            "Пример:\n<code>/parse 2025-02-26 100 продукты</code>\n"
            "Или несколько строк:\n<code>/parse\n2025-02-26 100 продукты\n2025-02-27 200 транспорт</code>"
        )
        return
    records = parse_message(text)
    if not records:
        await message.answer("Не удалось извлечь ни одной записи. Проверьте формат (дата сумма категория).")
        return
    lines = []
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. {r.date} — {r.amount} — {r.category}")
    total = sum(r.amount for r in records)
    reply = "Распознано записей: " + str(len(records)) + "\n\n" + "\n".join(lines) + "\n\nИтого: " + str(total)
    await message.answer(reply)


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
