"""
Чтение сообщений из групп-источников через MTProto (Telethon).
Позволяет видеть сообщения от других ботов; отправка PDF по-прежнему через Bot API (aiogram).
"""

from __future__ import annotations

import asyncio
import getpass
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from aiogram import Bot

from bot.pipeline import run_weighing_pipeline
from config import get_settings
from parser import WeighingData, parse_message

logger = logging.getLogger(__name__)
_MT_CLIENT: Any = None


def get_mtproto_client() -> Any:
    """Возвращает активный Telethon-клиент, если MTProto уже запущен."""
    return _MT_CLIENT


async def fetch_source_message_text(chat_id: int, message_id: int) -> Optional[str]:
    """
    Получает исходный текст сообщения из чата-источника по (chat_id, message_id).
    Возвращает None, если клиент неактивен, сообщение недоступно или текст пустой.
    """
    client = get_mtproto_client()
    if client is None:
        return None
    msg = await client.get_messages(chat_id, ids=message_id)
    raw_text = (getattr(msg, "raw_text", None) or "").strip() if msg is not None else ""
    return raw_text or None


async def find_previous_weighing_same_plate(
    *,
    chat_id: int,
    current_message_id: int,
    current_plate_number: str,
) -> Optional[WeighingData]:
    """
    Ищет первое по времени предыдущее распознаваемое взвешивание
    с тем же номером машины (plate_number).
    """
    client = get_mtproto_client()
    if client is None:
        return None

    plate_norm = (current_plate_number or "").strip().upper()
    if not plate_norm:
        return None

    async for msg in client.iter_messages(chat_id, offset_id=current_message_id):
        raw_text = (getattr(msg, "raw_text", None) or "").strip()
        if not raw_text or raw_text.startswith("/"):
            continue
        parsed = parse_message(raw_text)
        if parsed is None:
            continue
        if (parsed.plate_number or "").strip().upper() == plate_norm:
            return parsed
    return None


async def _has_same_plate_within_last_hour(
    *,
    client,
    chat_id: int,
    current_message_id: int,
    current_plate_number: str,
    current_weighing_datetime: datetime | None,
) -> bool:
    """
    Возвращает True, если в чате есть предыдущее распознаваемое взвешивание
    с тем же plate_number и разницей по `Дата взвешивания` не более 1 часа.
    """
    plate_norm = (current_plate_number or "").strip().upper()
    if not plate_norm or current_weighing_datetime is None:
        return False

    current_dt = current_weighing_datetime
    cutoff = current_dt - timedelta(hours=1)

    async for msg in client.iter_messages(chat_id, offset_id=current_message_id):
        raw_text = (getattr(msg, "raw_text", None) or "").strip()
        if not raw_text or raw_text.startswith("/"):
            continue

        parsed = parse_message(raw_text)
        if parsed is None:
            continue
        if (parsed.plate_number or "").strip().upper() != plate_norm:
            continue
        prev_dt = parsed.weighing_datetime
        if prev_dt is None:
            continue
        if cutoff <= prev_dt <= current_dt:
            return True
        if prev_dt < cutoff:
            # Дальше в истории время взвешивания будет только меньше.
            break

    return False


def _print_login_qr_to_terminal(url: str) -> None:
    """
    Рисует QR с tg://login?... в терминале (сканер в Telegram → Устройства → Подключить устройство).
    Без пакета qrcode остаётся только ссылка в логе.
    """
    import sys

    try:
        import qrcode
        from qrcode import constants as qr_constants
    except ImportError:
        logger.warning(
            "Пакет qrcode не установлен — QR в консоли недоступен. "
            "Выполните: pip install qrcode. Ссылка для входа — в строке лога выше."
        )
        return

    qr = qrcode.QRCode(
        version=None,
        error_correction=qr_constants.ERROR_CORRECT_M,
        box_size=1,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    out = sys.stdout
    out.write(
        "\n=== Отсканируйте QR в Telegram: Настройки → Устройства → "
        "Подключить устройство ===\n"
    )
    # PyInstaller exe на Windows: в cmd.exe ANSI из print_tty часто «ломается» — надёжнее ASCII.
    frozen_win = bool(getattr(sys, "frozen", False)) and sys.platform == "win32"
    use_tty = out.isatty() and not frozen_win
    try:
        if use_tty:
            qr.print_tty(out=out)
        else:
            qr.print_ascii(out=out, tty=False, invert=True)
    except OSError:
        qr.print_ascii(out=out, tty=False, invert=True)
    out.write("=== конец QR ===\n\n")
    out.flush()


async def _telethon_login_with_qr(client, password_cb) -> None:
    """
    Вход по QR (см. Telethon #4050).

    У одноразового QR у Telegram короткий срок жизни (~30–60 с). Telethon при timeout=None ждёт
    только до expires токена, затем asyncio.TimeoutError — поэтому цикл: новый QR и повтор.
    """
    from telethon.errors import SessionPasswordNeededError

    logger.info(
        "Вход по QR: в Telegram на телефоне — Настройки → Устройства → "
        "Подключить устройство (или Связать десктоп). Срок действия одной ссылки короткий; "
        "если не успели — в логе появится новая ссылка."
    )
    attempt = 0
    while not await client.is_user_authorized():
        attempt += 1
        qr_login = await client.qr_login()
        logger.info("Попытка входа по QR #%s — ссылка: %s", attempt, qr_login.url)
        _print_login_qr_to_terminal(qr_login.url)
        try:
            await qr_login.wait(timeout=None)
        except asyncio.TimeoutError:
            logger.warning(
                "Срок действия QR истёк, пока не подтвердили. Запрашиваем новый токен… "
                "(откройте следующую ссылку на телефоне сразу после появления.)"
            )
            continue
        except SessionPasswordNeededError:
            await client.sign_in(password=password_cb())
            break
        break


async def run_mtproto_client(bot: Bot) -> None:
    """Запускает Telethon-клиент до отключения; обрабатывает только указанные чаты-источники."""
    try:
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession
    except ImportError as e:
        logger.critical(
            "Включён MTProto (TELEGRAM_API_ID / TELEGRAM_API_HASH), но пакет telethon не установлен. "
            "Выполните: pip install telethon"
        )
        raise RuntimeError("Установите пакет telethon для режима MTProto.") from e

    settings = get_settings()
    api_id = settings.TELEGRAM_API_ID
    api_hash = settings.TELEGRAM_API_HASH
    assert api_id is not None and api_hash is not None

    raw_string = (settings.TELEGRAM_SESSION_STRING or "").strip()
    if raw_string:
        session: StringSession | str = StringSession(raw_string)
    else:
        session = settings.telethon_session_path

    client = TelegramClient(session, api_id, api_hash)
    global _MT_CLIENT
    _MT_CLIENT = client
    source_ids = list(settings.source_group_ids)

    @client.on(events.NewMessage(chats=source_ids))
    async def _on_new_message(event: events.NewMessage.Event) -> None:
        text = event.raw_text or ""
        if not text.strip() or text.strip().startswith("/"):
            return
        chat = await event.get_chat()
        title = getattr(chat, "title", None)
        enable_inline_buttons = False

        parsed_current = parse_message(text)
        if parsed_current is not None and parsed_current.plate_number:
            try:
                enable_inline_buttons = await _has_same_plate_within_last_hour(
                    client=client,
                    chat_id=event.chat_id,
                    current_message_id=event.id,
                    current_plate_number=parsed_current.plate_number,
                    current_weighing_datetime=parsed_current.weighing_datetime,
                )
            except Exception:
                logger.warning(
                    "Не удалось проверить условие показа inline-кнопок (chat_id=%s, message_id=%s).",
                    event.chat_id,
                    event.id,
                    exc_info=True,
                )
                enable_inline_buttons = False

        await run_weighing_pipeline(
            text=text,
            source_chat_id=event.chat_id,
            source_message_id=event.id,
            enable_inline_buttons=enable_inline_buttons,
            source_chat_title=title,
            bot=bot,
            reply=None,
        )

    logger.info(
        "Запуск Telethon (MTProto): чтение из чатов %s, отправка PDF через бота.",
        source_ids,
    )

    phone_str = (settings.TELEGRAM_PHONE or "").strip() or None
    pwd_plain = (settings.TELEGRAM_2FA_PASSWORD or "").strip()

    def _password_cb() -> str:
        if pwd_plain:
            return pwd_plain
        return getpass.getpass("Пароль 2FA Telegram: ")

    await client.connect()

    if not await client.is_user_authorized() and settings.TELEGRAM_LOGIN_QR:
        await _telethon_login_with_qr(client, _password_cb)

    if not await client.is_user_authorized():
        logger.info(
            "Первый вход Telethon: код приходит в приложение Telegram на телефоне "
            "(чат «Telegram» или уведомление). Принудительная SMS для сторонних приложений у Telegram отключена."
        )
        logger.info(
            "Если код не виден — остановите бота, в .env задайте TELEGRAM_LOGIN_QR=1 и запустите снова "
            "(вход по QR). Подробнее: docs/MTPROTO.md"
        )

    def _phone_interactive() -> str:
        p = input(
            "Telegram MTProto: введите номер телефона в международном формате "
            "(например +79001234567). Чтобы не спрашивало каждый раз, задайте TELEGRAM_PHONE в .env: "
        ).strip()
        if not p:
            raise ValueError(
                "Нужен номер телефона для входа Telethon. Укажите TELEGRAM_PHONE в .env "
                "или введите номер в консоли."
            )
        return p

    # Если сессия уже есть (или вошли по QR), start() сразу выходит по get_me() и не вызывает phone-callback.
    phone_for_start = phone_str if phone_str else _phone_interactive
    await client.start(phone=phone_for_start, password=_password_cb)

    if not await client.is_user_authorized():
        logger.critical("Telethon: не удалось авторизовать пользователя (нет сессии?).")
        await client.disconnect()
        raise RuntimeError("Telethon: сессия не авторизована.")

    try:
        await client.run_until_disconnected()
    finally:
        _MT_CLIENT = None
