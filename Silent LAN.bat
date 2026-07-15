@echo off
title Start Silent LAN Server
chcp 65001 >nul
:: Run as Admin
tasklist /FI "SESSIONNAME eq Console" 2>nul | find /i "cmd.exe" >nul || (
    powershell -Command "Start-Process '%~f0' -Verb RunAs -WindowStyle Hidden"
    exit /b
)

cd /d "%~dp0installments"
call ..\venv\Scripts\activate.bat
set DJANGO_ALLOWED_HOSTS=*

:: Firewall
netsh advfirewall firewall add rule name="Installment System 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1

:: Start server silently
start /min powershell -WindowStyle Hidden -Command "cd '%CD%'; waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application"

:: Show notification
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Installment System server is now running on your LAN.', 'Server Started', 'OK', 'Information')"
