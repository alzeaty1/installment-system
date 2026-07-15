# Installment System UI Redesign Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** تحديث شكل نظام التقسيط ليبقى أكثر احترافية ووضوحاً وسهل الاستخدام، مع الحفاظ على نفس الوظائف والداتا بدون مخاطرة.

**Architecture:** نبدأ من نسخة التجربة على `D:\installment-system-test` وليس النسخة الأساسية. التغيير يكون تدريجيًا: أولاً Design System مركزي في `base.html` أو ملف CSS مستقل، ثم تحسين صفحات رئيسية عالية الاستخدام، ثم اختبار وتشغيل على بورت `8001` قبل نقل أي شيء للنسخة الأساسية.

**Tech Stack:** Django Templates, Bootstrap 5 RTL, Bootstrap Icons, CSS variables, optional custom static CSS, existing `mask_money` template tag, Windows batch launchers.

---

## Current Context / Assumptions

- النسخة الأساسية: `C:\Users\Elnour Tech\installment-system`
- نسخة التجربة الآمنة: `D:\installment-system-test`
- المستخدم طلب تغيير شكل السيستم باستخدام skills؛ استخدمنا `frontend-design` كمرجع للتوجه البصري.
- النظام حاليًا يستخدم Bootstrap RTL من CDN و CSS مدمج داخل:
  - `installments/core/templates/core/base.html`
- لا يوجد CSS خارجي حاليًا داخل `core/static/`.
- المطلوب تصميم عملي لنظام حسابات/أقساط: وضوح، أرقام مالية، تحذيرات المتأخرات، أزرار دفع واضحة، واجهة عربية RTL.
- يجب عدم لمس الداتا الحقيقية أثناء التجربة.

---

## Proposed Design Direction

### Visual Identity: “دفتر مالي حديث”

واجهة مستوحاة من دفتر حسابات احترافي لكن بشكل حديث:
- ألوان هادئة تناسب الحسابات والفلوس.
- استخدام لون أخضر مالي للإجراءات الناجحة والدفع.
- استخدام أحمر واضح فقط للمتأخرات والمخاطر.
- كروت أقل عشوائية وأكثر انتظاماً.
- جداول أوضح، صفوف قابلة للمسح السريع، أرقام مالية ثابتة العرض.

### Design Tokens

```css
:root {
  --app-bg: #F3F6F4;
  --surface: #FFFFFF;
  --surface-soft: #F8FAF8;
  --ink: #17201A;
  --muted: #66736A;
  --line: #DDE6DF;
  --brand: #166534;
  --brand-soft: #DCFCE7;
  --warning: #B45309;
  --danger: #B91C1C;
  --danger-soft: #FEE2E2;
  --sidebar: #0F2417;
  --sidebar-hover: #183B25;
  --radius-card: 18px;
  --radius-control: 12px;
}
```

### Typography

- Display / headings: keep Arabic-friendly system stack initially for reliability:
  ```css
  font-family: "Segoe UI", Tahoma, Arial, sans-serif;
  ```
- Money / numeric values:
  ```css
  font-variant-numeric: tabular-nums;
  font-family: "Segoe UI", Tahoma, Arial, sans-serif;
  ```
- Avoid adding external fonts until the design is stable, to keep LAN/local use fast and reliable.

### Signature Element

**“Financial status rail”**: الشريط الجانبي والكروت المهمة يبقوا بلون أخضر داكن، مع شارات واضحة للمتأخرات والدفع. ده يخلي النظام شكله مالي/محاسبي مش SaaS عام.

---

## Step-by-Step Plan

### Task 1: Work Only in the Test Copy

**Objective:** ضمان أن كل تجارب الشكل تتم على نسخة D بدون لمس الداتا الأساسية.

**Files:**
- Workdir: `D:\installment-system-test`
- Do not modify: `C:\Users\Elnour Tech\installment-system` during design experiments.

**Step 1: Verify test copy exists**

Run:
```bash
cd /d/installment-system-test && pwd && git status
```

Expected:
```text
/d/installment-system-test
On branch codex-updates
nothing to commit, working tree clean
```

**Step 2: Run test server on 8001 only**

Run:
```bash
cd /d/installment-system-test/installments
source ../venv/Scripts/activate
python manage.py runserver 0.0.0.0:8001
```

Expected:
```text
Starting development server at http://0.0.0.0:8001/
```

**Step 3: Commit checkpoint before visual work**

```bash
cd /d/installment-system-test
git status
git commit --allow-empty -m "chore: checkpoint before UI redesign"
```

---

### Task 2: Move Inline Base CSS to a Dedicated Design File

**Objective:** تخلي التصميم قابل للتعديل بسهولة بدل CSS طويل داخل `base.html`.

**Files:**
- Create: `D:\installment-system-test\installments\core\static\core\css\app.css`
- Modify: `D:\installment-system-test\installments\core\templates\core\base.html`

**Step 1: Create static directory**

```bash
mkdir -p /d/installment-system-test/installments/core/static/core/css
```

**Step 2: Create `app.css` with the current base rules plus new tokens**

Start with this file:

```css
:root {
  --sidebar-width: 260px;
  --sidebar-mini-width: 76px;
  --app-bg: #F3F6F4;
  --surface: #FFFFFF;
  --surface-soft: #F8FAF8;
  --ink: #17201A;
  --muted: #66736A;
  --line: #DDE6DF;
  --brand: #166534;
  --brand-soft: #DCFCE7;
  --warning: #B45309;
  --danger: #B91C1C;
  --danger-soft: #FEE2E2;
  --sidebar: #0F2417;
  --sidebar-hover: #183B25;
  --radius-card: 18px;
  --radius-control: 12px;
}

body {
  background: var(--app-bg);
  color: var(--ink);
  font-family: "Segoe UI", Tahoma, Arial, sans-serif;
}

.layout { min-height: 100vh; }

.sidebar {
  background: linear-gradient(180deg, var(--sidebar), #07140B);
  color: #fff;
  width: var(--sidebar-width);
  transition: width .2s ease, transform .2s ease;
  z-index: 1040;
}

.sidebar a {
  color: #D7E5DC;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: .75rem;
  padding: .72rem .85rem;
  border-radius: 12px;
  white-space: nowrap;
}

.sidebar a:hover,
.sidebar a.active {
  background: var(--sidebar-hover);
  color: #fff;
}

.nav-icon {
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(255,255,255,.09);
  font-size: 1.05rem;
}

.stat,
.card.stat {
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  box-shadow: 0 10px 30px rgba(15, 36, 23, .06);
  background: var(--surface);
}

.table {
  vertical-align: middle;
}

.table th {
  white-space: nowrap;
  color: var(--muted);
  font-size: .82rem;
  font-weight: 700;
}

.money {
  direction: rtl;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.btn {
  border-radius: var(--radius-control);
}

.btn-primary,
.btn-success {
  background: var(--brand);
  border-color: var(--brand);
}

.btn-primary:hover,
.btn-success:hover {
  background: #104B27;
  border-color: #104B27;
}

.badge {
  border-radius: 999px;
  padding: .42rem .62rem;
}

.image-thumb { height: 170px; object-fit: cover; cursor: pointer; }
.image-thumb-sm { width: 64px; height: 48px; object-fit: cover; border-radius: .4rem; cursor: pointer; }
.js-fullscreen-image { cursor: zoom-in; }
.image-viewer .modal-dialog { max-width: min(1100px, 96vw); }
.image-viewer img { max-height: 82vh; width: auto; max-width: 100%; object-fit: contain; }
.sidebar-backdrop { display: none; position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 1030; }

@media (min-width: 992px) {
  .sidebar { position: sticky; top: 0; height: 100vh; }
  body.sidebar-collapsed .sidebar { width: var(--sidebar-mini-width); }
  body.sidebar-collapsed .sidebar-title,
  body.sidebar-collapsed .nav-label { opacity: 0; width: 0; pointer-events: none; }
  body.sidebar-collapsed .sidebar a { justify-content: center; gap: 0; padding: .65rem .4rem; }
  body.sidebar-collapsed .nav-icon { margin: 0; }
  body.sidebar-collapsed .sidebar-toggle { transform: rotate(180deg); }
}

@media (max-width: 991.98px) {
  .layout { display: block; }
  .sidebar { position: fixed; top: 0; bottom: 0; right: 0; transform: translateX(100%); overflow-y: auto; }
  body.sidebar-mobile-open .sidebar { transform: translateX(0); }
  body.sidebar-mobile-open .sidebar-backdrop { display: block; }
  .mobile-topbar { display: flex; }
}

@media (min-width: 992px) { .mobile-topbar { display: none; } }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
  }
}
```

**Step 3: Link stylesheet in `base.html`**

Modify `D:\installment-system-test\installments\core\templates\core\base.html`:

```html
<link href="{% static 'core/css/app.css' %}" rel="stylesheet">
```

Place it after Bootstrap Icons.

**Step 4: Remove duplicate inline CSS carefully**

Remove most rules from `<style>` but keep only tiny one-off fallback if needed. Prefer empty/removal of `<style>` if everything moved.

**Step 5: Verify**

Run:
```bash
cd /d/installment-system-test/installments
source ../venv/Scripts/activate
python manage.py test
```

Expected:
```text
Ran 86 tests
OK
```

**Step 6: Commit**

```bash
cd /d/installment-system-test
git add installments/core/templates/core/base.html installments/core/static/core/css/app.css
git commit -m "style: extract base design system css"
```

---

### Task 3: Redesign Sidebar and Top Mobile Bar

**Objective:** جعل التنقل شكله بروفيشنال وواضح، خصوصاً على شاشة 8GB Win10 وأجهزة الشبكة.

**Files:**
- Modify: `D:\installment-system-test\installments\core\templates\core\base.html`
- Modify: `D:\installment-system-test\installments\core\static\core\css\app.css`

**Step 1: Add account pill markup**

In `base.html`, replace the current account span around lines 105-108 with:

```html
<div class="account-pill mt-2">
  <div class="small text-white-50">الحساب الحالي</div>
  <div class="fw-bold text-truncate">{% if current_account %}{{ current_account.name }}{% else %}الحساب الرئيسي{% endif %}</div>
</div>
<span class="text-secondary small d-block px-2 mt-2">مرحباً، {{ user.username }}</span>
```

**Step 2: Add CSS**

```css
.account-pill {
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 16px;
  padding: .75rem;
}

.sidebar-title {
  white-space: nowrap;
  overflow: hidden;
  transition: opacity .15s ease;
  font-weight: 800;
  letter-spacing: -.02em;
}

.sidebar-toggle,
.theme-toggle {
  width: 38px;
  height: 38px;
  border: 1px solid rgba(255,255,255,.18);
  color: #fff;
  background: rgba(255,255,255,.08);
  border-radius: 12px;
}
```

**Step 3: Verify manually**

Open:
```text
http://127.0.0.1:8001/
```

Check:
- Sidebar is dark green, not generic black.
- Account name is readable.
- Collapse button still works.
- Mobile topbar still appears under 992px width.

**Step 4: Commit**

```bash
git add installments/core/templates/core/base.html installments/core/static/core/css/app.css
git commit -m "style: refresh sidebar navigation"
```

---

### Task 4: Redesign Dashboard Cards and Overdue Summary

**Objective:** الصفحة الرئيسية تكون أوضح: دخل الشهر، العقود، المتأخرات، وأقساط اليوم تظهر بسرعة.

**Files:**
- Modify: `D:\installment-system-test\installments\core\templates\core\dashboard.html`
- Modify: `D:\installment-system-test\installments\core\static\core\css\app.css`

**Step 1: Add reusable classes to dashboard cards**

Use classes like:

```html
<div class="card stat metric-card metric-success border-0 shadow-sm">
```

For overdue card:

```html
<div class="card stat overdue-card border-0 shadow-sm">
```

**Step 2: Add CSS**

```css
.metric-card {
  position: relative;
  overflow: hidden;
}

.metric-card::after {
  content: "";
  position: absolute;
  inset-inline-end: -34px;
  top: -34px;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: var(--brand-soft);
  opacity: .75;
}

.metric-card .card-body {
  position: relative;
  z-index: 1;
}

.overdue-card {
  border-color: #FECACA !important;
  background: linear-gradient(180deg, #fff, #fff7f7);
}

.overdue-card .card-title {
  color: var(--danger);
  font-weight: 800;
}

.table-sm td,
.table-sm th {
  padding: .6rem .65rem;
}
```

**Step 3: Keep existing data logic**

Do not change `views.py` in this task unless display requires new values. The dashboard already has:
- `due_today`
- `overdue_by_customer`
- `total_expected_today`
- `income_this_month`

**Step 4: Verify**

Run tests:
```bash
cd /d/installment-system-test/installments
source ../venv/Scripts/activate
python manage.py test
```

Expected:
```text
Ran 86 tests
OK
```

Manual check:
- `http://127.0.0.1:8001/`
- Login: `admin` / `admin123`
- Dashboard does not overflow on small width.
- Overdue summary shows customer / count / total.

**Step 5: Commit**

```bash
git add installments/core/templates/core/dashboard.html installments/core/static/core/css/app.css
git commit -m "style: improve dashboard financial overview"
```

---

### Task 5: Improve Tables Across Lists

**Objective:** الجداول المهمة تبقى أسهل في القراءة، خصوصاً العقود والأقساط والعملاء.

**Files:**
- Modify: `D:\installment-system-test\installments\core\static\core\css\app.css`
- Optional modify:
  - `installments/core/templates/core/contracts_list.html`
  - `installments/core/templates/core/installments_list.html`
  - `installments/core/templates/core/customers_list.html`

**Step 1: Add table polish CSS**

```css
.table-responsive {
  border-radius: 16px;
}

.table-hover tbody tr:hover {
  background: #F3FAF5;
}

.table td,
.table th {
  border-color: var(--line);
}

.table thead th {
  background: var(--surface-soft);
  color: var(--muted);
}

.status-dot {
  width: .55rem;
  height: .55rem;
  display: inline-block;
  border-radius: 50%;
  margin-inline-start: .35rem;
}

.status-dot.success { background: var(--brand); }
.status-dot.danger { background: var(--danger); }
.status-dot.warning { background: var(--warning); }
```

**Step 2: Optional status markup**

In `contracts_list.html`, use badges instead of plain text:

```html
<td>
  {% if contract.status == 'active' %}<span class="badge bg-success">نشط</span>
  {% elif contract.status == 'completed' %}<span class="badge bg-primary">مكتمل</span>
  {% elif contract.status == 'overdue' %}<span class="badge bg-danger">متأخر</span>
  {% else %}<span class="badge bg-secondary">ملغي</span>{% endif %}
</td>
```

**Step 3: Verify key pages**

Open:
```text
http://127.0.0.1:8001/contracts/
http://127.0.0.1:8001/installments/
http://127.0.0.1:8001/customers/
```

Expected:
- No template errors.
- Tables are readable.
- Money columns are aligned and not wrapping.

**Step 4: Commit**

```bash
git add installments/core/static/core/css/app.css installments/core/templates/core/contracts_list.html installments/core/templates/core/installments_list.html installments/core/templates/core/customers_list.html
git commit -m "style: polish list tables and status badges"
```

---

### Task 6: Redesign Customer Detail Page Quick Actions

**Objective:** صفحة العميل تبقى مفيدة أكتر: الأقساط المتأخرة واضحة وزر الدفع سريع.

**Files:**
- Modify: `D:\installment-system-test\installments\core\templates\core\customers_detail.html`
- Modify: `D:\installment-system-test\installments\core\static\core\css\app.css`

**Step 1: Add `quick-pay-card` class to overdue section**

Existing overdue section should become:

```html
<div class="card stat mb-3 quick-pay-card">
```

**Step 2: Add CSS**

```css
.quick-pay-card {
  border-color: #FECACA;
  background:
    linear-gradient(90deg, rgba(185,28,28,.07), transparent 38%),
    var(--surface);
}

.quick-pay-card h5 {
  font-weight: 900;
}

.quick-pay-card .btn-success {
  font-weight: 800;
}
```

**Step 3: Manual verify**

Open a customer with late installments:
```text
http://127.0.0.1:8001/customers/<id>/
```

Expected order:
1. بيانات العميل
2. العقود
3. الأقساط المتأخرة
4. الأقساط كلها

**Step 4: Commit**

```bash
git add installments/core/templates/core/customers_detail.html installments/core/static/core/css/app.css
git commit -m "style: highlight customer overdue quick pay"
```

---

### Task 7: Improve Payment Page Visual Clarity

**Objective:** صفحة دفع القسط تكون آمنة وواضحة للمستخدم قبل تسجيل الدفع.

**Files:**
- Modify: `D:\installment-system-test\installments\core\templates\core\installments_pay.html`
- Modify: `D:\installment-system-test\installments\core\static\core\css\app.css`

**Step 1: Add a payment summary panel**

If not already clear, add near top:

```html
<div class="payment-summary stat mb-3">
  <div class="d-flex justify-content-between flex-wrap gap-2">
    <div>
      <div class="text-muted small">العقد</div>
      <div class="fw-bold">{{ installment.contract.contract_number }}</div>
    </div>
    <div>
      <div class="text-muted small">العميل</div>
      <div class="fw-bold">{{ installment.contract.customer.name }}</div>
    </div>
    <div>
      <div class="text-muted small">المبلغ المطلوب</div>
      <div class="h5 money text-danger mb-0">{{ installment.amount|mask_money }}</div>
    </div>
  </div>
</div>
```

**Step 2: Add CSS**

```css
.payment-summary {
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  background: linear-gradient(180deg, #fff, #F8FAF8);
}
```

**Step 3: Verify validation still shows clearly**

Manual tests:
- Cash without receiver should show visible error.
- Instapay without sender info should show visible error.
- Valid cash payment should redirect.

Run:
```bash
cd /d/installment-system-test/installments
source ../venv/Scripts/activate
python manage.py test core.test_comprehensive.PaymentFormValidationTests -v2
```

Expected:
```text
OK
```

**Step 4: Commit**

```bash
git add installments/core/templates/core/installments_pay.html installments/core/static/core/css/app.css
git commit -m "style: clarify installment payment screen"
```

---

### Task 8: Add Dark Mode Polish Without Breaking Current Toggle

**Objective:** الحفاظ على زر الوضع الداكن الحالي، لكن بألوان متناسقة مع التصميم الجديد.

**Files:**
- Modify: `D:\installment-system-test\installments\core\static\core\css\app.css`

**Step 1: Add dark variables**

```css
body.theme-dark {
  --app-bg: #07140B;
  --surface: #102116;
  --surface-soft: #132A1B;
  --ink: #EAF5EE;
  --muted: #A9B8AD;
  --line: #24432D;
  --brand-soft: rgba(34, 197, 94, .14);
  background: var(--app-bg);
  color: var(--ink);
}

body.theme-dark .stat,
body.theme-dark .card {
  background: var(--surface);
  color: var(--ink);
  border-color: var(--line);
  box-shadow: none;
}

body.theme-dark .table {
  --bs-table-bg: var(--surface);
  --bs-table-color: var(--ink);
  --bs-table-border-color: var(--line);
  --bs-table-hover-bg: #183B25;
  --bs-table-hover-color: #fff;
}

body.theme-dark .table thead th {
  background: var(--surface-soft);
  color: var(--muted);
}

body.theme-dark .form-control,
body.theme-dark .form-select {
  background: #07140B;
  color: var(--ink);
  border-color: var(--line);
}
```

**Step 2: Verify**

Manual:
- Toggle dark mode from sidebar.
- Check dashboard, contracts list, payment page.
- Text must remain readable.

**Step 3: Commit**

```bash
git add installments/core/static/core/css/app.css
git commit -m "style: polish dark mode theme"
```

---

### Task 9: Full Validation Before Moving to Main Copy

**Objective:** التأكد أن الشكل الجديد آمن قبل نقله للنسخة الأساسية.

**Files:**
- No changes unless fixing issues.

**Step 1: Run tests**

```bash
cd /d/installment-system-test/installments
source ../venv/Scripts/activate
python manage.py test
```

Expected:
```text
Ran 86 tests
OK
```

**Step 2: Manual smoke test pages**

Open and inspect:
```text
http://127.0.0.1:8001/
http://127.0.0.1:8001/contracts/
http://127.0.0.1:8001/customers/
http://127.0.0.1:8001/installments/
http://127.0.0.1:8001/reports/
```

Expected:
- No 500 errors.
- No broken navigation.
- Money values readable.
- RTL layout correct.
- Mobile width works.

**Step 3: Optional screenshot review**

Use browser/computer screenshot to compare:
- Dashboard light
- Dashboard dark
- Contract list
- Customer detail
- Payment page

**Step 4: Commit final test pass**

```bash
git status
git commit --allow-empty -m "test: verify redesigned UI smoke checks"
```

---

### Task 10: Promote Design from Test Copy to Main Project

**Objective:** نقل الشكل الجديد من `D:\installment-system-test` إلى المشروع الأساسي بعد موافقة المستخدم.

**Files likely to copy:**
- `D:\installment-system-test\installments\core\static\core\css\app.css`
- `D:\installment-system-test\installments\core\templates\core\base.html`
- `D:\installment-system-test\installments\core\templates\core\dashboard.html`
- `D:\installment-system-test\installments\core\templates\core\customers_detail.html`
- `D:\installment-system-test\installments\core\templates\core\contracts_list.html`
- `D:\installment-system-test\installments\core\templates\core\installments_pay.html`

**Step 1: Confirm user approval**

Ask user to approve after seeing test server screenshots/pages.

**Step 2: Backup main project state**

```bash
cd ~/installment-system
git status
git add -A
git commit -m "chore: backup before UI redesign merge"
```

If nothing to commit, continue.

**Step 3: Copy only approved files**

Use file copy or patch carefully. Do not copy database or media.

**Step 4: Run tests in main project**

```bash
cd ~/installment-system/installments
source ../venv/Scripts/activate
python manage.py test
```

Expected:
```text
Ran 86 tests
OK
```

**Step 5: Restart main server**

```bash
cd ~/installment-system/installments
source ../venv/Scripts/activate
DJANGO_ALLOWED_HOSTS='*' waitress-serve --port=8000 --host=0.0.0.0 installments.wsgi:application
```

**Step 6: Commit and push**

```bash
cd ~/installment-system
git add -A
git commit -m "style: apply redesigned financial UI"
git push origin codex-updates
```

---

## Files Likely to Change

### Primary
- `D:\installment-system-test\installments\core\templates\core\base.html`
- `D:\installment-system-test\installments\core\static\core\css\app.css`
- `D:\installment-system-test\installments\core\templates\core\dashboard.html`
- `D:\installment-system-test\installments\core\templates\core\customers_detail.html`
- `D:\installment-system-test\installments\core\templates\core\contracts_list.html`
- `D:\installment-system-test\installments\core\templates\core\installments_pay.html`

### Optional Later
- `D:\installment-system-test\installments\core\templates\core\products_list.html`
- `D:\installment-system-test\installments\core\templates\core\products_detail.html`
- `D:\installment-system-test\installments\core\templates\core\reports_index.html`
- `D:\installment-system-test\installments\core\templates\core\reports_profit.html`
- `D:\installment-system-test\installments\core\templates\core\settings.html`

---

## Tests / Validation

### Automated

Run after every 1-2 tasks:

```bash
cd /d/installment-system-test/installments
source ../venv/Scripts/activate
python manage.py test
```

Expected:
```text
Ran 86 tests
OK
```

### Manual Smoke Tests

Login:
```text
admin / admin123
```

Pages:
```text
http://127.0.0.1:8001/
http://127.0.0.1:8001/contracts/
http://127.0.0.1:8001/customers/
http://127.0.0.1:8001/installments/
http://127.0.0.1:8001/reports/
```

Checklist:
- [ ] RTL correct.
- [ ] Sidebar opens/collapses.
- [ ] Dark mode readable.
- [ ] Mobile layout works.
- [ ] Money values readable and not wrapping.
- [ ] Payment validation errors visible.
- [ ] No work happens on real `db.sqlite3`.

---

## Risks, Tradeoffs, and Open Questions

### Risks
- Moving all CSS out of `base.html` can briefly cause missing styles if static path is wrong.
- Dark mode may need per-page tweaks after central CSS changes.
- Some templates use compressed one-line HTML, so edits should be careful and tested.

### Tradeoffs
- Keeping Bootstrap is faster and safer than rebuilding UI from scratch.
- External fonts could improve branding but may slow local/LAN use or require internet, so avoid for now.
- A bold design should not reduce data density; accounting users need fast scanning.

### Open Questions for User
1. تحب الشكل يكون **أخضر مالي هادي** ولا **أزرق إداري** ولا **داكن بروفيشنال**؟
2. هل نغيّر كل الصفحات مرة واحدة ولا نبدأ بـ Dashboard + العقود + العميل + الدفع؟
3. هل تحب نضيف Logo/اسم تجاري بدل “نظام التقسيط”؟
4. هل تريد نسخة startup/shortcut منفصلة للنسخة التجريبية على بورت `8001`؟

---

## Recommended Execution Order

1. Apply Task 1–2 to create safe design foundation.
2. Show user screenshot of dashboard from test copy.
3. If approved, continue Tasks 3–8.
4. Run Task 9 validation.
5. Only then promote to main project with Task 10.

