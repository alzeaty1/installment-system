@echo off
title Installment System — Network Mode
color 0B
chcp 65001 >nul
echo ==========================================
echo    تشغيل النظام على الشبكة المحلية (LAN)
echo ==========================================
echo.

cd /d "%~dp0installments"

:: Activate virtual environment
echo [1/3] تفعيل البيئة الافتراضية...
call ..\venv\Scripts\activate.bat

:: Detect the real LAN IP via route print
echo [2/3] الكشف عن IP الجهاز...
for /f "tokens=4" %%i in ('route print 0.0.0.0 ^| findstr "0.0.0.0"') do set LAN_IP=%%i
echo    IP الشبكة: %LAN_IP%

:: Ensure firewall rule
echo [3/3] فتح البورت 8000 في الجدار الناري...
netsh advfirewall firewall add rule name="Installment System 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1

:: Start server with ALL hosts allowed (safest for local network)
set DJANGO_ALLOWED_HOSTS=*

cls
echo ==========================================
echo   ✅ السيرفر شغال على الشبكة
echo ==========================================
echo.
echo    من هذا الجهاز:     http://127.0.0.1:8000
echo    من الأجهزة التانية: http://%LAN_IP%:8000
echo.
echo ==========================================
echo    اضغط Ctrl+C للإيقاف
echo ==========================================

waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application

pause
