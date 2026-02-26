"""
Получение стоимости по категориям из Google Таблицы.
Таблица: колонка A — наименование (категория), колонка B — цена.
Поддерживается публичный доступ без авторизации (CSV-экспорт) и опционально — доступ по сервисному аккаунту.
"""

import csv
import logging
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# ID таблицы из ссылки (можно переопределить через .env)
DEFAULT_SPREADSHEET_ID = "1AIxS1ue3F2lCioZM4odJdjoESkHPiLHawg_CRF8AMZg"

# Публичный CSV-экспорт (работает, если таблица опубликована в веб: Файл → Открыть доступ → Опубликовать в интернете → формат CSV)
def _fetch_public_csv(spreadsheet_id: str) -> Dict[str, Decimal]:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid=0"
    result: Dict[str, Decimal] = {}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "eLibroCargoReportBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8-sig")
        reader = csv.reader(text.splitlines())
        rows = list(reader)
    except Exception as e:
        logger.warning(
            "Google Sheet (public): failed to fetch CSV for %s: %s. "
            "If the sheet is public, publish it to web: File → Share → Publish to web → CSV.",
            spreadsheet_id,
            e,
        )
        return {}
    if not rows:
        return {}
    for row in rows[1:]:  # пропуск заголовка
        if len(row) < 2:
            continue
        name = (row[0] or "").strip()
        price_str = (row[1] or "").strip().replace(",", ".")
        if not name:
            continue
        try:
            result[name] = Decimal(price_str) if price_str else Decimal("0")
        except Exception:
            logger.debug("Skip invalid price for %r: %r", name, row[1])
    return result


def get_category_prices(
    spreadsheet_id: str,
    credentials_path: str | Path | None = None,
) -> Dict[str, Decimal]:
    """
    Читает первый лист таблицы: A = наименование, B = цена.
    Если credentials_path не задан — используется публичный CSV-экспорт (таблица должна быть опубликована в веб).
    Если задан — доступ через gspread и сервисный аккаунт.
    """
    if credentials_path and Path(credentials_path).exists():
        try:
            import gspread
            gc = gspread.service_account(filename=str(credentials_path))
            sh = gc.open_by_key(spreadsheet_id)
            ws = sh.sheet1
            rows = ws.get_all_values()
        except Exception as e:
            logger.warning(
                "Google Sheet (service account): failed to read %s: %s. "
                "Falling back to public CSV.",
                spreadsheet_id,
                e,
            )
            return _fetch_public_csv(spreadsheet_id)
        if not rows:
            return {}
        result: Dict[str, Decimal] = {}
        for row in rows[1:]:
            if len(row) < 2:
                continue
            name = (row[0] or "").strip()
            price_str = (row[1] or "").strip().replace(",", ".")
            if not name:
                continue
            try:
                result[name] = Decimal(price_str) if price_str else Decimal("0")
            except Exception:
                logger.debug("Skip invalid price for %r: %r", name, row[1])
        return result
    # Публичный доступ без авторизации
    return _fetch_public_csv(spreadsheet_id)
