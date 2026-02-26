"""
eLibroCargoReportBot — бот для расчётов и PDF-отчётов по сообщениям из группы.
Точка входа: запуск long polling.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import get_settings

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
