"""Расчёты и генерация отчётов по записям Record."""

from report.calculator import CalculationResult, calculate
from report.pdf_builder import build_pdf

__all__ = ["CalculationResult", "calculate", "build_pdf"]
