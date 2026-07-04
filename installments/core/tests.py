from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Contract, Customer, Installment, Product
from .views import InstallmentPaymentForm, _remaining_installments_total


class InstallmentAccountingTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Customer", phone="01000000000")
        self.contract = Contract.objects.create(
            customer=self.customer,
            product_name="Phone",
            actual_cost=Decimal("8000.00"),
            customer_price=Decimal("10000.00"),
            down_payment=Decimal("1000.00"),
            remaining_amount=Decimal("9000.00"),
            interest_rate=Decimal("10.00"),
            total_interest=Decimal("900.00"),
            total_amount=Decimal("9900.00"),
            months_count=3,
            installment_amount=Decimal("3300.00"),
            calculation_mode=Contract.MODE_B,
            start_date=date(2026, 7, 1),
            payment_due_day=1,
        )

    def test_remaining_total_subtracts_partial_payments(self):
        Installment.objects.create(
            contract=self.contract,
            installment_number=1,
            due_date=date(2026, 7, 1),
            amount=Decimal("1000.00"),
            paid_amount=Decimal("400.00"),
            status=Installment.STATUS_PARTIAL,
        )
        Installment.objects.create(
            contract=self.contract,
            installment_number=2,
            due_date=date(2026, 8, 1),
            amount=Decimal("1000.00"),
            paid_amount=Decimal("1000.00"),
            status=Installment.STATUS_PAID,
        )
        Installment.objects.create(
            contract=self.contract,
            installment_number=3,
            due_date=date(2026, 9, 1),
            amount=Decimal("1000.00"),
            paid_amount=Decimal("0.00"),
            status=Installment.STATUS_PENDING,
        )

        total = _remaining_installments_total(Installment.objects.filter(contract=self.contract))

        self.assertEqual(total, Decimal("1600"))

    def test_payment_form_rejects_more_than_remaining_amount(self):
        installment = Installment.objects.create(
            contract=self.contract,
            installment_number=1,
            due_date=date(2026, 7, 1),
            amount=Decimal("1000.00"),
            paid_amount=Decimal("400.00"),
            status=Installment.STATUS_PARTIAL,
        )

        form = InstallmentPaymentForm(
            data={
                "paid_amount": "700.00",
                "paid_date": "2026-07-03",
                "payment_method": Installment.PAYMENT_CASH,
                "notes": "",
            },
            instance=installment,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("paid_amount", form.errors)

    def test_payment_form_rejects_zero_amount(self):
        installment = Installment.objects.create(
            contract=self.contract,
            installment_number=1,
            due_date=date(2026, 7, 1),
            amount=Decimal("1000.00"),
            paid_amount=Decimal("0.00"),
        )

        form = InstallmentPaymentForm(
            data={
                "paid_amount": "0.00",
                "paid_date": "2026-07-03",
                "payment_method": Installment.PAYMENT_CASH,
                "notes": "",
            },
            instance=installment,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("paid_amount", form.errors)

class ContractEditTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Customer", phone="01000000001")
        self.contract = Contract.objects.create(
            customer=self.customer,
            product_name="Laptop",
            actual_cost=Decimal("8000.00"),
            customer_price=Decimal("10000.00"),
            down_payment=Decimal("1000.00"),
            remaining_amount=Decimal("9000.00"),
            interest_rate=Decimal("10.00"),
            total_interest=Decimal("900.00"),
            total_amount=Decimal("9900.00"),
            months_count=3,
            installment_amount=Decimal("3300.00"),
            calculation_mode=Contract.MODE_B,
            start_date=date(2026, 7, 1),
            payment_due_day=1,
        )
        for index in range(3):
            Installment.objects.create(
                contract=self.contract,
                installment_number=index + 1,
                due_date=date(2026, 7 + index, 1),
                amount=Decimal("3300.00"),
            )

    def _post_data(self, months_count="4"):
        return {
            "customer": str(self.customer.id),
            "product": "",
            "product_name": "Laptop",
            "actual_cost": "8000.00",
            "customer_price": "10000.00",
            "down_payment": "1000.00",
            "calculation_mode": Contract.MODE_B,
            "interest_rate": "10.00",
            "months_count": months_count,
            "installment_amount": "3300.00",
            "start_date": "2026-07-01",
            "payment_due_day": "1",
            "status": Contract.STATUS_ACTIVE,
            "notes": "",
        }

    def test_edit_regenerates_installments_when_schedule_changes_without_payments(self):
        response = self.client.post(
            reverse("core:contract_edit", args=[self.contract.id]),
            data=self._post_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.contract.refresh_from_db()
        installments = list(self.contract.installments.order_by("installment_number"))
        self.assertEqual(len(installments), 4)
        self.assertEqual(self.contract.months_count, 4)
        self.assertEqual(installments[0].amount, Decimal("2475.00"))

    def test_edit_blocks_schedule_changes_when_payments_exist(self):
        installment = self.contract.installments.first()
        installment.paid_amount = Decimal("100.00")
        installment.status = Installment.STATUS_PARTIAL
        installment.save()

        response = self.client.post(
            reverse("core:contract_edit", args=[self.contract.id]),
            data=self._post_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.months_count, 3)
        self.assertEqual(self.contract.installments.count(), 3)

class ContractCreateInlineEntityTests(TestCase):
    def _post_data(self):
        return {
            "customer": "",
            "new_customer_name": "Inline Customer",
            "new_customer_phone": "01000000002",
            "product": "",
            "new_product_name": "Inline Product",
            "new_product_brand": "Brand X",
            "new_product_estimated_price": "8500.00",
            "product_name": "",
            "actual_cost": "8000.00",
            "customer_price": "10000.00",
            "down_payment": "1000.00",
            "calculation_mode": Contract.MODE_B,
            "interest_rate": "10.00",
            "months_count": "3",
            "installment_amount": "3300.00",
            "start_date": "2026-07-01",
            "payment_due_day": "1",
            "status": Contract.STATUS_ACTIVE,
            "notes": "",
        }

    def test_contract_create_can_create_customer_and_product_inline(self):
        response = self.client.post(reverse("core:contract_create"), data=self._post_data())

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(phone="01000000002")
        product = Product.objects.get(name="Inline Product")
        contract = Contract.objects.get(customer=customer)
        self.assertEqual(contract.product, product)
        self.assertEqual(contract.product_name, "Inline Product")
        self.assertEqual(product.brand, "Brand X")
        self.assertEqual(product.estimated_price, Decimal("8500.00"))
        self.assertEqual(contract.installments.count(), 3)



    def test_contract_create_reuses_existing_customer_name_without_phone(self):
        Customer.objects.create(name="Inline Customer", phone="01009999999")
        data = self._post_data()
        data["new_customer_phone"] = ""

        response = self.client.post(reverse("core:contract_create"), data=data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.filter(name="Inline Customer").count(), 1)
        contract = Contract.objects.get(customer__name="Inline Customer")
        self.assertEqual(contract.customer.phone, "01009999999")
    def test_contract_create_reuses_existing_inline_product(self):
        Product.objects.create(
            name="Inline Product",
            brand="Brand X",
            estimated_price=Decimal("8500.00"),
        )

        response = self.client.post(reverse("core:contract_create"), data=self._post_data())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.filter(name="Inline Product", brand="Brand X").count(), 1)
        contract = Contract.objects.get(product__name="Inline Product")
        self.assertEqual(contract.product.brand, "Brand X")
    def test_contract_create_requires_customer_choice_or_new_customer(self):
        data = self._post_data()
        data["new_customer_name"] = ""
        data["new_customer_phone"] = ""

        response = self.client.post(reverse("core:contract_create"), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Customer.objects.filter(phone="01000000002").count(), 0)
        self.assertEqual(Contract.objects.count(), 0)
