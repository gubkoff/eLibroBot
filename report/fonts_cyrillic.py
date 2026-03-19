"""
Register a font that supports Cyrillic for PDF output.
Prefers Arial/Arial Bold on macOS; falls back to DejaVuSans (project or system).
On Windows, uses fonts from %WINDIR%\\Fonts (Arial) when available — важно для PyInstaller onefile.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Union

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Name used in ReportLab styles
CYRILLIC_FONT_NAME = "DejaVuSans"
CYRILLIC_FONT_BOLD_NAME = "DejaVuSans-Bold"


def _project_root() -> Path:
    """Корень приложения: каталог с ``main.py`` / распакованный ``_MEIPASS`` у PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # .../report/fonts_cyrillic.py -> родитель ``report`` = корень репозитория
    return Path(__file__).resolve().parents[1]


_PROJECT_ROOT = _project_root()

_CANDIDATES: list[Tuple[Path, Union[Path, None]]] = []

if sys.platform == "win32":
    _windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    _CANDIDATES.extend(
        [
            (_windir / "Fonts" / "arial.ttf", _windir / "Fonts" / "arialbd.ttf"),
            (_windir / "Fonts" / "ARIAL.TTF", _windir / "Fonts" / "ARIALBD.TTF"),
        ]
    )

_CANDIDATES.extend(
    [
    # macOS Arial (preferred)
    (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
    (Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
    # Project-provided DejaVu
    (_PROJECT_ROOT / "fonts" / "DejaVuSans.ttf", _PROJECT_ROOT / "fonts" / "DejaVuSans-Bold.ttf"),
    # Linux DejaVu
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("/usr/share/fonts/TTF/DejaVuSans.ttf"), Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf")),
    # User fonts
    (Path.home() / "Library" / "Fonts" / "DejaVuSans.ttf", Path.home() / "Library" / "Fonts" / "DejaVuSans-Bold.ttf"),
    ]
)

_loaded = False


def _find_font_paths() -> Optional[Tuple[Path, Optional[Path]]]:
    """
    Returns (regular_path, bold_path_or_none) if regular font exists.
    """
    for regular, bold in _CANDIDATES:
        if regular.exists():
            return regular, (bold if bold and bold.exists() else None)
    return None


def register_cyrillic_font() -> bool:
    """
    Register a Cyrillic-capable font for ReportLab.
    Returns True if a font was registered, False otherwise (Cyrillic may show as squares).
    """
    global _loaded
    if _loaded:
        return True
    paths = _find_font_paths()
    if paths is None:
        logger.warning(
            "Cyrillic font not found. Put DejaVuSans.ttf in project 'fonts/' folder, "
            "or install system fonts (e.g. fonts-dejavu). Cyrillic may render as black squares."
        )
        return False
    regular_path, bold_path = paths
    try:
        pdfmetrics.registerFont(TTFont(CYRILLIC_FONT_NAME, str(regular_path)))
        if bold_path is not None:
            pdfmetrics.registerFont(TTFont(CYRILLIC_FONT_BOLD_NAME, str(bold_path)))
        else:
            # Fallback: same font for "bold" (ReportLab will fake bold)
            pdfmetrics.registerFont(TTFont(CYRILLIC_FONT_BOLD_NAME, str(regular_path)))
        _loaded = True
        logger.debug(
            "Registered Cyrillic font from %s (bold=%s)",
            regular_path,
            bold_path or regular_path,
        )
        return True
    except Exception as e:
        logger.warning("Failed to register font %s: %s", regular_path, e)
        return False
