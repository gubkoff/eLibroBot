"""
Хендлер сообщений из группы-источника: парсинг → расчёт → PDF → отправка в группу-получатель.
"""

from aiogram import Router
from aiogram.types import Message

from bot.filters import source_group_message
from bot.pipeline import run_weighing_pipeline

router = Router()


@router.message(source_group_message)
async def pipeline_handler(message: Message) -> None:
    """
    Пайплайн по сообщению из группы-источника (Bot API):
    parse_message (WeighingData) → формирование накладной → build_pdf → отправка в группу-получатель.
    Регистрируется с фильтром source_group_message, поэтому сюда попадают только
    текстовые сообщения из SOURCE_GROUP_ID(S) (не команды).
    Если в .env заданы TELEGRAM_API_ID и TELEGRAM_API_HASH, этот роутер не подключается —
    чтение идёт через MTProto (см. bot.mtproto_reader).
    """
    async def reply(text: str) -> None:
        await message.reply(text)

    await run_weighing_pipeline(
        text=message.text or "",
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        source_chat_title=getattr(message.chat, "title", None),
        bot=message.bot,
        reply=reply,
    )
