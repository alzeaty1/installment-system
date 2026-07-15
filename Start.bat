@echo off
title Installment System
chcp 65001 >nul

:: Go to project
cd /d "C:\Users\Elnour Tech\installment-system\installments"

:: Activate venv and set env
call "..\venv\Scripts\activate.bat"
set DJANGO_ALLOWED_HOSTS=*

:: Firewall
netsh advfirewall firewall add rule name="Installment System 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1

:: Get LAN IP
for /f "tokens=*" %%i in ('python -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));print(s.getsockname()[0]);s.close()"') do set LAN_IP=%%i

:: Open browser
start "" "http://%LAN_IP%:8000"

:: Show info
cls
color 0A
echo.
echo ========================================
echo    Installment System - Running
echo ========================================
echo.
echo URL:   http://%LAN_IP%:8000
echo Login: admin / admin123
echo.
echo Press Ctrl+C to stop server
echo ========================================
echo.

:: Run server
python -m waitress --port=8000 --host=0.0.0.0 installments.wsgi:application
