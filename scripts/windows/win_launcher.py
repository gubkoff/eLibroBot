"""
Лёгкий лаунчер для Windows (отдельный exe без окна).

Рядом с этим exe должен лежать eLibroBot.exe и .env.
- Если включён MTProto (TELEGRAM_API_ID + TELEGRAM_API_HASH) и нет сессии —
  запускает основной exe с новой консолью (QR / код входа).
- Иначе — запускает основной exe без окна (фон).

Прямой запуск eLibroBot.exe по-прежнему даёт обычное консольное окно с логами.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        k = key.strip()
        v = val.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def _mtproto_configured(env: dict[str, str]) -> bool:
    return bool((env.get("TELEGRAM_API_ID") or "").strip()) and bool(
        (env.get("TELEGRAM_API_HASH") or "").strip()
    )


def _has_telethon_session(base: Path, env: dict[str, str]) -> bool:
    if (env.get("TELEGRAM_SESSION_STRING") or "").strip():
        return True
    name = (env.get("TELEGRAM_SESSION_FILE") or "telethon.session").strip() or "telethon.session"
    p = Path(name)
    if not p.is_absolute():
        p = base / p
    return p.is_file()


def _worker_argv(base: Path) -> list[str]:
    exe = base / "eLibroBot.exe"
    if exe.is_file():
        return [str(exe)]
    main_py = base / "main.py"
    if main_py.is_file():
        return [sys.executable, str(main_py)]
    raise SystemExit(
        "eLibroBotLaunch: не найден eLibroBot.exe или main.py в папке с лаунчером.\n"
        f"Ожидалось: {exe} или {main_py}"
    )


def main() -> int:
    base = _app_dir()
    os.chdir(base)

    env_map = _parse_dotenv(base / ".env")
    argv = _worker_argv(base)

    need_console = False
    if _mtproto_configured(env_map) and not _has_telethon_session(base, env_map):
        need_console = True

    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_CONSOLE if need_console else subprocess.CREATE_NO_WINDOW
        subprocess.Popen(argv, cwd=str(base), creationflags=flags)
    else:
        subprocess.Popen(argv, cwd=str(base))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
