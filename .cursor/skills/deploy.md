---
name: "Deploy"
description: "Deploy Django project to PythonAnywhere"
---

Deploy this Django project to PythonAnywhere.

## Steps:
1. Push latest code to GitHub
2. Open PythonAnywhere bash console
3. Clone/pull repo
4. Create/update venv: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
5. Run migrations: `python manage.py migrate`
6. Collect static: `python manage.py collectstatic --noinput`
7. Update WSGI file (point to project's wsgi.py)

## PythonAnywhere Config:
- Username: alzeaty1
- Project path: /home/alzeaty1/installment-system
- WSGI: /var/www/alzeaty1_pythonanywhere_com_wsgi.py
- Static files: /static/ → /home/alzeaty1/installment-system/static/

## After deploy:
- Set up free tier monthly renewal: click "Run until 1 month" in dashboard
- Consider password protection for admin pages
- Set up daily database backup
