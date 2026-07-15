@echo off
title Installment System — Silent Mode
chcp 65001 >nul

:: ── Go to project ──
cd /d "%~dp0installments"
call ..\venv\Scripts\activate.bat
set DJANGO_ALLOWED_HOSTS=*

:: ── Log file ──
set LOG="%~dp0server_log.txt"

echo [%date% %time%] Server started >> %LOG%

:: ── Auto-restart loop ──
:Loop
waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application
echo [%date% %time%] Server CRASHED! Restarting in 5s... >> %LOG%
timeout /t 5 /nobreak >nul
goto Loop
