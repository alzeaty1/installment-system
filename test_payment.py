import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'installments.settings')
os.environ['DJANGO_ALLOWED_HOSTS'] = '*'

# Setup django
import django
from django.conf import settings
django.setup()

# Now safe to import models
from django.test import Client
from django.urls import reverse
from core.models import Installment, Receiver, Account
from django.contrib.auth import get_user_model

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
if not admin:
    print("NO ADMIN USER")
    sys.exit(1)

c = Client()
c.force_login(admin)

# Find RECEIVER first
receiver = Receiver.objects.filter(is_active=True).first()
if not receiver:
    acc = Account.objects.first()
    if not acc:
        acc = Account.objects.create(name="Test")
    receiver = Receiver.objects.create(name="Test Receiver", account=acc, is_active=True)
    print(f"Created receiver ID={receiver.id}")

print(f"Using receiver ID={receiver.id}, Name={receiver.name}")

# Find pending installment
inst = Installment.objects.filter(status='pending').first()
if not inst:
    print("NO PENDING INSTALLMENTS")
    sys.exit(1)

url = reverse('core:installment_pay', args=[inst.id])
print(f"Testing: ID={inst.id}, Amount={inst.amount}, Status={inst.status}")

# GET
resp = c.get(url)
print(f"GET -> HTTP {resp.status_code}")
if resp.status_code != 200:
    print("SKIPPING - cannot access page")
    sys.exit(1)

paid = float(inst.amount - inst.paid_amount)
print(f"Amount to pay: {paid}")

# POST - test cash + receiver
post_data = {
    'paid_amount': str(paid),
    'paid_date': '2026-07-11',
    'payment_method': 'cash',
    'receiver': str(receiver.id),
}
resp = c.post(url, post_data, follow=False)
print(f"\nPOST (cash+receiver) -> HTTP {resp.status_code}")
if resp.status_code == 302:
    print("✅ PAYMENT SUCCESSFUL!")
    print(f"   Redirect to: {resp.headers.get('Location', '')}")
else:
    content = resp.content.decode()
    import re
    errs = re.findall(r'text-danger[^>]*>([^<]+)', content)
    print(f"❌ Failed. Errors: {errs[:5] if errs else 'none'}")
    if not errs:
        print(f"   Page snippet: {content[:200]}")

inst.refresh_from_db()
print(f"After: Status={inst.status}, Paid={inst.paid_amount}")
print("DONE")
