"""
PyInstaller: при запуске onefile/donedir выставить CWD на каталог с .exe,
чтобы рядом лежал ``.env`` (pydantic-settings ищет его относительно текущего каталога).
"""

import os
import sys

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
