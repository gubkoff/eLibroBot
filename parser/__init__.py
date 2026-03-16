"""Парсер сообщений взвешивания в структуру WeighingData."""

from parser.models import WeighingData
from parser.parser import parse_message

__all__ = ["WeighingData", "parse_message"]
