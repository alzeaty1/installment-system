"""Tests for early contract completion (closing contracts with waived installments)."""
from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import Account, Contract, Customer, Installment, Product


class EarlyCompletionTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.customer = Customer.objects.create(account=self.account, name="عميل تجربة", phone="01000000000")
        self.product = Product.objects.create(account=self.account, name="منتج", model_name="M1")
        self.contract = Contract.objects.create(
            account=self.account,
            customer=self.customer,
            product=self.product,
            product_name="منتج",
            actual_cost=Decimal("1000"),
            customer_price=Decimal("1200"),
            down_payment=Decimal("0"),
            remaining_amount=Decimal("1200"),
            interest_rate=Decimal("0"),
            total_interest=Decimal("0"),
            total_amount=Decimal("200"),
            months_count=2,
            installment_amount=Decimal("100"),
            payment_due_day=10,
            start_date=date(2026, 1, 1),
        )
        Installment.objects.create(
            account=self.account, contract=self.contract, installment_number=1,
            amount=Decimal("100"), paid_amount=Decimal("100"), due_date=date(2026, 1, 10),
            paid_date=date(2026, 1, 10), status=Installment.STATUS_PAID,
        )
        self.inst2 = Installment.objects.create(
            account=self.account, contract=self.contract, installment_number=2,
            amount=Decimal("100"), paid_amount=Decimal("0"), due_date=date(2026, 2, 10),
            status=Installment.STATUS_PENDING,
        )

    def _mark_completed(self):
        return self.client.post(reverse("core:contract_mark_completed", args=[self.contract.id]))

    def test_mark_completed_with_unpaid_closes_early(self):
        self.client.force_login(self._admin())
        r = self._mark_completed()
        self.contract.refresh_from_db()
        self.inst2.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.STATUS_EARLY_COMPLETED)
        self.assertEqual(self.inst2.status, Installment.STATUS_CLOSED)
        # no fake payment recorded
        self.assertEqual(self.inst2.paid_amount, Decimal("0"))
        self.assertIsNone(self.inst2.paid_date)
        # total paid stays at what was actually collected
        self.assertEqual(self.contract.total_paid, Decimal("100"))

    def test_pay_blocked_on_early_completed(self):
        self._close()
        self.client.force_login(self._admin())
        r = self.client.get(reverse("core:installment_pay", args=[self.inst2.id]))
        self.assertRedirects(r, reverse("core:contract_detail", args=[self.contract.id]))
        r = self.client.post(reverse("core:installment_pay", args=[self.inst2.id]), {"paid_amount": "50"})
        self.inst2.refresh_from_db()
        self.assertEqual(self.inst2.paid_amount, Decimal("0"))

    def test_edit_blocked_on_early_completed(self):
        self._close()
        self.client.force_login(self._admin())
        r = self.client.post(reverse("core:installment_edit", args=[self.inst2.id]),
                             {"amount": "999", "due_date": "2026-02-10", "notes": ""})
        self.assertRedirects(r, reverse("core:contract_detail", args=[self.contract.id]))
        self.inst2.refresh_from_db()
        self.assertEqual(self.inst2.amount, Decimal("100"))

    def test_closed_not_marked_late(self):
        self._close()
        from .views import _mark_late_installments
        _mark_late_installments()
        self.inst2.refresh_from_db()
        self.assertEqual(self.inst2.status, Installment.STATUS_CLOSED)

    def test_full_payment_still_completes_normally(self):
        self.client.force_login(self._admin())
        # pay the second installment fully → normal completed path
        self.inst2.paid_amount = Decimal("100")
        self.inst2.paid_date = date(2026, 2, 10)
        self.inst2.status = Installment.STATUS_PAID
        self.inst2.save()
        self._mark_completed()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.STATUS_COMPLETED)

    # helpers -------------------------------------------------------------
    def _admin(self):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        user = U.objects.create_user(username="closer", password="x")
        session = self.client.session
        session["account_id"] = self.account.id
        session.save()
        return user

    def _close(self):
        self.contract.status = Contract.STATUS_EARLY_COMPLETED
        self.contract.save(update_fields=["status"])
        self.inst2.status = Installment.STATUS_CLOSED
        self.inst2.save(update_fields=["status"])
