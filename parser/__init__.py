"""Парсер структурированных сообщений в записи Record."""

from parser.models import Record
from parser.parser import parse_message

__all__ = ["Record", "parse_message"]
