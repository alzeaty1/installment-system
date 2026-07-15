@echo off
title Check Server Status
chcp 65001 >nul
cls
color 0B

echo.
echo   ╔════════════════════════════════════════════════════════╗
echo   ║        Server Status Check                             ║
echo   ╚════════════════════════════════════════════════════════╝
echo.

:: Get LAN IP
for /f "tokens=*" %%i in ('python -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));print(s.getsockname()[0]);s.close()"') do set LAN_IP=%%i

:: Check if server is running on port 8000
set PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do set PID=%%a

if defined PID (
    color 0A
    echo   ✅  Server is RUNNING
echo.
    echo   ┌──────────────────────────────────────────────────────
    echo   │  Process ID: %PID%
    echo   │  Local URL:  http://127.0.0.1:8000
    echo   │  LAN URL:    http://%LAN_IP%:8000
    echo   └──────────────────────────────────────────────────────
    echo.
    echo   📱  Any device on same network: http://%LAN_IP%:8000
) else (
    color 0C
    echo   ❌  Server is NOT RUNNING
echo.
    echo   Start it using: "Start LAN" shortcut
)

echo.
pause
