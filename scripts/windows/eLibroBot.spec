# PyInstaller spec: один исполняемый файл для Windows.
# Запуск из корня репозитория:
#   python -m PyInstaller scripts/windows/eLibroBot.spec
# или scripts/windows/build_onefile.bat

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# В .spec-файлах PyInstaller не всегда определяет __file__,
# зато передаёт путь к spec в переменной `spec`.
SPEC_DIR = Path(globals().get("spec", "scripts/windows/eLibroBot.spec")).resolve().parent
ROOT = SPEC_DIR.parent.parent

datas = []
binaries = []
hiddenimports = []

for pkg in ("aiogram", "pydantic", "pydantic_settings", "reportlab", "telethon", "qrcode"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

fonts_dir = ROOT / "fonts"
if fonts_dir.is_dir():
    datas += [(str(fonts_dir), "fonts")]

hiddenimports += [
    "config",
    "bot",
    "bot.handlers",
    "bot.filters",
    "bot.pipeline",
    "bot.mtproto_reader",
    "parser",
    "parser.models",
    "parser.parser",
    "report",
    "report.calculator",
    "report.pdf_builder",
    "report.money_ru",
    "report.invoice_models",
    "report.invoice_rules",
    "report.fonts_cyrillic",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(SPEC_DIR / "pyi_runtimedir.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="eLibroBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
