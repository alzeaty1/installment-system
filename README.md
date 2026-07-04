# installment-system

A Django-based installment business management system.

## Local setup

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
cd installments
..\venv\Scripts\python manage.py migrate
..\venv\Scripts\python manage.py runserver
```

## Configuration

The project reads these environment variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`

Use `.env.example` as a reference when preparing an external runtime environment.