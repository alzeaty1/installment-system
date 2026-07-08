# Fixed-Term Contract Date Tracking with Flexible Payments — Implementation Plan

> **For Hermes:** Implement task-by-task with TDD. Each task = failing test → code → pass → commit.

**Goal:** Add fixed `end_date` to contracts, `overpaid` installment status, contract status properties, and receipt discrepancy display — without breaking existing data or field names.

**Architecture:** Evolutionary changes on the existing Django 5.2 models. We keep existing field names (`amount`, `paid_amount`, `paid_date`, `late`) and ADD new capabilities on top. No field renames — that would break templates, views, and 12 migrations of existing data.

**Key decisions (pragmatic mapping from spec → codebase):**
- Spec's `base_amount` → existing `amount` field (no rename)
- Spec's `amount_paid` → existing `paid_amount` field (no rename)
- Spec's `paid_at` (DateTimeField) → existing `paid_date` (DateField) is sufficient (no rename)
- Spec's `overdue` status → existing `late` status (no rename, same semantics)
- Spec's `overpaid` status → **NEW** — add to choices
- Spec's `end_date` on Contract → **NEW** field
- Spec's `post_save` signal → keep existing `_generate_installments()` called from `contract_create` view (already works, no signal needed)
- Spec's `relativedelta` → use existing `_add_months()` helper (already handles day-clamping)

**Tech Stack:** Django 5.2, SQLite, Bootstrap 5, python-dateutil (installed)

---

## Files That Will Change

| File | Change Type |
|------|-------------|
| `installments/core/models.py` | Add `end_date` field to Contract, `overpaid` status to Installment, 4 properties to Contract |
| `installments/core/views.py` | Update `installment_pay` status logic, fix carryover in `contract_summary`, update `installment_receipt` context |
| `installments/core/templates/core/receipt_detail.html` | Add expected/difference rows with color coding |
| `installments/core/templates/core/contract_summary.html` | Fix "المتبقي" column to use actual remaining, not base amount |
| `installments/core/migrations/0013_*` | New migration for `end_date` + `overpaid` status |
| `installments/core/test_comprehensive.py` | New tests for all features |

---

## Task 1: Add `end_date` field to Contract model

**Objective:** Store a calculated, immutable end date on every contract.

**Files:**
- Modify: `installments/core/models.py` (Contract model, ~line 298 after `start_date`)
- Migration: `installments/core/migrations/0013_contract_end_date.py`

**Step 1: Write failing test**

```python
# test_comprehensive.py — add to ContractNumberGenerationTests or new class
class ContractEndDateTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.customer = Customer.objects.create(name="End Date Test", phone="010", account=Account.objects.first())
    
    def test_end_date_is_calculated_on_save(self):
        """end_date = start_date + months_count via _add_months."""
        from datetime import date
        contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=10,
            installment_amount=Decimal("100"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=Account.objects.first(),
        )
        # 10 months from June 8, 2025 → April 8, 2026
        self.assertEqual(contract.end_date, date(2026, 4, 8))
    
    def test_end_date_not_overwritten_on_resave(self):
        """end_date is set once and not changed on subsequent saves."""
        from datetime import date
        contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=3,
            installment_amount=Decimal("333.33"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=Account.objects.first(),
        )
        original_end = contract.end_date
        contract.save()  # re-save
        self.assertEqual(contract.end_date, original_end)
```

**Step 2: Run test — expect FAIL** (no `end_date` field)

```bash
cd installments && python manage.py test core.test_comprehensive.ContractEndDateTests -v2
```

**Step 3: Add field + override save()**

In `models.py`, Contract model:
- After `start_date` field (line 298), add:
```python
    end_date = models.DateField(null=True, blank=True, verbose_name="تاريخ نهاية العقد")
```

- In `save()` method (line 323), BEFORE `super().save()`:
```python
    if not self.end_date and self.start_date and self.months_count:
        self.end_date = _add_months(self.start_date, self.months_count, self.payment_due_day)
```

Note: `_add_months` is in views.py, not models.py. We need a local version or import. Better to add a module-level helper in models.py:

```python
import calendar

def _add_months(source_date, months, due_day=1):
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return source_date.replace(year=year, month=month, day=min(int(due_day), last_day))
```

**Step 4: Create migration**

```bash
cd installments && python manage.py makemigrations core --name contract_end_date
python manage.py migrate
```

**Step 5: Run test — expect PASS**

**Step 6: Backfill existing contracts**

```bash
python manage.py shell -c "
from core.models import Contract, _add_months
for c in Contract.objects.filter(end_date__isnull=True):
    c.end_date = _add_months(c.start_date, c.months_count, c.payment_due_day)
    c.save(update_fields=['end_date'])
print(f'Backfilled {Contract.objects.filter(end_date__isnull=True).count()} remaining')
"
```

**Step 7: Commit**
```bash
git add -A && git commit -m "feat: add end_date to Contract (calculated from start_date + months_count)"
```

---

## Task 2: Add `overpaid` status to Installment

**Objective:** When a customer pays more than the installment amount, status = `overpaid`.

**Files:**
- Modify: `installments/core/models.py` (Installment model, ~line 345-355)

**Step 1: Write failing test**

```python
class OverpaidStatusTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="Overpay Test", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=2,
            installment_amount=Decimal("500"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=self.account,
        )
        Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            account=self.account,
        )

    def test_overpaid_status_when_paid_exceeds_amount(self):
        """Direct DB update — status should be 'overpaid' when paid > amount."""
        inst = self.contract.installments.first()
        inst.paid_amount = Decimal("600")
        inst.status = Installment.STATUS_OVERPAID
        inst.save()
        self.assertEqual(inst.status, "overpaid")
        self.assertIn(("overpaid", "زيادة"), Installment.STATUS_CHOICES)
```

**Step 2: Run test — expect FAIL** (no `STATUS_OVERPAID`)

**Step 3: Add status constant + choice**

In `models.py`, Installment model:
```python
    STATUS_OVERPAID = "overpaid"
    
    STATUS_CHOICES = [
        (STATUS_PENDING, "معلق"),
        (STATUS_PAID, "مدفوع"),
        (STATUS_LATE, "متأخر"),
        (STATUS_PARTIAL, "جزئي"),
        (STATUS_OVERPAID, "زيادة"),
    ]
```

**Step 4: Create migration** (choices change → Django may want a migration, but choices don't require one. Only field changes do.)

Actually, adding choices doesn't require a migration in Django — choices are Python-only. But if `status` field's `choices` param changed, Django's `makemigrations` won't detect it (choices aren't stored in DB). So no migration needed.

**Step 5: Run test — expect PASS**

**Step 6: Commit**
```bash
git add -A && git commit -m "feat: add 'overpaid' status to Installment model"
```

---

## Task 3: Update `installment_pay` to set `overpaid` status

**Objective:** Payment logic should set `overpaid` when paid_amount > amount.

**Files:**
- Modify: `installments/core/views.py` (~line 1264-1270, `installment_pay` function)

**Step 1: Write failing test**

```python
class PaymentOverpaidStatusTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="Pay Over Test", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=2,
            installment_amount=Decimal("500"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=self.account,
        )
        self.inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            account=self.account,
        )

    def test_pay_more_than_amount_sets_overpaid(self):
        """Paying 600 on a 500 installment → status = overpaid."""
        r = self.client.post(reverse("core:installment_pay", args=[self.inst.id]), {
            "paid_amount": "600.00",
            "paid_date": "2025-07-10",
            "payment_method": "cash",
            "received_by": "Test User",
        })
        self.assertEqual(r.status_code, 302)  # redirect to receipt
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.paid_amount, Decimal("600.00"))
        self.assertEqual(self.inst.status, Installment.STATUS_OVERPAID)
```

**Step 2: Run test — expect FAIL** (status will be `paid` not `overpaid`)

**Step 3: Update payment logic**

In `views.py`, `installment_pay` function (~line 1265):
```python
        if installment.paid_amount > installment.amount:
            installment.status = Installment.STATUS_OVERPAID
        elif installment.paid_amount >= installment.amount:
            installment.status = Installment.STATUS_PAID
        elif installment.paid_amount > 0:
            installment.status = Installment.STATUS_PARTIAL
        else:
            installment.status = Installment.STATUS_PENDING
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**
```bash
git add -A && git commit -m "feat: installment_pay sets 'overpaid' status when paid > amount"
```

---

## Task 4: Add Contract status properties

**Objective:** `total_paid`, `remaining_balance`, `is_complete`, `is_on_track` on Contract model.

**Files:**
- Modify: `installments/core/models.py` (Contract model, after `__str__` method)

**Step 1: Write failing test**

```python
class ContractPropertiesTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="Props Test", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=2,
            installment_amount=Decimal("500"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=self.account,
        )
        Installment.objects.bulk_create([
            Installment(contract=self.contract, installment_number=1,
                due_date=date(2025, 7, 8), amount=Decimal("500"),
                paid_amount=Decimal("300"), status=Installment.STATUS_PARTIAL, account=self.account),
            Installment(contract=self.contract, installment_number=2,
                due_date=date(2025, 8, 8), amount=Decimal("500"),
                paid_amount=Decimal("0"), status=Installment.STATUS_PENDING, account=self.account),
        ])

    def test_total_paid(self):
        self.assertEqual(self.contract.total_paid, Decimal("300"))

    def test_remaining_balance(self):
        self.assertEqual(self.contract.remaining_balance, Decimal("700"))

    def test_is_complete_false(self):
        self.assertFalse(self.contract.is_complete)

    def test_is_complete_true(self):
        self.contract.installments.all().update(paid_amount=Decimal("500"), status=Installment.STATUS_PAID)
        self.assertTrue(self.contract.is_complete)

    def test_is_on_track(self):
        # No installments are due yet (both future), so expected=0, paid=300 → on track
        self.assertTrue(self.contract.is_on_track)
```

**Step 2: Run test — expect FAIL** (no properties)

**Step 3: Add properties to Contract model**

In `models.py`, need `Sum` import at top:
```python
from django.db.models import Sum
```

After `__str__` on Contract:
```python
    @property
    def total_paid(self):
        """Sum of all installment paid_amount for this contract."""
        return self.installments.aggregate(
            s=Sum("paid_amount", default=Decimal("0.00"))
        )["s"]

    @property
    def remaining_balance(self):
        """Total amount still owed on this contract."""
        return self.total_amount - self.total_paid

    @property
    def is_complete(self):
        """True when total paid covers total amount."""
        return self.total_paid >= self.total_amount

    @property
    def is_on_track(self):
        """True if total paid >= sum of base amounts of all due installments."""
        from datetime import date
        expected = self.installments.filter(
            due_date__lte=date.today()
        ).aggregate(
            s=Sum("amount", default=Decimal("0.00"))
        )["s"]
        return self.total_paid >= expected
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**
```bash
git add -A && git commit -m "feat: add Contract properties (total_paid, remaining_balance, is_complete, is_on_track)"
```

---

## Task 5: Fix carryover display in `contract_summary`

**Objective:** Remove the clamping that loses overpayment credit in the schedule display.

**Files:**
- Modify: `installments/core/views.py` (~line 1097-1108, `contract_summary` function)

**Step 1: Write failing test**

```python
class ContractSummaryCarryoverFixTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="Carry Fix", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=3,
            installment_amount=Decimal("333.33"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=self.account,
        )
        Installment.objects.bulk_create([
            Installment(contract=self.contract, installment_number=1,
                due_date=date(2025, 7, 8), amount=Decimal("333.33"),
                paid_amount=Decimal("500"), status=Installment.STATUS_OVERPAID, account=self.account),
            Installment(contract=self.contract, installment_number=2,
                due_date=date(2025, 8, 8), amount=Decimal("333.33"),
                paid_amount=Decimal("0"), status=Installment.STATUS_PENDING, account=self.account),
            Installment(contract=self.contract, installment_number=3,
                due_date=date(2025, 9, 8), amount=Decimal("333.34"),
                paid_amount=Decimal("0"), status=Installment.STATUS_PENDING, account=self.account),
        ])

    def test_carryover_not_clamped_to_zero(self):
        """Overpayment should carry forward as negative carryover."""
        r = self.client.get(reverse("core:contract_summary", args=[self.contract.id]))
        self.assertEqual(r.status_code, 200)
        rows = r.context["schedule_rows"]
        # inst1: expected=333.33, paid=500, carried = 333.33-500 = -166.67
        # This should NOT be clamped to 0
        self.assertLess(rows[0]["carried"], Decimal("0"))
```

**Step 2: Run test — expect FAIL** (carryover is clamped to 0)

**Step 3: Remove the clamping**

In `views.py`, `contract_summary` (~line 1101-1103):
```python
        carried = expected - paid_now
        # REMOVED: if carried < 0: carried = Decimal("0.00")
```

Also fix line 1107 — show carryover for ALL statuses, not just pending:
```python
            "carried": carried,
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**
```bash
git add -A && git commit -m "fix: carryover display in contract_summary no longer clamps overpayment to zero"
```

---

## Task 6: Update receipt to show expected/difference with color coding

**Objective:** Receipt shows Expected Amount, Amount Paid, and Difference with 🔴/🟢/🔵 coloring.

**Files:**
- Modify: `installments/core/views.py` (~line 1291-1328, `installment_receipt` function)
- Modify: `installments/core/templates/core/receipt_detail.html`

**Step 1: Write failing test**

```python
class ReceiptDifferenceTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="Receipt Diff", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=2,
            installment_amount=Decimal("500"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=self.account,
        )

    def test_receipt_shows_expected_and_difference_underpayment(self):
        """Receipt context includes expected_amount and difference (negative)."""
        inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            paid_amount=Decimal("300"), status=Installment.STATUS_PARTIAL,
            account=self.account,
        )
        r = self.client.get(reverse("core:installment_receipt", args=[inst.id]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("expected_amount", r.context)
        self.assertIn("difference", r.context)
        self.assertEqual(r.context["expected_amount"], Decimal("500.00"))
        self.assertEqual(r.context["difference"], Decimal("-200.00"))

    def test_receipt_shows_difference_overpayment(self):
        """Receipt shows positive difference when overpaid."""
        inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            paid_amount=Decimal("600"), status=Installment.STATUS_OVERPAID,
            account=self.account,
        )
        r = self.client.get(reverse("core:installment_receipt", args=[inst.id]))
        self.assertEqual(r.context["difference"], Decimal("100.00"))
```

**Step 2: Run test — expect FAIL** (no `expected_amount`/`difference` in context)

**Step 3: Update `installment_receipt` view**

In `views.py`, `installment_receipt` (~line 1319 context dict):
```python
    expected_amount = installment.amount
    difference = installment.paid_amount - installment.amount

    context = {
        "installment": installment,
        "expected_amount": expected_amount,
        "difference": difference,
        "remaining_balance": remaining_balance,
        "business_name": business_name,
        "due_month": due_month,
        "is_late": is_late,
        "carryover": carryover,
        "overpaid": overpaid,
    }
```

**Step 4: Update `receipt_detail.html` template**

Add after the "المبلغ المدفوع" row (line ~107), a new row for Expected + Difference:

```html
        <tr>
          <td class="text-muted">المبلغ المتوقع:</td>
          <td><span class="fw-bold">{{ expected_amount|floatformat:2 }}</span> <span class="fs-6">جنيه</span></td>
        </tr>
        <tr>
          <td class="text-muted">الفرق:</td>
          <td>
            {% if difference < 0 %}
              <span class="fw-bold text-danger">نقص {{ difference|floatformat:2 }} جنيه</span>
            {% elif difference > 0 %}
              <span class="fw-bold text-primary">زيادة {{ difference|floatformat:2 }} جنيه</span>
            {% else %}
              <span class="fw-bold text-success">مدفوع بالكامل</span>
            {% endif %}
          </td>
        </tr>
```

**Step 5: Run test — expect PASS**

**Step 6: Commit**
```bash
git add -A && git commit -m "feat: receipt shows expected amount + difference with color coding"
```

---

## Task 7: Fix contract_summary template "المتبقي" column

**Objective:** The "المتبقي" column in the schedule table should show `amount - paid_amount`, not just `amount`.

**Files:**
- Modify: `installments/core/templates/core/contract_summary.html` (~line 68)

**Step 1: Write failing test**

```python
class SummaryRemainingColumnTests(TestCase):
    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="Col Test", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=2,
            installment_amount=Decimal("500"),
            calculation_mode="B", start_date=date(2025, 6, 8),
            payment_due_day=8, account=self.account,
        )
        self.inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            paid_amount=Decimal("300"), status=Installment.STATUS_PARTIAL,
            account=self.account,
        )
        Installment.objects.create(
            contract=self.contract, installment_number=2,
            due_date=date(2025, 8, 8), amount=Decimal("500"),
            paid_amount=Decimal("0"), status=Installment.STATUS_PENDING,
            account=self.account,
        )

    def test_remaining_column_shows_actual_remaining(self):
        """Template should show 200 (500-300) not 500 for partial installment."""
        r = self.client.get(reverse("core:contract_summary", args=[self.contract.id]))
        self.assertContains(r, "200")  # 500 - 300 = 200
```

**Step 2: Run test — may pass or fail depending on template** (currently shows `row.inst.amount` which is always 500)

**Step 3: Fix template**

In `contract_summary.html` line 68:
```html
<!-- Before: -->
<td class="money">{{ row.inst.amount|floatformat:2 }}</td>
<!-- After: -->
<td class="money">{{ row.inst.amount|floatformat:2 }}</td>
```

Wait, line 68 is "المبلغ" column, not "المتبقي". Let me re-read...

Line 60: `<th>#</th><th>الاستحقاق</th><th>المبلغ</th><th>المدفوع</th><th>المتبقي</th><th>الحالة</th>`
Line 66: `{{ row.inst.amount|floatformat:2 }}` → المبلغ ✅
Line 67: `{{ row.inst.paid_amount|floatformat:2 }}` → المدفوع ✅
Line 68: `{{ row.inst.amount|floatformat:2 }}` → المتبقي ❌ (should be amount - paid_amount)

Fix line 68:
```html
<td class="money">{{ row.remaining|default:"0.00" }}</td>
```

And in `contract_summary` view, add `remaining` to each schedule_row:
```python
        schedule_rows.append({
            "inst": inst,
            "expected": expected,
            "carried": carried,
            "remaining": max(inst.amount - inst.paid_amount, Decimal("0.00")),
        })
```

**Step 4: Run test — expect PASS**

**Step 5: Commit**
```bash
git add -A && git commit -m "fix: contract_summary 'remaining' column shows actual remaining per installment"
```

---

## Task 8: Run full test suite + final verification

**Objective:** All tests pass, no regressions.

**Step 1: Run all tests**
```bash
cd installments && python manage.py test core -v2
```

**Step 2: Run server locally**
```bash
cd installments && python manage.py runserver 0.0.0.0:8000
```

**Step 3: Manual verification checklist**
- [ ] Create new contract → verify `end_date` is set
- [ ] Pay installment with extra amount → verify `overpaid` status
- [ ] View receipt → verify Expected + Difference rows with colors
- [ ] View contract_summary → verify carryover not clamped, remaining column correct
- [ ] Check existing contracts still work (end_date backfilled)

**Step 4: Final commit**
```bash
git add -A && git commit -m "test: full suite passes with new features"
```

---

## Risks & Tradeoffs

| Risk | Mitigation |
|------|-----------|
| `end_date` null on existing contracts | Backfill script in Task 1 Step 6 |
| `overpaid` status not in `_mark_late_installments` | Not needed — overpaid is a paid state, not late |
| `is_on_track` uses `date.today()` not `_today()` | Acceptable — model has no request context |
| Carryover fix changes display behavior | Desired — old behavior was a bug |
| Receipt template changes print layout | Test print manually |

## Open Questions (for user)

1. **Should `overdue` replace `late` or coexist?** — Current plan: keep `late`, add `overpaid` only. Spec says `overdue` but renaming would require data migration.
2. **Should `end_date` be editable in the form?** — Current plan: auto-calculated, not user-editable (hidden field or display-only).
3. **Should down_payment create a separate Installment #0?** — Current plan: no, keep as-is (down_payment reduces remaining_amount).
