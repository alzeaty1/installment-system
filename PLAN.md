# نظام إدارة بيزنس التقسيط (Installment System)

## المتطلبات الكاملة

Build a complete Django installment management system in Arabic (RTL) with the following:

### Tech Stack
- Django 5.2 + SQLite
- Bootstrap 5 (RTL) + Chart.js
- WeasyPrint for PDF reports
- Pillow for images

### Database Models (in `core/models.py`)

#### 1. Customer (عميل)
- name (CharField)
- phone (CharField, unique)
- national_id (CharField, optional)
- address (TextField, optional)
- whatsapp (CharField, optional)
- created_at (DateTimeField)

#### 2. SupplierCategory (فئة تاجر)
- name (CharField) — e.g. "سامسونج", "شاومي", "اكسسوارات"

#### 3. Supplier (تاجر)
- name (CharField)
- phone (CharField)
- address (TextField, optional)
- category (FK SupplierCategory, optional)
- notes (TextField, optional)
- created_at (DateTimeField)

#### 4. ProductCategory (فئة منتج)
- name (CharField)

#### 5. Product (منتج)
- name (CharField)
- brand (CharField, optional)
- category (FK ProductCategory, optional)
- estimated_price (DecimalField, optional)
- image (ImageField, optional)
- created_at (DateTimeField)

#### 6. SupplierPurchase (مشتريات من تاجر)
- supplier (FK Supplier)
- product (FK Product, optional)
- product_name (CharField) — free text in case no product
- purchase_price (DecimalField)
- purchase_date (DateField)
- image (ImageField, optional)
- notes (TextField, optional)
- created_at (DateTimeField)

#### 7. Contract (عقد تقسيط) — THE CORE
- contract_number (CharField, auto-generated, unique)
- customer (FK Customer)
- product (FK Product, optional)
- product_name (CharField) — free text
- actual_cost (DecimalField) — سعر الشراء الفعلي (9400)
- customer_price (DecimalField) — السعر للعميل (9700)
- down_payment (DecimalField, default=0) — المقدم
- remaining_amount (DecimalField) — المتبقي = customer_price - down_payment
- interest_rate (DecimalField) — النسبة % (35)
- total_interest (DecimalField) — إجمالي الفائدة = remaining × rate/100
- total_amount (DecimalField) — الإجمالي المستحق = remaining + total_interest
- months_count (IntegerField) — عدد الشهور
- installment_amount (DecimalField) — القسط الشهري
- calculation_mode (CharField choices: A/B/C)
- start_date (DateField)
- payment_due_day (IntegerField, default=1) — يوم الاستحقاق كل شهر
- status (CharField: active/completed/overdue/cancelled, default=active)
- notes (TextField, optional)
- created_at (DateTimeField)

#### 8. Installment (قسط)
- contract (FK Contract, related_name='installments')
- installment_number (IntegerField)
- due_date (DateField)
- amount (DecimalField) — المبلغ المستحق
- paid_amount (DecimalField, default=0)
- paid_date (DateField, null=True, blank=True)
- status (CharField: pending/paid/late/partial, default=pending)
- payment_method (CharField: cash/wallet/instapay, blank=True)
- notes (TextField, optional)

#### 9. Expense (مصروف)
- title (CharField)
- amount (DecimalField)
- expense_date (DateField)
- category (CharField, optional) — e.g. "نقل", "إيجار", "نت"
- notes (TextField, optional)

#### 10. Notification (تنبيه)
- contract (FK Contract, optional)
- installment (FK Installment, optional)
- message (TextField)
- notification_type (CharField: reminder/overdue/info)
- is_read (BooleanField, default=False)
- created_at (DateTimeField)

#### 11. Settings (إعدادات)
- default_interest_rate (DecimalField, default=3.5) — النسبة الشهرية الافتراضية %
- default_payment_due_day (IntegerField, default=1)
- business_name (CharField, default="نظام التقسيط")
- whatsapp_enabled (BooleanField, default=True)

### Calculation Logic (in `core/calculations.py`)

Three calculation modes:

**Mode A** — User provides monthly installment + months count → system calculates interest rate:
```
total_payable = installment × months
interest = total_payable - remaining
rate = (interest / remaining) × 100
```

**Mode B** — User provides interest rate + months count → system calculates monthly installment:
```
interest = remaining × (rate / 100)
total = remaining + interest
installment = total / months
```

**Mode C** — User provides months count only → system suggests rate:
```
rate = default_monthly_rate × months
# Then same as Mode B
```

### Views & URLs (in `core/views.py` and `core/urls.py`)

#### Dashboard
- GET `/` — Dashboard with: total active contracts, due today installments, total profit, total invested, overdue count, recent activities, Chart.js graphs

#### Customers
- GET `/customers/` — List + search (name, phone)
- GET `/customers/create/` — Create form
- POST `/customers/create/` — Save
- GET `/customers/<id>/` — Detail: contracts, installments, total paid, total remaining
- GET `/customers/<id>/edit/` — Edit form
- POST `/customers/<id>/edit/` — Update

#### Suppliers
- GET `/suppliers/` — List + search
- GET `/suppliers/create/` — Create
- GET `/suppliers/<id>/` — Detail: purchase history, total spent
- GET `/suppliers/<id>/edit/` — Edit

#### Products
- GET `/products/` — List + search
- GET `/products/create/` — Create
- GET `/products/<id>/` — Detail

#### Supplier Purchases
- GET `/purchases/` — List
- GET `/purchases/create/` — Create (select supplier, enter price, date, image, notes)

#### Contracts
- GET `/contracts/` — List with filters (status, customer)
- GET `/contracts/create/` — Create form with 3-mode calculator (AJAX/JS)
- POST `/contracts/create/` — Save contract + auto-generate installments
- GET `/contracts/<id>/` — Detail: all info + installment table + profit breakdown
- GET `/contracts/<id>/edit/` — Edit
- POST `/contracts/<id>/mark-completed/` — Mark as completed

#### Installments
- GET `/installments/` — List with filters (status, date range)
- POST `/installments/<id>/pay/` — Record payment (amount, method, date)
- GET `/installments/due-today/` — Installments due today
- GET `/installments/overdue/` — Overdue installments

#### Reports
- GET `/reports/` — Reports dashboard
- GET `/reports/profit/` — Profit report (per contract, per month, overall)
- GET `/reports/profit/pdf/` — PDF export
- GET `/reports/customer-statement/<id>/` — Customer statement
- GET `/reports/customer-statement/<id>/pdf/` — PDF export
- GET `/reports/investment/` — Money invested vs returns
- GET `/reports/suppliers/` — Supplier comparison
- GET `/reports/monthly/` — Monthly summary

#### Notifications
- GET `/notifications/` — List
- POST `/notifications/<id>/read/` — Mark as read
- POST `/notifications/check-due/` — Check and generate due reminders

#### Expenses
- GET `/expenses/` — List
- GET `/expenses/create/` — Create
- POST `/expenses/create/` — Save

#### Settings
- GET `/settings/` — Edit settings
- POST `/settings/` — Save

### Templates (in `core/templates/core/`)
- Use Bootstrap 5 RTL (from CDN)
- Base template with navbar (sidebar navigation)
- All forms styled with Bootstrap
- Arabic labels everywhere
- Currency in جنيه (EGP)

### Admin
- Register all models in `core/admin.py` with list_display, search_fields, list_filter

### Settings Updates
- Add 'core' to INSTALLED_APPS
- Set LANGUAGE_CODE = 'ar'
- Set TIME_ZONE = 'Africa/Cairo'
- Configure MEDIA_ROOT and MEDIA_URL for images
- Configure STATIC_ROOT

### Important Notes
- When a contract is created, auto-generate all installment records with due_dates
- Installment due_date: start_date + N months, on the payment_due_day
- Auto-detect overdue installments (due_date < today and status == pending)
- Profit per contract = (customer_price - actual_cost) + total_interest
- Total invested = sum of all actual_cost across contracts
- Total collected = sum of all paid_amount across installments
