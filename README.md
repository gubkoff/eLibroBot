# eLibroBot

Telegram-бот: разбор сообщений формата «ВЗВЕШИВАНИЕ № …» и генерация PDF-накладной.

## Требования

- **Python ≥ 3.9** (задано в `pyproject.toml`, `requires-python`).

## Установка

```bash
python3.9 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните переменные (см. `config.py`).

## Запуск бота

```bash
python main.py
```

## Тесты

```bash
pytest -q
```

## Локальная генерация PDF (без Telegram)

```bash
python scripts/debug_nakladnaya.py
python scripts/generate_pdf_baselines.py
```

Подробнее: `docs/PDF_REGRESSION_BASELINE.md`, `docs/PDF_MANUAL_CHECKLIST.md`.
