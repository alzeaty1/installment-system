"""
Comprehensive tests for the Installment System.
Covers calculation modes, edge cases, overpayment, and contract lifecycle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .calculations import calculate_mode_a, calculate_mode_b, calculate_mode_c
from .models import Account, Contract, Customer, Installment
from .views import (
    _add_months,
    _remaining_installments_total,
    InstallmentPaymentForm,
)


def _auth_client(client):
    User = get_user_model()
    user = User.objects.create_superuser(username="testadmin", password="testpass123")
    account, _ = Account.objects.get_or_create(name="Test Account")
    session = client.session
    session["account_id"] = account.id
    session.save()
    client.force_login(user)
    return user, account


# ─── Mode A Calculation Tests ──────────────────────────────────────────

class CalculationModeATests(TestCase):
    """Mode A: user provides installment amount and months count."""

    def test_mode_a_basic(self):
        result = calculate_mode_a(Decimal("9000"), Decimal("3300"), 3)
        # total_payable = 3300*3 = 9900, interest = 900, rate = 10%
        self.assertEqual(result["remaining_amount"], Decimal("9000.00"))
        self.assertEqual(result["installment_amount"], Decimal("3300.00"))
        self.assertEqual(result["total_amount"], Decimal("9900.00"))
        self.assertEqual(result["total_interest"], Decimal("900.00"))
        self.assertEqual(result["interest_rate"], Decimal("10.00"))
        self.assertEqual(result["months_count"], 3)

    def test_mode_a_zero_interest(self):
        """installment * months == remaining → zero interest."""
        result = calculate_mode_a(Decimal("9000"), Decimal("3000"), 3)
        self.assertEqual(result["total_interest"], Decimal("0.00"))
        self.assertEqual(result["interest_rate"], Decimal("0.00"))

    def test_mode_a_single_month(self):
        result = calculate_mode_a(Decimal("5000"), Decimal("5000"), 1)
        self.assertEqual(result["total_interest"], Decimal("0.00"))

    def test_mode_a_installment_greater_than_remaining(self):
        result = calculate_mode_a(Decimal("5000"), Decimal("6000"), 1)
        self.assertEqual(result["total_interest"], Decimal("1000.00"))
        self.assertEqual(result["interest_rate"], Decimal("20.00"))

    def test_mode_a_rejects_zero_remaining(self):
        with self.assertRaises(ValueError):
            calculate_mode_a(Decimal("0"), Decimal("1000"), 3)

    def test_mode_a_rejects_zero_months(self):
        with self.assertRaises(ValueError):
            calculate_mode_a(Decimal("9000"), Decimal("3300"), 0)

    def test_mode_a_rejects_zero_installment(self):
        with self.assertRaises(ValueError):
            calculate_mode_a(Decimal("9000"), Decimal("0"), 3)

    def test_mode_a_fractional_installment(self):
        result = calculate_mode_a(Decimal("10000"), Decimal("3333.33"), 3)
        # total = 3333.33 * 3 = 9999.99 → quantized to 10000
        # interest = 10000 - 10000 = 0
        self.assertEqual(result["installment_amount"], Decimal("3333"))
        self.assertEqual(result["total_amount"], Decimal("10000"))
        self.assertEqual(result["total_interest"], Decimal("0"))


# ─── Mode B Calculation Tests ──────────────────────────────────────────

class CalculationModeBTests(TestCase):
    """Mode B: user provides interest rate and months count."""

    def test_mode_b_basic(self):
        result = calculate_mode_b(Decimal("9000"), Decimal("10"), 3)
        self.assertEqual(result["remaining_amount"], Decimal("9000.00"))
        self.assertEqual(result["total_interest"], Decimal("900.00"))
        self.assertEqual(result["total_amount"], Decimal("9900.00"))
        self.assertEqual(result["installment_amount"], Decimal("3300.00"))
        self.assertEqual(result["interest_rate"], Decimal("10.00"))

    def test_mode_b_zero_rate(self):
        result = calculate_mode_b(Decimal("9000"), Decimal("0"), 3)
        self.assertEqual(result["total_interest"], Decimal("0.00"))
        self.assertEqual(result["installment_amount"], Decimal("3000.00"))

    def test_mode_b_single_month_high_rate(self):
        result = calculate_mode_b(Decimal("8000"), Decimal("50"), 1)
        self.assertEqual(result["total_interest"], Decimal("4000.00"))
        self.assertEqual(result["total_amount"], Decimal("12000.00"))

    def test_mode_b_rejects_negative_rate(self):
        with self.assertRaises(ValueError):
            calculate_mode_b(Decimal("9000"), Decimal("-5"), 3)

    def test_mode_b_large_remaining(self):
        result = calculate_mode_b(Decimal("50000"), Decimal("5"), 12)
        self.assertEqual(result["total_interest"], Decimal("2500.00"))
        self.assertEqual(result["total_amount"], Decimal("52500.00"))


# ─── Mode C Calculation Tests ──────────────────────────────────────────

class CalculationModeCTests(TestCase):
    """Mode C: auto-suggests rate = default_rate * months."""

    def test_mode_c_basic(self):
        result = calculate_mode_c(Decimal("9000"), 3, Decimal("3.5"))
        self.assertEqual(result["interest_rate"], Decimal("10.50"))

    def test_mode_c_default_rate(self):
        result = calculate_mode_c(Decimal("10000"), 6)
        self.assertEqual(result["interest_rate"], Decimal("21.00"))

    def test_mode_c_single_month_custom_rate(self):
        result = calculate_mode_c(Decimal("5000"), 1, Decimal("2.0"))
        self.assertEqual(result["interest_rate"], Decimal("2.00"))

    def test_mode_c_24_months(self):
        result = calculate_mode_c(Decimal("15000"), 24, Decimal("2.0"))
        self.assertEqual(result["interest_rate"], Decimal("48.00"))


# ─── Date / _add_months Tests ──────────────────────────────────────────

class AddMonthsEdgeTests(TestCase):
    """Edge cases for _add_months helper."""

    def test_add_months_basic(self):
        d = date(2026, 7, 15)
        result = _add_months(d, 3, 1)
        self.assertEqual(result, date(2026, 10, 1))

    def test_add_months_end_of_month_31_to_feb(self):
        d = date(2026, 1, 31)
        result = _add_months(d, 1, 31)
        self.assertEqual(result, date(2026, 2, 28))

    def test_add_months_31_day_to_april(self):
        d = date(2026, 3, 15)
        result = _add_months(d, 1, 31)
        self.assertEqual(result, date(2026, 4, 30))

    def test_add_months_year_rollover(self):
        d = date(2026, 11, 5)
        result = _add_months(d, 3, 5)
        self.assertEqual(result, date(2027, 2, 5))

    def test_add_months_due_day_default_1(self):
        d = date(2026, 2, 1)
        result = _add_months(d, 2, 1)
        self.assertEqual(result, date(2026, 4, 1))


# ─── _remaining_installments_total Tests ───────────────────────────────

class RemainingInstallmentsTests(TestCase):
    """Test remaining balance calculation logic."""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.customer = Customer.objects.create(name="Test", phone="0", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="X",
            actual_cost=Decimal("0"), customer_price=Decimal("0"),
            remaining_amount=Decimal("0"), interest_rate=Decimal("0"),
            total_interest=Decimal("0"), total_amount=Decimal("0"),
            months_count=3, installment_amount=Decimal("1000.00"),
            calculation_mode="B",
            start_date=date(2026, 7, 1), payment_due_day=1,
            account=self.account,
        )

    def test_all_pending(self):
        Installment.objects.bulk_create([
            Installment(contract=self.contract, installment_number=i,
                        due_date=date(2026, 7, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("0"), status=Installment.STATUS_PENDING)
            for i in [1, 2, 3]
        ])
        total = _remaining_installments_total(Installment.objects.filter(contract=self.contract))
        self.assertEqual(total, Decimal("3000.00"))

    def test_mixed_partial_and_pending(self):
        Installment.objects.bulk_create([
            Installment(contract=self.contract, installment_number=1,
                        due_date=date(2026, 7, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("1000.00"), status=Installment.STATUS_PAID),
            Installment(contract=self.contract, installment_number=2,
                        due_date=date(2026, 8, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("400.00"), status=Installment.STATUS_PARTIAL),
            Installment(contract=self.contract, installment_number=3,
                        due_date=date(2026, 9, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("0"), status=Installment.STATUS_PENDING),
        ])
        total = _remaining_installments_total(Installment.objects.filter(contract=self.contract))
        # (1000-1000) + (1000-400) + (1000-0) = 0 + 600 + 1000 = 1600
        self.assertEqual(total, Decimal("1600.00"))

    def test_overpayment_remaining_is_correct(self):
        """Overpayment reduces total remaining (3000 owed - 1500 paid = 1500)."""
        Installment.objects.bulk_create([
            Installment(contract=self.contract, installment_number=1,
                        due_date=date(2026, 7, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("1500.00"), status=Installment.STATUS_PAID),
            Installment(contract=self.contract, installment_number=2,
                        due_date=date(2026, 8, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("0"), status=Installment.STATUS_PENDING),
            Installment(contract=self.contract, installment_number=3,
                        due_date=date(2026, 9, 1), amount=Decimal("1000.00"),
                        paid_amount=Decimal("0"), status=Installment.STATUS_PENDING),
        ])
        total = _remaining_installments_total(Installment.objects.filter(contract=self.contract))
        # Total owed = 3000, total paid = 1500, remaining = 1500
        self.assertEqual(total, Decimal("1500.00"))


# ─── Contract Number Auto-Generation Tests ─────────────────────────────

class ContractNumberGenerationTests(TestCase):
    """Auto contract_number generation via save()."""

    def test_first_gets_con_000001(self):
        account = Account.objects.create(name="Test")
        customer = Customer.objects.create(name="Cust", phone="0", account=account)
        c = Contract.objects.create(
            customer=customer, product_name="Test",
            actual_cost=Decimal("0"), customer_price=Decimal("0"),
            remaining_amount=Decimal("0"), interest_rate=Decimal("0"),
            total_interest=Decimal("0"), total_amount=Decimal("0"),
            months_count=1, installment_amount=Decimal("0"),
            calculation_mode="B", start_date=date(2026, 7, 1),
            payment_due_day=1, account=account,
        )
        self.assertEqual(c.contract_number, "CON-000001")

    def test_second_gets_con_000002(self):
        account = Account.objects.create(name="Test")
        customer = Customer.objects.create(name="Cust", phone="0", account=account)
        Contract.objects.create(customer=customer, product_name="T1",
            actual_cost=Decimal("0"), customer_price=Decimal("0"),
            remaining_amount=Decimal("0"), interest_rate=Decimal("0"),
            total_interest=Decimal("0"), total_amount=Decimal("0"),
            months_count=1, installment_amount=Decimal("0"),
            calculation_mode="B", start_date=date(2026, 7, 1),
            payment_due_day=1, account=account)
        c2 = Contract.objects.create(customer=customer, product_name="T2",
            actual_cost=Decimal("0"), customer_price=Decimal("0"),
            remaining_amount=Decimal("0"), interest_rate=Decimal("0"),
            total_interest=Decimal("0"), total_amount=Decimal("0"),
            months_count=1, installment_amount=Decimal("0"),
            calculation_mode="B", start_date=date(2026, 7, 1),
            payment_due_day=1, account=account)
        self.assertEqual(c2.contract_number, "CON-000002")


# ─── Payment Lifecycle Tests ───────────────────────────────────────────

class PaymentLifecycleTests(TestCase):
    """End-to-end payment flow: pay, overpay, partial, 2-partials, completion."""

    def setUp(self):
        self.user, self.account = _auth_client(self.client)
        self.customer = Customer.objects.create(name="Pay Customer", phone="010", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="Phone",
            actual_cost=Decimal("8000.00"), customer_price=Decimal("10000.00"),
            down_payment=Decimal("1000.00"), remaining_amount=Decimal("9000.00"),
            interest_rate=Decimal("10.00"), total_interest=Decimal("900.00"),
            total_amount=Decimal("9900.00"), months_count=3,
            installment_amount=Decimal("3300.00"),
            calculation_mode=Contract.MODE_B,
            start_date=date(2026, 7, 1), payment_due_day=1,
            account=self.account,
        )
        self.inst1 = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2026, 7, 1), amount=Decimal("3300.00"),
            paid_amount=Decimal("0"), status=Installment.STATUS_PENDING,
            account=self.account,
        )

    def test_pay_exact(self):
        r = self.client.post(reverse("core:installment_pay", args=[self.inst1.id]), data={
            "paid_amount": "3300.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "Cashier", "notes": ""})
        self.assertEqual(r.status_code, 302)
        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.status, Installment.STATUS_PAID)

    def test_pay_over(self):
        r = self.client.post(reverse("core:installment_pay", args=[self.inst1.id]), data={
            "paid_amount": "4000.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "Cashier", "notes": ""})
        self.assertEqual(r.status_code, 302)
        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.paid_amount, Decimal("4000.00"))

    def test_pay_partial(self):
        r = self.client.post(reverse("core:installment_pay", args=[self.inst1.id]), data={
            "paid_amount": "1000.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "Cashier", "notes": ""})
        self.assertEqual(r.status_code, 302)
        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.status, Installment.STATUS_PARTIAL)

    def test_two_partials_sum_to_full(self):
        self.client.post(reverse("core:installment_pay", args=[self.inst1.id]), data={
            "paid_amount": "1000.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "Cashier", "notes": ""})
        self.client.post(reverse("core:installment_pay", args=[self.inst1.id]), data={
            "paid_amount": "2300.00", "paid_date": "2026-07-10",
            "payment_method": "cash", "received_by": "Cashier", "notes": ""})
        self.inst1.refresh_from_db()
        self.assertEqual(self.inst1.paid_amount, Decimal("3300.00"))
        self.assertEqual(self.inst1.status, Installment.STATUS_PAID)

    def test_all_paid_completes_contract(self):
        inst2 = Installment.objects.create(contract=self.contract, installment_number=2,
            due_date=date(2026, 8, 1), amount=Decimal("3300.00"),
            paid_amount=Decimal("0"), account=self.account)
        inst3 = Installment.objects.create(contract=self.contract, installment_number=3,
            due_date=date(2026, 9, 1), amount=Decimal("3300.00"),
            paid_amount=Decimal("0"), account=self.account)
        self.client.post(reverse("core:installment_pay", args=[self.inst1.id]), data={
            "paid_amount": "3300.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "C", "notes": ""})
        self.client.post(reverse("core:installment_pay", args=[inst2.id]), data={
            "paid_amount": "3300.00", "paid_date": "2026-08-03",
            "payment_method": "cash", "received_by": "C", "notes": ""})
        self.client.post(reverse("core:installment_pay", args=[inst3.id]), data={
            "paid_amount": "3300.00", "paid_date": "2026-09-03",
            "payment_method": "cash", "received_by": "C", "notes": ""})
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.STATUS_COMPLETED)


# ─── Payment Form Validation Tests ─────────────────────────────────────

class PaymentFormValidationTests(TestCase):
    """Form-level transfer/validation rules."""

    def setUp(self):
        self.account = Account.objects.create(name="Test")
        self.customer = Customer.objects.create(name="Test", phone="0", account=self.account)

    def test_wallet_requires_sender_fields(self):
        form = InstallmentPaymentForm(data={
            "paid_amount": "1000.00", "paid_date": "2026-07-03",
            "payment_method": "wallet",
            "transfer_sender_account": "", "transfer_sender_name": "", "notes": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("transfer_sender_account", form.errors)
        self.assertIn("transfer_sender_name", form.errors)

    def test_instapay_requires_sender_fields(self):
        form = InstallmentPaymentForm(data={
            "paid_amount": "1000.00", "paid_date": "2026-07-03",
            "payment_method": "instapay",
            "transfer_sender_account": "", "transfer_sender_name": "", "notes": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("transfer_sender_account", form.errors)

    def test_cash_requires_received_by(self):
        form = InstallmentPaymentForm(data={
            "paid_amount": "1000.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "", "notes": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        self.assertIn("يجب اختيار المستلم أو إدخال اسمه.", form.errors["__all__"][0])

    def test_cash_valid_with_received_by(self):
        form = InstallmentPaymentForm(data={
            "paid_amount": "1000.00", "paid_date": "2026-07-03",
            "payment_method": "cash", "received_by": "Ahmed", "notes": "",
        })
        self.assertTrue(form.is_valid())


# ─── Customer Detail Edge Tests ────────────────────────────────────────

class CustomerDetailEdgeTests(TestCase):
    def setUp(self):
        self.user, self.account = _auth_client(self.client)

    def test_customer_no_contracts(self):
        customer = Customer.objects.create(name="NoContract", phone="0", account=self.account)
        r = self.client.get(reverse("core:customer_detail", args=[customer.id]))
        self.assertEqual(r.status_code, 200)

    def test_customer_commitment_full(self):
        customer = Customer.objects.create(name="FullPay", phone="0", account=self.account)
        contract = Contract.objects.create(
            customer=customer, product_name="X",
            actual_cost=Decimal("0"), customer_price=Decimal("0"),
            remaining_amount=Decimal("0"), interest_rate=Decimal("0"),
            total_interest=Decimal("0"), total_amount=Decimal("0"),
            months_count=1, installment_amount=Decimal("1000.00"),
            calculation_mode="B", start_date=date(2026, 7, 1),
            payment_due_day=1, account=self.account,
        )
        Installment.objects.create(contract=contract, installment_number=1,
            due_date=date(2026, 7, 1), amount=Decimal("1000.00"),
            paid_amount=Decimal("1000.00"), status=Installment.STATUS_PAID,
            account=self.account)
        r = self.client.get(reverse("core:customer_detail", args=[customer.id]))
        self.assertEqual(r.status_code, 200)


# ─── Reset Payment Tests ───────────────────────────────────────────────

class ResetPaymentTests(TestCase):
    """Tests for installment_payment_reset."""

    def setUp(self):
        self.user, self.account = _auth_client(self.client)
        self.customer = Customer.objects.create(name="Reset Cust", phone="0", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer, product_name="X",
            actual_cost=Decimal("0"), customer_price=Decimal("0"),
            remaining_amount=Decimal("0"), interest_rate=Decimal("0"),
            total_interest=Decimal("0"), total_amount=Decimal("0"),
            months_count=2, installment_amount=Decimal("500.00"),
            calculation_mode="B", start_date=date(2026, 7, 1),
            payment_due_day=1, account=self.account,
        )

    def test_reset_reverts_to_pending(self):
        inst = Installment.objects.create(contract=self.contract, installment_number=1,
            due_date=date(2026, 9, 1), amount=Decimal("500.00"),
            paid_amount=Decimal("500.00"), paid_date=date(2026, 7, 3),
            status=Installment.STATUS_PAID, account=self.account)
        r = self.client.post(reverse("core:installment_reset_payment", args=[inst.id]))
        self.assertEqual(r.status_code, 302)
        inst.refresh_from_db()
        self.assertEqual(inst.paid_amount, Decimal("0.00"))
        self.assertEqual(inst.status, Installment.STATUS_PENDING)

    def test_reset_past_due_goes_late(self):
        inst = Installment.objects.create(contract=self.contract, installment_number=1,
            due_date=date(2026, 1, 1), amount=Decimal("500.00"),
            paid_amount=Decimal("500.00"), paid_date=date(2026, 1, 3),
            status=Installment.STATUS_PAID, account=self.account)
        r = self.client.post(reverse("core:installment_reset_payment", args=[inst.id]))
        self.assertEqual(r.status_code, 302)
        inst.refresh_from_db()
        self.assertEqual(inst.status, Installment.STATUS_LATE)


# ─── Contract Create Edge Tests ────────────────────────────────────────

class ContractCreateEdgeTests(TestCase):
    """Additional contract creation edge cases."""

    def setUp(self):
        self.user, self.account = _auth_client(self.client)

    def test_mode_a_exact_create(self):
        r = self.client.post(reverse("core:contract_create"), data={
            "customer_name": "ModeA Customer",
            "supplier_name": "",
            "product_name": "ModeA Product",
            "actual_cost": "5000.00", "customer_price": "5000.00",
            "down_payment": "0.00", "calculation_mode": "A",
            "interest_rate": "", "months_count": "1",
            "installment_amount": "5000.00", "start_date": "2026-07-01",
            "payment_due_day": "1", "status": "active", "notes": "",
        })
        self.assertEqual(r.status_code, 302)
        contract = Contract.objects.get()
        self.assertEqual(contract.total_interest, Decimal("0.00"))

    def test_mode_c_create_with_settings_rate(self):
        r = self.client.post(reverse("core:contract_create"), data={
            "customer_name": "ModeC Customer",
            "supplier_name": "",
            "product_name": "ModeC Product",
            "actual_cost": "5000.00", "customer_price": "10000.00",
            "down_payment": "0.00", "calculation_mode": "C",
            "interest_rate": "", "months_count": "3",
            "installment_amount": "", "start_date": "2026-07-01",
            "payment_due_day": "1", "status": "active", "notes": "",
        })
        self.assertEqual(r.status_code, 302)


# ─── Calculation Rounding / Quantize Tests ─────────────────────────────

class CalculationRoundingTests(TestCase):
    """Tests for decimal rounding precision."""

    def test_rounding_whole_numbers(self):
        """Money amounts should always be whole numbers (no decimals)."""
        result = calculate_mode_b(Decimal("9999.99"), Decimal("5"), 3)
        self.assertEqual(result["remaining_amount"].as_tuple().exponent, 0)
        self.assertEqual(result["total_amount"].as_tuple().exponent, 0)
        self.assertEqual(result["installment_amount"].as_tuple().exponent, 0)

    def test_rate_two_decimal_places(self):
        result = calculate_mode_a(Decimal("5000"), Decimal("5500"), 1)
        self.assertEqual(result["interest_rate"].as_tuple().exponent, -2)

    def test_mode_b_half_up_rounding(self):
        """Verify rounding is ROUND_HALF_UP (rounds to whole number)."""
        # 10000 * 3.33% = 333, total = 10333, installment = 3444.333... → 3444
        result = calculate_mode_b(Decimal("10000"), Decimal("3.33"), 3)
        self.assertEqual(result["installment_amount"].as_tuple().exponent, 0)
        self.assertEqual(result["installment_amount"], Decimal("3444"))


# ─── Fixed-Term Contract Date Tracking Tests ──────────────────────────

class ContractEndDateTests(TestCase):
    """Tests for end_date field auto-calculation."""

    def setUp(self):
        _auth_client(self.client)
        self.account = Account.objects.first()
        self.customer = Customer.objects.create(name="End Date Test", phone="010", account=self.account)

    def _make_contract(self, months=10, start=date(2025, 6, 8), due_day=8):
        return Contract.objects.create(
            customer=self.customer, product_name="Test",
            actual_cost=Decimal("1000"), customer_price=Decimal("1000"),
            down_payment=Decimal("0"), remaining_amount=Decimal("1000"),
            interest_rate=Decimal("0"), total_interest=Decimal("0"),
            total_amount=Decimal("1000"), months_count=months,
            installment_amount=Decimal("100"),
            calculation_mode="B", start_date=start,
            payment_due_day=due_day, account=self.account,
        )

    def test_end_date_is_calculated_on_save(self):
        """end_date = start_date + months_count."""
        c = self._make_contract(months=10, start=date(2025, 6, 8))
        self.assertEqual(c.end_date, date(2026, 4, 8))

    def test_end_date_not_overwritten_on_resave(self):
        """end_date set once, not changed on subsequent saves."""
        c = self._make_contract(months=3)
        original_end = c.end_date
        c.save()
        self.assertEqual(c.end_date, original_end)

    def test_end_date_with_day_clamping(self):
        """Start on Jan 31 + 1 month → Feb 28 (clamped)."""
        c = self._make_contract(months=1, start=date(2025, 1, 31), due_day=31)
        self.assertEqual(c.end_date, date(2025, 2, 28))


# ─── Overpaid Status Tests ─────────────────────────────────────────────

class OverpaidStatusTests(TestCase):
    """Tests for the 'overpaid' installment status."""

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
        self.inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            account=self.account,
        )

    def test_status_choices_include_overpaid(self):
        choices = dict(Installment.STATUS_CHOICES)
        self.assertIn("overpaid", choices)

    def test_pay_more_than_amount_sets_overpaid(self):
        """Paying 600 on a 500 installment → status=overpaid."""
        r = self.client.post(reverse("core:installment_pay", args=[self.inst.id]), {
            "paid_amount": "600.00",
            "paid_date": "2025-07-10",
            "payment_method": "cash",
            "received_by": "Test User",
        })
        self.assertEqual(r.status_code, 302)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.paid_amount, Decimal("600.00"))
        self.assertEqual(self.inst.status, Installment.STATUS_OVERPAID)

    def test_pay_exact_sets_paid_not_overpaid(self):
        """Paying exactly 500 → status=paid."""
        r = self.client.post(reverse("core:installment_pay", args=[self.inst.id]), {
            "paid_amount": "500.00",
            "paid_date": "2025-07-10",
            "payment_method": "cash",
            "received_by": "Test User",
        })
        self.assertEqual(r.status_code, 302)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.status, Installment.STATUS_PAID)


# ─── Contract Properties Tests ──────────────────────────────────────────

class ContractPropertiesTests(TestCase):
    """Tests for total_paid, remaining_balance, is_complete, is_on_track."""

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
        self.contract.installments.all().update(
            paid_amount=Decimal("500"), status=Installment.STATUS_PAID
        )
        self.assertTrue(self.contract.is_complete)


# ─── Carryover Fix + Summary Remaining Column Tests ────────────────────

class CarryoverAndSummaryTests(TestCase):
    """Tests for carryover display fix and remaining column."""

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
        self.assertLess(rows[0]["carried"], Decimal("0"))

    def test_remaining_column_shows_actual_remaining(self):
        """Template context 'remaining' = amount - paid_amount."""
        r = self.client.get(reverse("core:contract_summary", args=[self.contract.id]))
        rows = r.context["schedule_rows"]
        # inst1: 333.33 - 500 = negative → max(0) = 0
        self.assertEqual(rows[0]["remaining"], Decimal("0.00"))
        # inst2: 333.33 - 0 = 333.33
        self.assertEqual(rows[1]["remaining"], Decimal("333.33"))


# ─── Receipt Expected/Difference Tests ──────────────────────────────────

class ReceiptDifferenceTests(TestCase):
    """Tests for expected_amount and difference in receipt context."""

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

    def test_receipt_underpayment_difference(self):
        """Receipt shows negative difference on underpayment."""
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
        self.assertEqual(r.context["expected_amount"], Decimal("500"))
        self.assertEqual(r.context["difference"], Decimal("-200"))

    def test_receipt_overpayment_difference(self):
        """Receipt shows positive difference on overpayment."""
        inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            paid_amount=Decimal("600"), status=Installment.STATUS_OVERPAID,
            account=self.account,
        )
        r = self.client.get(reverse("core:installment_receipt", args=[inst.id]))
        self.assertEqual(r.context["difference"], Decimal("100"))

    def test_receipt_exact_difference_zero(self):
        """Receipt shows zero difference on exact payment."""
        inst = Installment.objects.create(
            contract=self.contract, installment_number=1,
            due_date=date(2025, 7, 8), amount=Decimal("500"),
            paid_amount=Decimal("500"), status=Installment.STATUS_PAID,
            account=self.account,
        )
        r = self.client.get(reverse("core:installment_receipt", args=[inst.id]))
        self.assertEqual(r.context["difference"], Decimal("0"))