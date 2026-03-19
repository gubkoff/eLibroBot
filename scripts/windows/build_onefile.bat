@echo off
REM Сборка eLibroBot.exe (PyInstaller onefile). Запускать на Windows, где установлен Python.
REM Из каталога scripts\windows — переход в корень репозитория.

setlocal
cd /d "%~dp0..\.." || exit /b 1

python -m pip install -q -r requirements.txt
if errorlevel 1 exit /b 1
python -m pip install -q -r requirements-windows-build.txt
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --clean scripts\windows\eLibroBot.spec
if errorlevel 1 exit /b 1

echo.
echo Готово: dist\eLibroBot.exe
echo Скопируйте exe и файл .env в одну папку на целевой машине (см. docs\WINDOWS_EXE_DEPLOY.md).
exit /b 0
