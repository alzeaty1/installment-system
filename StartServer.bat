@echo off
title Installment System Server
color 0A
echo ==========================================
echo    Starting Installment System Server
echo ==========================================
echo.
echo [1/3] Changing directory...
cd /d "%~dp0installments"

echo [2/3] Activating virtual environment...
call ..\venv\Scripts\activate.bat

:: Detect local IP for LAN access display
for /f "tokens=*" %%i in ('python -c "import socket; ips=[a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None) if '127.' not in a[4][0]]; print(ips[0] if ips else '127.0.0.1')"') do set LOCAL_IP=%%i

echo [3/3] Starting Waitress server (multi-threaded)...
echo.
echo ==========================================
echo  SERVER IS RUNNING!
echo  Local: http://127.0.0.1:8000
echo  LAN:   http://%LOCAL_IP%:8000
echo ==========================================
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul

:: Open default browser to local server
start "" "http://127.0.0.1:8000"

echo.
echo Server is ready. Press Ctrl+C to stop.
echo.
waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application

pause