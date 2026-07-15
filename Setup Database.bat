@echo off
title Setup Database for LAN Server
chcp 65001 >nul
cd /d "%~dp0installments"
call ..\venv\Scripts\activate.bat

echo Creating database tables...
python manage.py migrate

echo.
echo Creating superuser (admin / admin123)...
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', '', 'admin123')
    print('Superuser created: admin / admin123')
else:
    print('Superuser already exists')
"

echo.
echo Collecting static files...
python manage.py collectstatic --noinput

echo.
echo Setup complete!
pause
