# Early Completion Lock: منع تسجيل دفعات على عقد "مكتمل يدويًا"

> **For Hermes:** تنفيذ مباشر (مش subagents) — مهام صغيرة متسلسلة على نفس الملفات.

**Goal:** لما صاحب النظام يضغط "تعليم كمكتمل" على عقد العميل خلّص تمن أقساط بدري (والباقي يُعفى عنه)، العقد يتقفل نهائيًا: مفيش زرار "دفع" يظهر على الأقساط المتبقية، وأي محاولة دفع بالـ URL مباشرة تترفض، والشيت يوضح إن العقد اتقفل مبكرًا.

**Architecture:** إضافة حالة `early_completed` جديدة على موديل Contract (متميزة عن `completed` العادي)، مع حاجز حماية (guard) في `installment_pay` + `installment_edit`، وإخفاء أزرار الدفع في القوالب لما العقد يكون مقفول، وعرض بانر توضيحي. الحالة الجديدة تظهر كـ"مكتمل" في كل التقارير والإحصائيات الحالية (بدون ما نكسر أي فلتر موجود).

**Tech Stack:** Django 5.2 / SQLite — models, views, templates, tests.

---

## السياق الحالي (المشكلة)

- عقد CON-000012 (غلاب): 12 قسط، العميل خلّص **10 أقساط** (= قيمة العقد كلها 4,875).
- المستخدم ضغط **"تعليم كمكتمل"** → الكود الحالي بيعمل `paid_amount = amount` لكل الأقساط غير المدفوعة → القسطين 11 و12 بقوا "مدفوعين" ببلاش.
- لو بعدين العميل جاي يسدد القسطين دول فعليًا (كهدية أو تسوية) → هيدوس "دفع" → **المدفوع الإجمالي يعدي 4,875** → الباقي يبقى سالب وتقرير الأرباح يتلخبط.

### اللوجيك المطلوب
1. "تعليم كمكتمل" على عقد فيه أقساط غير مدفوعة = **إغلاق مبكر** (early completion): العقد يخلص، الأقساط المتبقية تتقفل (status جديد `closed` — مش مدفوع)، ومجموع المدفوع يفضل زي ما هو.
2. عقد `early_completed`:
   - مفيش زرار "دفع" على أقساطه.
   - محاولات دفع/تعديل بالـ URL → رسالة خطأ ورفض.
   - الشيت يعرض بانر: "العقد اتقفل مبكرًا بتاريخ X — الأقساط المتبقية معفاة".
3. الفرق بين الحالتين في العرض: `completed` = كل الأقساط اتدفعت فعلًا. `early_completed` = اتقفل قبل السداد الكامل.

---

### Task 1: إضافة حالة `early_completed` للموديل

**Files:**
- Modify: `C:/Users/Elnour Tech/installment-system/installments/core/models.py` (Contract.STATUS_* block ~lines 236-246)

**Step 1:** بعد `STATUS_CANCELLED = "cancelled"` أضف:

```python
    STATUS_EARLY_COMPLETED = "early_completed"
```

**Step 2:** داخل `STATUS_CHOICES` أضف:

```python
        (STATUS_EARLY_COMPLETED, "مكتمل (إغلاق مبكر)"),
```

**Step 3:** property مساعد على Contract:

```python
    @property
    def is_early_completed(self):
        return self.status == self.STATUS_EARLY_COMPLETED
```

**Step 4:** Verify: `python manage.py check` → 0 issues. (الحالة نصية — مفيش migration.)

### Task 2: توافق الفلاتر والإحصائيات مع الحالة الجديدة

**Files:**
- Modify: `core/views.py`
  - `contract_list` filter options (template `contracts_list.html` select status)
  - `dashboard` `completed_count` (~line 809)
  - `_refresh_contract_status` (~line 707): لازم ما ترجعش عقد `early_completed` لـ active/overdue

**Step 1:** في `_refresh_contract_status` أول سطر:

```python
    if contract.status == contract.STATUS_EARLY_COMPLETED or contract.status == contract.STATUS_COMPLETED and False:
        return  # early-completed contracts stay closed
```

(النظيف: `if contract.status == Contract.STATUS_EARLY_COMPLETED: return`)

**Step 2:** في dashboard/reports أي `.filter(status=Contract.STATUS_COMPLETED)` للعدّادات المالية يبقى:

```python
contracts.filter(status__in=[Contract.STATUS_COMPLETED, Contract.STATUS_EARLY_COMPLETED])
```

**Step 3:** `contracts_list.html`: أضف option "مكتمل (إغلاق مبكر)" بقيمة `early_completed`.

**Step 4:** Verify: `manage.py check` + افتح الرئيسية والتقارير — مفيش crash.

### Task 3: تعديل "تعليم كمكتمل" ليستخدم الإغلاق المبكر

**Files:**
- Modify: `core/views.py` `contract_mark_completed` (~line 1464)

**Step 1:** استبدال منطق التسوية: بدل ما يحط `paid_amount=amount` للأقساط غير المدفوعة:

```python
        had_unpaid = contract.installments.exclude(status=Installment.STATUS_PAID).exists()
        if had_unpaid:
            # إغلاق مبكر: اقفل الأقساط المتبقية بدون تسجيل دفع وهمي
            contract.status = Contract.STATUS_EARLY_COMPLETED
            contract.installments.exclude(status=Installment.STATUS_PAID).update(
                status=Installment.STATUS_CLOSED,
            )
        else:
            contract.status = Contract.STATUS_COMPLETED
        contract.save(update_fields=["status"])
```

**Step 2:** الرسالة تتفرع:

```python
        if contract.status == Contract.STATUS_EARLY_COMPLETED:
            msg = "تم إغلاق العقد مبكرًا — الأقساط المتبقية اعتبرت معفاة ولن تُحسب عليه."
        else:
            msg = "تم تعليم العقد كمكتمل."
```

**Step 3:** الـ confirm message في `contracts_detail.html` زرار "تعليم كمكتمل" يتحدث:

```html
onsubmit="return confirm('لو فيه أقساط غير مدفوعة هيتم إغلاق العقد مبكرًا ومعافتها. متأكد؟');"
```

**Verify:** جرّب على عقد تجريبي فيه قسطين غير مدفوعين: بعد الضغط — status = early_completed، القسطين status=closed، paid_amount زي ما هو.

### Task 4: حالة `closed` للأقساط + حاجز الدفع

**Files:**
- Modify: `core/models.py` Installment.STATUS_* (~line 402):

```python
    STATUS_CLOSED = "closed"
```

وأضف للـ STATUS_CHOICES:

```python
        (STATUS_CLOSED, "معفي"),
```

- Modify: `core/views.py`:

**Step 1:** guard في `installment_pay` بعد جلب القسط:

```python
    if installment.contract.status == Contract.STATUS_EARLY_COMPLETED:
        messages.error(request, "العقد مغلق مبكرًا — لا يمكن تسجيل دفعات عليه.")
        return redirect("core:contract_detail", id=installment.contract_id)
```

**Step 2:** نفس الـ guard في `installment_edit`.

**Step 3:** `_mark_late_installments`: استثنى أقساط العقود المغلقة:

```python
    late_qs = Installment.objects.filter(
        due_date__lt=_today(),
        status=Installment.STATUS_PENDING,
    ).exclude(contract__status=Contract.STATUS_EARLY_COMPLETED)
```

وكذلك في `contract_detail`/`summary` منطق "لم يتم السداد — متأخر": القسط `closed` يظهر "معفي" بدل متأخر.

**Step 4:** `installments_list.html` + `contracts_detail.html` badges: أضف حالة `closed` → badge رمادي "معفي".

### Task 5: إخفاء أزرار الدفع على العقود المغلقة + بانر الشيت

**Files:**
- Modify: `core/templates/core/contracts_detail.html`
- Modify: `core/templates/core/contract_summary.html`

**Step 1:** في جدول الأقساط (الاتنين):

```django
{% if contract.is_early_completed and installment.status == 'closed' %}
  <span class="badge bg-secondary">معفي</span>
{% else %}
  ...أزرار دفع/تعديل الحالية...
{% endif %}
```

**Step 2:** بانر فوق شيت العقد:

```django
{% if contract.is_early_completed %}
<div class="alert alert-warning no-print">
  <i class="bi bi-lock-fill ms-1"></i>
  هذا العقد اتقفل مبكرًا — الأقساط المتبقية معفاة ومجموع المسدد هو قيمة العقد النهائية.
</div>
{% endif %}
```

### Task 6: اختبارات (TDD-style سريعة)

**Files:**
- Modify: `core/tests.py` (أو test file جديد `test_early_completion.py`)

**Tests:**

```python
def test_mark_completed_with_unpaid_closes_early(self):
    # عقد بقسطين: واحد مدفوع وواحد pending
    # POST mark_completed
    # assert: contract.status == 'early_completed'
    # assert: pending installment.status == 'closed', paid_amount unchanged
    # assert: total_paid == القيمة المدفوعة فقط (مش total_amount)

def test_pay_blocked_on_early_completed(self):
    # عقد early_completed + قسط closed
    # GET/POST installment_pay → redirect مع message error، paid_amount لم يتغير

def test_edit_blocked_on_early_completed(self):
    # نفس الفكرة لـ installment_edit

def test_closed_not_marked_late(self):
    # _mark_late_installments ما يمسش أقساط closed

def test_full_payment_still_completes_normally(self):
    # عقد تدفع كل أقساطه واحدة واحدة → status='completed' (مش early)
```

**Run:** `python manage.py test core -v 2` → all pass (87 حالي + ~5 جداد).

### Task 7: ريستارت + تحقق بصري + رفع GitHub

1. ريستارت السيرفر (`DJANGO_DEBUG=false`, port 8000).
2. تحقق بصري على عقد CON-000012: الزرار مخفي على القسطين، البادج "معفي"، الشيت سليم، المدفوع ثابت 4,875.
3. Commit: `feat: early completion lock — close contracts with waived remaining installments` → push `codex-updates`.

---

## Risks & Tradeoffs

| الخطر | المعالجة |
|---|---|
| تقارير قديمة بتعد "completed" بس | عدّلنا العدّادات لتشمل الحالتين — مراجعة `reports_dashboard` |
| مستخدم يفتح عقد مغلق بالغلط | البانر + البادج "معفي" واضحين |
| `_refresh_contract_status` يقلب العقد لـ overdue | Guard في أول الدالة |
| أقساط partial على عقد بيتقفل مبكر | تبقى partial زي ما هي (مدفوع جزئي محسوب) وتتقفل برضه |

## Open Questions
- هل نسمح بـ "إعادة فتح" عقد مغلق مبكر؟ (مقترح: لأ دلوقتي — YAGNI، نضيفها لو احتجتها)
