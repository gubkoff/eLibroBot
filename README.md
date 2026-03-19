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

**Сообщения от других ботов в группе-источнике:** через Bot API их не видно. Чтобы читать их и строить PDF, включите режим **MTProto** (`TELEGRAM_API_ID` + `TELEGRAM_API_HASH`) — см. [`docs/MTPROTO.md`](docs/MTPROTO.md).

## Запуск бота

```bash
python main.py
```

### Windows: автозапуск после перезагрузки

Скрипт [`scripts/windows/run_bot.bat`](scripts/windows/run_bot.bat) и пошаговая настройка **Планировщика заданий** — в [`docs/WINDOWS_AUTOSTART.md`](docs/WINDOWS_AUTOSTART.md).

Сборка **одного `eLibroBot.exe`** для машины без Python — [`docs/WINDOWS_EXE_DEPLOY.md`](docs/WINDOWS_EXE_DEPLOY.md), скрипт [`scripts/windows/build_onefile.bat`](scripts/windows/build_onefile.bat).

**Инструкция для пользователей** (exe, `.env`, автозапуск): [`docs/USER_GUIDE_EXE_WINDOWS.md`](docs/USER_GUIDE_EXE_WINDOWS.md).

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
