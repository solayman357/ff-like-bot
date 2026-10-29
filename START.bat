@echo off
title FF Daily Like Bot
echo ==================================================
echo    FF DAILY LIKE BOT - Setaup suru holo...
echo ==================================================
echo.

where python >nul 2>nul
if %errorlevel%==0 (
    echo [OK] Python paowa geche
) else (
    echo [!] Python install korte hobe!
    echo.
    echo Step 1: https://www.python.org/downloads/ e jao
    echo Step 2: "Download Python 3.13" click koro
    echo Step 3: Installer e "Add Python to PATH" checkbox MARK koro
    echo Step 4: Install koro
    echo.
    echo Tarpor abar ei file ta double-click koro.
    pause
    exit /b
)

echo [1/2] Dorkari tools install hocche...
python -m pip install --quiet --break-system-packages httpx pycryptodome 2>nul
python -m pip install --quiet httpx pycryptodome 2>nul

echo [2/2] Bot cholchhe...
python main_menu.py

pause
