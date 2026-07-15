@echo off
title Start LAN Network Server
chcp 65001 >nul
:: ── Run as Admin (auto-elevate) ──
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 🔐 Requesting Admin privileges for firewall...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0installments"
call ..\venv\Scripts\activate.bat

:: Get real LAN IP
for /f "tokens=*" %%i in ('python -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));print(s.getsockname()[0]);s.close()"') do set LAN_IP=%%i

:: Open firewall
netsh advfirewall firewall add rule name="Installment System 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1

set DJANGO_ALLOWED_HOSTS=*

echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║     Installment System — LAN Network Mode              ║
echo ╚════════════════════════════════════════════════════════╝
echo.
echo   ✅ Server running on:
echo   ┌──────────────────────────────────────────────────────
echo   │  Local:  http://127.0.0.1:8000
echo   │  LAN:    http://%LAN_IP%:8000
echo   └──────────────────────────────────────────────────────
echo.
echo   📱  Any device on the same WiFi can access:
echo        http://%LAN_IP%:8000
echo.
echo   Press Ctrl+C to stop
echo.

waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application
