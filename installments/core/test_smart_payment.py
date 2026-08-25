"""اختبارات الدفع: القسط المفتوح فقط — بدون توزيع تلقائي (السلوك المتفق عليه).

- الدفعة بتتسجل على القسط اللي فتحت منه شاشة الدفع بس.
- الزيادة عن قيمة القسط بتتسجل على نفس القسط (حالة "زيادة").
- لو مجموع مدفوعات العقد وصل قيمة العقد → إقفال تلقائي (completed).
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import Account, Contract, Customer, Installment, Product


class SingleInstallmentPaymentTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name="Acc")
        self.customer = Customer.objects.create(account=self.account, name="عميل", phone="0100")
        self.product = Product.objects.create(account=self.account, name="منتج", model_name="M1")
        self.contract = Contract.objects.create(
            account=self.account,
            customer=self.customer,
            product=self.product,
            product_name="منتج",
            actual_cost=Decimal("1000"),
            customer_price=Decimal("1200"),
            remaining_amount=Decimal("1200"),
            interest_rate=Decimal("0"),
            total_interest=Decimal("0"),
            total_amount=Decimal("600"),
            months_count=3,
            installment_amount=Decimal("200"),
            payment_due_day=10,
            start_date=date(2026, 1, 1),
        )
        for n, d in [(1, date(2026, 1, 10)), (2, date(2026, 2, 10)), (3, date(2026, 3, 10))]:
            Installment.objects.create(
                account=self.account, contract=self.contract, installment_number=n,
                amount=Decimal("200"), paid_amount=Decimal("0"), due_date=d,
                status=Installment.STATUS_PENDING,
            )
        self.user = self._admin()
        self.client.force_login(self.user)

    def _admin(self):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        user = U.objects.create_user(username="payer", password="x")
        s = self.client.session
        s["account_id"] = self.account.id
        s.save()
        return user

    def _pay(self, inst_id, amount):
        return self.client.post(reverse("core:installment_pay", args=[inst_id]), {
            "paid_amount": str(amount),
            "paid_date": "2026-01-15",
            "payment_method": "cash",
            "received_by": "test",
        })

    def test_payment_stays_on_target_installment(self):
        """دفع 300 على القسط الأول → يفضل على الأول كـ"زيادة" وميوزعش على التاني."""
        first = self.contract.installments.get(installment_number=1)
        r = self._pay(first.id, 300)
        self.assertEqual(r.status_code, 302)
        i1 = self.contract.installments.get(installment_number=1)
        i2 = self.contract.installments.get(installment_number=2)
        i3 = self.contract.installments.get(installment_number=3)
        self.assertEqual(i1.paid_amount, Decimal("300"))
        self.assertEqual(i1.status, Installment.STATUS_OVERPAID)
        self.assertEqual(i2.paid_amount, Decimal("0"))  # مفيش توزيع
        self.assertEqual(i3.paid_amount, Decimal("0"))
        # العقد لسه شغال
        self.contract.refresh_from_db()
        self.assertIn(self.contract.status, [Contract.STATUS_ACTIVE, Contract.STATUS_OVERDUE])

    def test_full_contract_payment_on_first_installment_closes(self):
        """سداد إجمالي قيمة العقد من أول قسط → الإجمالي بيوصل واللوجيك الموحد يقفل."""
        first = self.contract.installments.first()
        r = self._pay(first.id, 600)
        self.assertEqual(r.status_code, 302)
        self.contract.refresh_from_db()
        total = sum(i.paid_amount for i in self.contract.installments.all())
        self.assertEqual(total, Decimal("600"))

    def test_overpay_rejected(self):
        """دفع أكبر من المتبقي على العقد → مرفوض وما يتسجلش حاجة."""
        first = self.contract.installments.first()
        before_total = sum(i.paid_amount for i in self.contract.installments.all())
        r = self._pay(first.id, 999)
        after_total = sum(i.paid_amount for i in self.contract.installments.all())
        self.assertEqual(before_total, after_total)

    def test_partial_then_completion_same_installment(self):
        """جزئي ثم مكملته بعدين على نفس القسط → يكتمل صح."""
        first = self.contract.installments.first()
        self._pay(first.id, 50)
        i1 = self.contract.installments.get(installment_number=1)
        self.assertEqual(i1.status, Installment.STATUS_PARTIAL)
        self._pay(first.id, 150)  # يكمل الـ 200 بالظبط
        i1.refresh_from_db()
        self.assertEqual(i1.paid_amount, Decimal("200"))
        self.assertEqual(i1.status, Installment.STATUS_PAID)

    def test_closed_installments_receive_no_payments(self):
        """أقساط معفاة (عقد مغلق مبكرًا) ما بتستقبلش دفعات."""
        self.contract.status = Contract.STATUS_EARLY_COMPLETED
        self.contract.save(update_fields=["status"])
        second = self.contract.installments.get(installment_number=2)
        r = self._pay(second.id, 100)
        self.assertRedirects(r, reverse("core:contract_detail", args=[self.contract.id]))
        second.refresh_from_db()
        self.assertEqual(second.paid_amount, Decimal("0"))
