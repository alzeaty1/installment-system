# بلان: إصلاح مبلغ "أحدث المدفوعات" في الداشبورد (دايمًا صفر)

## المشكلة
جدول "أحدث المدفوعات" في الداشبورد بيعرض العقد والعميل صح، لكن عمود المبلغ دايمًا صفر.

## السبب الجذري (مؤكد من الكود)
- الكاتب `installments/core/views.py:1778-1779` بيسجّل الدفع في `ActivityLog` بالمفاتيح:
  `previous_value={"total_paid": ...}` و `new_value={"total_paid": ...}`
- القارئ `installments/core/views.py:947` بيحسب الفرق بمفاتيح **مختلفة**:
  `log.new_value.get("paid_amount", "0") - log.previous_value.get("paid_amount", "0")`
- المفاتيح غير موجودة → `Decimal("0") - Decimal("0") = 0` دايمًا.
- الـ fallback (`except → inst.paid_amount`) لا يعمل أبدًا لأن `.get(..., "0")` لا يرمي exception.
- العقد والعميل ظاهرين صح لأنهم من علاقة `inst.contract` مش من الـ log.

## الإصلاح (تاسك واحد، سطرين تقريبًا — في القارئ فقط، بدون لمس مسار الدفع)
في `installments/core/views.py:946-949`:
1. قراءة الفرق من مفاتيح `total_paid` (اللي الكاتب فعلًا بيخزنها):
   `payment_amount = Decimal(new.total_paid) - Decimal(prev.total_paid)`
2. تفعيل الـ fallback الحقيقي: لو المفاتيح ناقصة (لوجات قديمة) **أو** الناتج صفر، استخدم `inst.paid_amount`.
3. حماية: لو `log.new_value/previous_value` مش dict (None أو غيره) → fallback مباشرة بدون exception صامتة.

ليه القارئ مش الكاتب؟ `contract.total_paid` = مجموع `paid_amount` (models.py:366)، واللوج يتكتب بعد الحفظ، فالفرق = مبلغ الدفعة بالظبط. تعديل الكاتب كان هيلمس مسار دفع حساس بدون داعي.

## التحقق قبل "تم"
- `python manage.py check`
- سويت الاختبارات الخاصة بالدفع (`core/tests.py` فيها `test_...payment...` + سطر 454 يتأكد من لوك الدفع)
- معاينة حية للداشبورد: تسجيل دفعة بمبلغ معلوم → يظهر نفس المبلغ في "أحدث المدفوعات"

## الرفع
- commit واضح → `git push origin codex-updates`

## ملاحظة تنفيذ (لـ ZCode)
- التنفيذ في القارئ فقط (داشبورد `recent_payments`)، ممنوع تعديل `_apply_payment` أو سطر كتابة اللوج (1772-1780) أو أي validation (`#26` مقدم>قيمة، `#31` دفع قبل البداية).
