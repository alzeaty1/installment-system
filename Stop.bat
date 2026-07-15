@echo off
title Installment System
chcp 65001 >nul
echo.
echo   Stopping server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    echo   Stopped process %%a
)
echo   Done
echo.
