@echo off
REM eLibroBot: запуск из корня репозитория (для планировщика заданий Windows).
REM Расположение: scripts\windows\run_bot.bat

setlocal EnableDelayedExpansion
set "ROOT=%~dp0..\.."
cd /d "%ROOT%" || exit /b 1

if not exist "%ROOT%\main.py" (
  echo ERROR: main.py not found. ROOT=%ROOT%
  exit /b 1
)

set "LOGDIR=%ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\bot.log"

set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%\venv\Scripts\python.exe" set "PYTHON=%ROOT%\venv\Scripts\python.exe"
if not defined PYTHON set "PYTHON=python"

echo.>>"%LOG%"
echo [%date% %time%] run_bot.bat: start>>"%LOG%"
"%PYTHON%" -u "%ROOT%\main.py" >>"%LOG%" 2>&1
set "EC=!errorlevel!"
echo [%date% %time%] run_bot.bat: exit code !EC!>>"%LOG%"
exit /b !EC!
