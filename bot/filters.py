"""Фильтры для хендлеров: только сообщения из группы-источника с текстом."""

import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import get_settings

logger = logging.getLogger(__name__)


class SourceGroupFilter(BaseFilter):
    """
    Пропускает только сообщения из группы-источника с непустым текстом.
    Не пропускает команды (текст, начинающийся с /), чтобы /start и /parse обрабатывались своими хендлерами.
    """

    async def __call__(self, message: Message) -> bool:
        if not message.text or not message.text.strip():
            return False
        settings = get_settings()
        if message.chat.id not in settings.source_group_ids:
            # Помогает увидеть реальный id чата в логе, если .env настроен неверно.
            if message.chat.type in ("group", "supergroup"):
                logger.info(
                    "Сообщение не из списка источников: chat id=%s title=%r "
                    "(ожидаются id: %s)",
                    message.chat.id,
                    getattr(message.chat, "title", None),
                    settings.source_group_ids,
                )
            return False
        if message.text.strip().startswith("/"):
            return False
        return True


source_group_message = SourceGroupFilter()
