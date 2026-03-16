"""
Register a font that supports Cyrillic for PDF output.
Tries: project fonts/DejaVuSans.ttf, then common system paths.
"""

import logging
from pathlib import Path
from typing import Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Name used in ReportLab styles
CYRILLIC_FONT_NAME = "DejaVuSans"
CYRILLIC_FONT_BOLD_NAME = "DejaVuSans-Bold"

# Candidate paths: project fonts/ then system
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATES = [
    _PROJECT_ROOT / "fonts" / "DejaVuSans.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path.home() / "Library" / "Fonts" / "DejaVuSans.ttf",
]

_loaded = False


def _find_font_path() -> Optional[Path]:
    for p in _CANDIDATES:
        if p.exists():
            return p
    return None


def register_cyrillic_font() -> bool:
    """
    Register a Cyrillic-capable font for ReportLab.
    Returns True if a font was registered, False otherwise (Cyrillic may show as squares).
    """
    global _loaded
    if _loaded:
        return True
    path = _find_font_path()
    if path is None:
        logger.warning(
            "Cyrillic font not found. Put DejaVuSans.ttf in project 'fonts/' folder, "
            "or install system fonts (e.g. fonts-dejavu). Cyrillic may render as black squares."
        )
        return False
    try:
        pdfmetrics.registerFont(TTFont(CYRILLIC_FONT_NAME, str(path)))
        # Use same font for "bold" (ReportLab will fake bold if no bold file)
        pdfmetrics.registerFont(TTFont(CYRILLIC_FONT_BOLD_NAME, str(path)))
        _loaded = True
        logger.debug("Registered Cyrillic font from %s", path)
        return True
    except Exception as e:
        logger.warning("Failed to register font %s: %s", path, e)
        return False
