# التسوية الذكية للدفعات + الإقفال التلقائي عند السداد الكامل

> **For Hermes:** تنفيذ مباشر — مهام صغيرة متسلسلة على نفس الملفات.

**Goal:** إعادة تصميم لوجيك الدفع بحيث أي مبلغ يدفعه العميل يتوزع **تلقائيًا** على الأقساط (الشهر الحالي الأول، ثم الشهور الجاية بالترتيب)، والعقد يتقفل **تلقائيًا** لحظة وصول إجمالي المسدد = قيمة العقد، مع تنويه صريح قبل الإقفال وعلامة "خلاص" جنب العميل في صفحته.

**Architecture:** تعديل `installment_pay` ليستقبل "مبلغ الدفعة" فقط ويوزعه عبر دالة تسوية مركزية `_apply_payment_across_installments(contract, amount, date, method...)` تخصص المبلغ للأقساط بالترتيب (partial أولًا ثم pending/late)، وتسجل كل دفعة في ActivityLog. الإقفال: لما `total_paid >= total_amount` → تنويه في صفحة الدفع قبل التأكيد (JS confirm يوضح "هذا الدفعة هتكمل قيمة العقد") + بعد الحفظ status=`completed` تلقائيًا والأقساط المغطاة تتعلّم paid. علامة ✅ جنب اسم العميل في `customers_list.html` لو كل عقوده خلاص (أو لكل عقد خلاص).

---

## السياق

- الفلسفة المعتمدة من المستخدم:
  1. هدف العقد الوحيد = سداد كامل القيمة خلال مدته. الإغلاق لا يتم إلا عند اكتمال المبلغ.
  2. القسط الشهري يُدفع في ميعاده، الزيادة مقبولة.
  3. سيناريو الدفع المقبول (اختيار المستخدم): **سداد شهر حالي + الزيادة تُخصم تلقائيًا من الشهر التالي** (أو أي مبلغ على بعضه يوزعه النظام بنفس المنطق).
- الإقفال: عند `إجمالي المدفوع == total_amount` في أي وقت، مع تنويه قبل الإقفال.
- UI: في خانة العملاء — العقد المنتهي يتعلّم جنبه.

## المهام

### Task 1 — دالة التوزيع المركزي
`core/views.py`: دالة جديدة:

```python
def _apply_payment(contract, amount, pay_date, method="", **meta):
    """وزّع المبلغ على أقساط العقد بالترتيب: جزئي أولًا ثم معلق/متأخر.
    ترجع list[(installment, applied_amount)]."""
```

- ترتيب الأقساط: `order_by("installment_number")`.
- لكل قسط: `shortfall = amount - paid_amount`؛ لو > 0 ضع منه حتى يكتمل.
- استمر حتى ينفد المبلغ أو الأقساط تخلص (الفائض يرفض برسالة "المبلغ أكبر من إجمالي المتبقي").
- حدّث status لكل قسط ممسوس (paid إذا اكتمل / partial إن نقص) + paid_date + payment_method + meta (receiver, transfer...).
- حدّث حالة العقد عبر `_refresh_contract_status`.

### Task 2 — إعادة ربط صفحة الدفع
`installment_pay`:
- الفورم يستقبل **مبلغ الدفعة الكلي** (زي ما هو).
- بعد التحقق: استدعاء `_apply_payment` بدل المنطق الحالي (previous_paid + form.save).
- الإيصال يتحوّل لآخر قسط اتلمس (أو صفحة إيصال مجمعة — نبدأ بآخر قسط).

### Task 3 — تنويه ما قبل الإقفال
في `installments_pay.html`: حساب JS بسيط:
- `remaining_total` متاح في context.
- لو `paid_amount_input >= remaining_total` → confirm message: "⚠️ هذا الدفع هيكمل قيمة العقد كاملة — العقد هيقفل تلقائيًا. متابعة؟"

### Task 4 — الإقفال التلقائي
بعد نجاح `_apply_payment`:
```python
if contract.total_paid >= contract.total_amount and contract.status != Contract.STATUS_EARLY_COMPLETED:
    contract.status = Contract.STATUS_COMPLETED  # خلاص حقيقي بالفلوس
    contract.save(update_fields=["status"])
```
- رسالة نجاح خاصة: "🎉 تم سداد كامل قيمة العقد — العقد اتقفل."
- ActivityLog: ACTION_PAYMENT + علم completion.

### Task 5 — علامة الخلاص في خانة العملاء
`customers_list.html` + `customer_list` view:
- annotate لكل عميل: عدد العقود + عقود "غير مكتملة السداد":
```python
Count("contract", filter=~Q(contract__status__in=[COMPLETED, EARLY_COMPLETED]))
```
- عمود جديد "الحالة": لو مفيش عقود غير مكتملة وعنده عقود → badge أخضر "خلاص ✅"؛ لو عنده عقود نشطة → "جاري".
- وكذلك في تفاصيل العميل: كل عقد خلاص جنبه علامة ✅.

### Task 6 — اختبارات
`core/test_smart_payment.py`:
1. دفع قيمة قسطين مرة واحدة → القسط الأول paid والثاني paid/partial حسب المبلغ.
2. زيادة على القسط الحالي → تمسح نقص القسط التالي.
3. سداد كامل بدري → العقد completed تلقائيًا.
4. دفع أكبر من المتبقي → مرفوض برسالة واضحة.
5. partial ثم مكملته بعدين → يكتمل صح.
6. الأقساط المغلقة (early) مش بتستقبل دفعات.

Run: `manage.py test core -v 2` → 92 + ~6 = pass.

### Task 7 — ريستارت + تحقق بصري + push
- تجربة عملية على عقد تجريبي: دفع مزدوج، إقفال تلقائي، علامة ✅.
- commit + push codex-updates.
