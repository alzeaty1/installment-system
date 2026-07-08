@echo off
title Stop Installment System Server
color 0C
echo ==========================================
echo    Stopping Installment System Server
echo ==========================================
echo.
echo Searching for running Python server processes...
echo.

:: Kill the python process running manage.py
taskkill /F /FI "WINDOWTITLE eq Installment System Server" /IM python.exe

if %ERRORLEVEL% EQU 0 (
    echo Server stopped successfully!
) else (
    echo No running server found or already stopped.
)

echo.
pause