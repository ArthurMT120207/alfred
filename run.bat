@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ALFRED
if not exist venv (
  echo Run install.bat first.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python alfred.py %*
pause
