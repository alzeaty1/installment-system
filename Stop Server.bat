@echo off
title Installment System - Stop Server
chcp 65001 >nul
cls
color 0C

echo.
echo   ╔══════════════════════════════════════╗
echo   ║        Stop Server                   ║
echo   ╚══════════════════════════════════════╝
echo.

:: Show listening on port 8000 first
echo   Looking for server process on port 8000...
set FOUND=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo   Found process PID: %%a
call :killProcess %%a
    set FOUND=1
)

if not defined FOUND (
    echo   No server found on port 8000.
)

echo.
echo   ✅ Done
echo.
timeout /t 2 /nobreak >nul
exit /b

:killProcess
echo   Killing PID %1...
taskkill /PID %1 /F >nul 2>&1
echo   Stopped.
exit /b
