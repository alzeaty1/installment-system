@echo off
title ◈ Installment System Server ◈
setlocal enabledelayedexpansion

:: ── UTF-8 Support ──
chcp 65001 >nul

:: ── Check Admin for Firewall ──
net session >nul 2>&1
set ADMIN=%errorlevel%

:: ── Go to project ──
cd /d "%~dp0installments"

:: ── Clear screen for clean look ──
cls

:: ── Banner ──
color 0B
echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║       💼  Installment System  💼                ║
echo   ║     نظام إدارة التقسيط — متعدد الأجهزة          ║
echo   ╚══════════════════════════════════════════════════╝
echo.

:: ── Step 1: Activate venv ──
echo   [1/4] 🔄  تجهيز البيئة الافتراضية...
call ..\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    color 0C
    echo   ⛔  فشل تفعيل البيئة الافتراضية!
    pause
    exit /b 1
)
echo   ✅  تم التفعيل
echo.

:: ── Step 2: Detect LAN IP ──
echo   [2/4] 🌐  كشف IP الشبكة...
for /f "tokens=4" %%i in ('route print 0.0.0.0 ^| findstr "0.0.0.0"') do set LAN_IP=%%i
if not defined LAN_IP set LAN_IP=127.0.0.1
echo   ✅  IP الشبكة: %LAN_IP%
echo.

:: ── Step 3: Firewall ──
echo   [3/4] 🔓  فتح البورت 8000...
if %ADMIN% equ 0 (
    netsh advfirewall firewall add rule name="Installment System 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
    echo   ✅  تم التأكد من فتح البورت
) else (
    color 0E
    echo   ⚠️  لم يتم تشغيل الباتش كـ Admin — الجدار الناري قد يمنع الاتصال
    echo      شغّل الملف بزر الماوس الأيمن ^> Run as administrator
)
echo.

:: ── Step 4: Start Server ──
echo   [4/4] 🚀  تشغيل السيرفر...
echo.

:: ── Set ALLOWED_HOSTS ──
set DJANGO_ALLOWED_HOSTS=*

:: ── Display Connection Info ──
cls
color 0A
echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║          ✅  السيرفر شغال بنجاح               ║
echo   ╠══════════════════════════════════════════════════╣
echo   ║                                                  ║
echo   ║   📍  محلي:     http://127.0.0.1:8000           ║
echo   ║   🌐  شبكة:     http://%LAN_IP%:8000              ║
echo   ║                                                  ║
echo   ║   👤  دخول:     admin / admin123                ║
echo   ║                                                  ║
echo   ╠══════════════════════════════════════════════════╣
echo   ║                                                  ║
echo   ║   📱  افتح http://%LAN_IP%:8000 من أي جهاز      ║
echo   ║      على نفس شبكة الواي فاي                      ║
echo   ║                                                  ║
echo   ╚══════════════════════════════════════════════════╝
echo.
echo   ═══════════════════════════════════════════════════
echo      اضغط Ctrl+C لإيقاف السيرفر
echo   ═══════════════════════════════════════════════════
echo.

:: ── Start Waitress ──
waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application

:: ── When Server Stops ──
cls
color 0E
echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║       🔴  السيرفر متوقف                        ║
echo   ╚══════════════════════════════════════════════════╝
echo.
echo   اضغط أي مفتاح لإغلاق النافذة...
pause >nul
