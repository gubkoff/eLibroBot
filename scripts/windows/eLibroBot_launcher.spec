# Лаунчер без окна: стартует eLibroBot.exe с консолью или в фоне.
# Сборка из корня репозитория:
#   python -m PyInstaller scripts/windows/eLibroBot_launcher.spec

from pathlib import Path

block_cipher = None

SPEC_DIR = Path(globals().get("spec", "scripts/windows/eLibroBot_launcher.spec")).resolve().parent
ROOT = SPEC_DIR.parent.parent

a = Analysis(
    [str(SPEC_DIR / "win_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name="eLibroBotLaunch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
