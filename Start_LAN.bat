@echo off
title Installment System - LAN Access
color 0A
echo ==========================================
echo    فتح منفذ 8000 في جدار الحماية
echo ==========================================
echo.
netsh advfirewall firewall add rule name="Installment System 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
echo تم فتح المنفذ بنجاح
echo.
echo ==========================================
echo       تشغيل سيرفر التقسيط
echo ==========================================
echo.
cd /d "%~dp0installments"
call ..\venv\Scripts\activate.bat

:: جلب IP الجهاز
for /f "tokens=*" %%i in ('python -c "import socket; ips=[a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None) if '127.' not in a[4][0] and a[4][0].count('.')==3]; print(ips[0] if ips else '0.0.0.0')"') do set LOCAL_IP=%%i

echo.
echo ==========================================
echo  السيرفر شغال!
echo  Local: http://127.0.0.1:8000
echo  LAN:   http://%LOCAL_IP%:8000
echo ==========================================
echo.
echo  افتح من أي جهاز عالشبكة:
echo  http://%LOCAL_IP%:8000
echo.
echo ==========================================
echo  الضغط Ctrl+C للإيقاف
echo ==========================================
echo.

waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application
pause
