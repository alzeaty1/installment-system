@echo off
title ⚙️ Installment System — Startup Setup
chcp 65001 >nul
cd /d "%~dp0"
cls
color 0B

echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║     ⚙️  إعداد التشغيل التلقائي (Startup)       ║
echo   ╚══════════════════════════════════════════════════╝
echo.
echo   ╔══════════════════════════════════════════════════╗
echo   ║  ⚠️  ملاحظات مهمة:                              ║
echo   ║                                                  ║
echo   ║  • السيرفر هيشتغل تلقائياً كل ما تفتح الجهاز    ║
echo   ║  • هيفضل شغال في الخلفية — استهلاك ~270MB رام  ║
echo   ║  • تقدر تفتح http://127.0.0.1:8000 في المتصفح  ║
echo   ║    أي وقت بدون ما تشغله手                    ║
echo   ║  • لو عايز توقفه: افتح Task Manager وقتل العملية║
echo   ║                                                  ║
echo   ╚══════════════════════════════════════════════════╝
echo.
echo   اختر رقم:
echo     1️⃣  تفعيل — تشغيل السيرفر مع بداية الجهاز
echo     2️⃣  إلغاء — إزالة التشغيل التلقائي
echo.
set /p CHOICE="   ▶  "

if "%CHOICE%"=="1" (
    cls
    color 0A
    echo.
    echo   ╔══════════════════════════════════════════════════╗
    echo   ║      🛠️  جاري إعداد التشغيل التلقائي...       ║
    echo   ╚══════════════════════════════════════════════════╝
    echo.
    
    :: Create VBS script to run Start Silent.bat (no window + auto-restart on crash)
    set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    set "VBS=%STARTUP%\InstallmentSystem.vbs"
    set "BAT=%~dp0Start Silent.bat"
    
    (
        echo Set WshShell = CreateObject^("WScript.Shell"^)
        echo WshShell.Run chr^(34^) ^& "%BAT:\=\\%" ^& chr^(34^), 0, False
    ) > "%VBS%"
    
    echo   ✅  تمت الإضافة!
    echo   📂  المسار: %VBS%
    echo.
    echo   السيرفر هيشتغل تلقائياً بعد إعادة تشغيل الجهاز
    echo   (أو تقدر تشغله دلوقتي من Start System.bat)
    
) else if "%CHOICE%"=="2" (
    cls
    color 0E
    echo.
    echo   ╔══════════════════════════════════════════════════╗
    echo   ║      🗑️  جاري إزالة التشغيل التلقائي...       ║
    echo   ╚══════════════════════════════════════════════════╝
    echo.
    
    set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    if exist "%STARTUP%\InstallmentSystem.vbs" (
        del "%STARTUP%\InstallmentSystem.vbs"
        echo   ✅  تمت الإزالة
    ) else (
        echo   ℹ️  لم يتم العثور على إعداد سابق
    )
    
) else (
    echo   ⛔  اختيار غير صحيح
)

echo.
pause
