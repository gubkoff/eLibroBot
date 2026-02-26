"""
Генерация PDF-отчёта по результатам расчёта и списку записей.
Сохраняет во временный файл и возвращает путь для отправки в Telegram.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.platypus.tables import TableStyle

from parser.models import Record
from report.calculator import CalculationResult


def build_pdf(
    calculation_result: CalculationResult,
    records: List[Record],
    title: str = "eLibroCargoReportBot — Отчёт",
    **meta: str,
) -> Path:
    """
    Строит PDF-отчёт: заголовок, дата генерации, таблица записей,
    сводка по категориям, итог, подпись «Сгенерировано: …».
    Возвращает путь к временному PDF-файлу (файл нужно удалить после отправки).
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    path = Path(tmp.name)
    tmp.close()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    # Заголовок
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6 * mm,
    )
    story.append(Paragraph(title, title_style))

    # Дата генерации
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    story.append(Paragraph(f"Дата формирования отчёта: {generated_at}", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))

    # Таблица записей
    if records:
        story.append(Paragraph("Записи", styles["Heading2"]))
        data = [["Дата", "Сумма", "Категория"]]
        for r in records:
            data.append([str(r.date), str(r.amount), r.category])
        t = Table(data, colWidths=[35 * mm, 30 * mm, 80 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.append(t)
        story.append(Spacer(1, 4 * mm))

    # Сводка по категориям
    if calculation_result.by_category:
        story.append(Paragraph("По категориям", styles["Heading2"]))
        cat_data = [["Категория", "Сумма"]]
        for cat, amount in sorted(calculation_result.by_category.items(), key=lambda x: -x[1]):
            cat_data.append([cat, str(amount)])
        t2 = Table(cat_data, colWidths=[100 * mm, 45 * mm])
        t2.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.append(t2)
        story.append(Spacer(1, 4 * mm))

    # Итого
    story.append(
        Paragraph(
            f"<b>Итого: {calculation_result.total}</b>",
            ParagraphStyle("Total", parent=styles["Normal"], fontSize=12, spaceAfter=6 * mm),
        )
    )

    # Подпись внизу
    story.append(
        Paragraph(
            f"Сгенерировано: {generated_at}",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.gray),
        )
    )

    doc.build(story)
    return path
