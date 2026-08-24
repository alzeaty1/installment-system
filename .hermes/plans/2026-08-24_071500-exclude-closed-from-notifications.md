# استثناء الأقساط المعفاة من التنبيهات والمتأخرات

> **For Hermes:** تنفيذ مباشر — تاسك واحد صغير، مش محتاج subagents.

**Goal:** الأقساط "المعفاة" (closed) على العقود المغلقة مبكرًا ما تظهرش في: التنبيهات، أقساط اليوم، المتأخرات، وعدّادات لوحة التحكم — لأنها مش دين فعلي.

**Architecture:** إضافة `exclude(status=STATUS_CLOSED)` في 4 مواضع بتستعلم عن الأقساط "المطلوب سدادها". الحالة `closed` أصلاً مستثناة من `_mark_late_installments` (اتعملت في الإغلاق المبكر)، لكن الاستعلامات اللي بتجيب "غير مدفوع" لسه بتحسبها.

**Tech Stack:** Django ORM — تعديلات view-level فقط، مفيش migrations.

---

## السياق

- حالة القسط الجديدة `closed` ("معفي") بتتولد لما عقد يتقفل مبكرًا.
- `_mark_late_installments` بيستثني عقود `early_completed` ✅ (متظبط).
- لكن: `due_date__lte=today).exclude(status=paid)` بيجيب closed برضه ❌ → تنبيهات زورو على فلوس مش مطلوبة.
- حاليًا mafeesh حالات closed في الداتابيز (0) — يعني التغيير ده وقاية قبل ما تحصل أول حالة.

## Task 1: استثناء closed من الاستعلامات الأربعة

**Files:**
- Modify: `C:/Users/Elnour Tech/installment-system/installments/core/views.py`

**التعديل 1 — التنبيهات (`notification_check_due` ~line 1937):**

```python
        due_installments = (
            Installment.objects
            .filter(account=request.current_account)
            .select_related("contract", "contract__customer")
            .filter(due_date__lte=_today())
            .exclude(status__in=[Installment.STATUS_PAID, Installment.STATUS_CLOSED])
        )
```

**التعديل 2 — أقساط اليوم (`installment_due_today` ~line 1839):**

```python
    installments = (
        Installment.objects
        .filter(account=request.current_account)
        .select_related("contract", "contract__customer")
        .filter(due_date=_today())
        .exclude(status__in=[Installment.STATUS_PAID, Installment.STATUS_CLOSED])
    )
```

**التعديل 3 — عدّاد متأخرات لوحة التحكم (~line 789 منطقة overdue):**

أي استعلام overdue في dashboard يستخدم `.exclude(status=Installment.STATUS_LATE)` أصلاً — أتأكد منه وقت التنفيذ وأستبعد closed لو كان `exclude(paid)` فقط.

**التعديل 4 — واتساب/عرض جدول العقد:** الأزرار أصلاً مخفية على closed في القالب ✅ (اتعملت في الإغلاق المبكر) — أتأكد بس إن `_get_whatsapp_url` مش بينده على closed (مش هيتنادى لأن الزرار مخفي).

**Verify:** `manage.py check` + `manage.py test` → 97 PASS + اختبار جديد.

## Task 2: اختبار يمنع الرجوع للخلف

**Files:**
- Create: `core/test_notifications_exclude_closed.py`

```python
def test_closed_installment_gets_no_notification(self):
    # عقد early_completed بقسط closed مستحق فات
    # POST notification_check_due
    # assert: مفيش Notification على القسط المعفي

def test_closed_not_in_due_today(self):
    # GET installment_due_today → القسط المعفي مش ظاهر
```

**Run:** `manage.py test core -v 2` → 97 + 2 = 99 PASS.

## Task 3: ريستارت + تحقق + رفع GitHub

1. ريستارت السيرفر (DJANGO_DEBUG=false).
2. تحقق: صفحة الأقساط والتنبيهات شغالين عادي.
3. Commit: `fix: exclude waived (closed) installments from notifications and due lists` → push codex-updates.

---

## Risks

| الخطر | المعالجة |
|---|---|
| نسيان مكان استعلام | الفحص بالـ grep على `exclude(status=Installment.STATUS_PAID)` |
| تغيير سلوك قوائم موجودة | الاختبارات تغطي؛ التغيير حصري على closed فقط |

## Open Questions
- لا شيء — النطاق ضيق ومحدد.

## Flow المتبقي بعد هذا الـ Plan (حسب طلب المستخدم)
تنفيذ Task 1 → عرض النتيجة → موافقة → Task 2 → رفع GitHub وعرض → Task 3 → مراجعة نهائية وتسليم.
