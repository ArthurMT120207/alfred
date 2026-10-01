@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Alfred Installer

echo ==========================================
echo           Installing ALFRED
echo ==========================================
echo.

rem PyAudio (microphone) only works up to Python 3.13 on Windows
set "PY="
py -3.13 --version >nul 2>&1 && set "PY=py -3.13"
if not defined PY goto no313

echo [1/3] Creating virtual environment with Python 3.13...
if not exist venv %PY% -m venv venv
call venv\Scripts\activate.bat

echo [2/3] Installing dependencies (this may take a few minutes)...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 goto piperror

echo.
echo [3/3] Setting up your Anthropic API key...
if exist .env goto hasenv
echo Create your key at https://console.anthropic.com (API Keys)
echo.
set /p APIKEY=Paste your key here and press Enter: 
(
echo ANTHROPIC_API_KEY=%APIKEY%
echo ALFRED_MODEL=claude-sonnet-5-5
echo ALFRED_WAKE_WORD=alfred
echo ALFRED_USER_TITLE=sir
) > .env
echo Key saved to the .env file
goto done

:hasenv
echo .env file already exists, keeping your current key.
goto done

:no313
echo ERROR: Python 3.13 not found.
echo Alfred's microphone does not work on Python 3.14 yet.
echo Open cmd and run:  py install 3.13
echo Then run this installer again.
pause
exit /b 1

:piperror
echo.
echo ERROR installing dependencies. Take a screenshot of this window.
pause
exit /b 1

:done
echo.
echo ==========================================
echo  Done! Now double-click run.bat
echo ==========================================
pause
