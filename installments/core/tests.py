from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Account, ActivityLog, Contract, Customer, Installment, Product, Supplier, SupplierPurchase
from .views import (
    ContractForm,
    CustomerForm,
    ExpenseForm,
    InstallmentPaymentForm,
    _remaining_installments_total,
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



class InstallmentAccountingTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.customer = Customer.objects.create(name="Test Customer", phone="01000000000", account=self.account)
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
            account=self.account,
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

    def test_payment_form_rejects_amount_over_site_limit(self):
        installment = Installment.objects.create(
            contract=self.contract,
            installment_number=1,
            due_date=date(2026, 7, 1),
            amount=Decimal("100000.00"),
            paid_amount=Decimal("0.00"),
        )

        form = InstallmentPaymentForm(
            data={
                "paid_amount": "100000.01",
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
        self.user, self.account = _auth_client(self.client)
        self.customer = Customer.objects.create(name="Test Customer", phone="01000000001", account=self.account)
        self.product = Product.objects.create(name="Laptop", brand="Dell", account=self.account)
        self.contract = Contract.objects.create(
            customer=self.customer,
            product=self.product,
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
            account=self.account,
        )
        for index in range(3):
            Installment.objects.create(
                contract=self.contract,
                installment_number=index + 1,
                due_date=date(2026, 7 + index, 1),
                amount=Decimal("3300.00"),
                account=self.account,
            )

    def _post_data(self, months_count="4"):
        return {
            "customer_name": "Test Customer",
            "supplier_name": "",
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
    """Tests for contract creation via single text field — lookup-or-create with supplier."""

    def setUp(self):
        self.user, self.account = _auth_client(self.client)

    def _base_post_data(self):
        return {
            "customer_name": "Inline Customer",
            "supplier_name": "Inline Supplier",
            "product_name": "Inline Product",
            "new_product_image": "",
            "purchase_date": "2026-07-01",
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

    def test_contract_create_creates_new_customer_supplier_and_product(self):
        response = self.client.post(reverse("core:contract_create"), data=self._base_post_data())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(name="Inline Customer").exists())
        self.assertTrue(Supplier.objects.filter(name="Inline Supplier").exists())
        self.assertTrue(Product.objects.filter(name="Inline Product").exists())
        contract = Contract.objects.get()
        self.assertEqual(contract.installments.count(), 3)
        purchase = SupplierPurchase.objects.get()
        self.assertEqual(purchase.product, contract.product)
        self.assertEqual(purchase.customer, contract.customer)
        self.assertEqual(purchase.supplier, contract.supplier)
        self.assertEqual(purchase.contract, contract)
        self.assertEqual(purchase.purchase_price, Decimal("8000.00"))
        self.assertEqual(purchase.purchase_date, date(2026, 7, 1))

    def test_contract_create_reuses_existing_customer_and_supplier_by_name(self):
        Customer.objects.create(name="Inline Customer", phone="01009999999", account=self.account)
        Supplier.objects.create(name="Inline Supplier", phone="01008888888", account=self.account)
        response = self.client.post(reverse("core:contract_create"), data=self._base_post_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.filter(name="Inline Customer").count(), 1)
        self.assertEqual(Supplier.objects.filter(name="Inline Supplier").count(), 1)

    def test_contract_create_reuses_existing_product_by_name(self):
        Product.objects.create(name="Inline Product", brand="Brand X", account=self.account)
        response = self.client.post(reverse("core:contract_create"), data=self._base_post_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.filter(name="Inline Product").count(), 1)

    def test_contract_create_adds_purchase_record_each_time_product_is_bought(self):
        Product.objects.create(name="Inline Product", brand="Brand X", account=self.account)
        first = self._base_post_data()
        second = self._base_post_data()
        second["customer_name"] = "Second Customer"
        second["actual_cost"] = "8500.00"
        second["purchase_date"] = "2026-08-05"

        self.assertEqual(self.client.post(reverse("core:contract_create"), data=first).status_code, 302)
        self.assertEqual(self.client.post(reverse("core:contract_create"), data=second).status_code, 302)

        product = Product.objects.get(name="Inline Product")
        purchases = list(SupplierPurchase.objects.filter(product=product).order_by("purchase_date"))
        self.assertEqual(Product.objects.filter(name="Inline Product").count(), 1)
        self.assertEqual(len(purchases), 2)
        self.assertEqual(purchases[0].purchase_price, Decimal("8000.00"))
        self.assertEqual(purchases[1].purchase_price, Decimal("8500.00"))
        self.assertEqual(purchases[1].customer.name, "Second Customer")
        self.assertEqual(purchases[1].purchase_date, date(2026, 8, 5))

    def test_contract_create_rejects_empty_customer_and_product(self):
        data = self._base_post_data()
        data["customer_name"] = ""
        data["product_name"] = ""
        response = self.client.post(reverse("core:contract_create"), data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contract.objects.count(), 0)

    def test_contract_create_rejects_calculated_amount_above_global_limit(self):
        data = self._base_post_data()
        data["customer_price"] = "100000.00"
        data["down_payment"] = "0.00"
        data["interest_rate"] = "10.00"

        response = self.client.post(reverse("core:contract_create"), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contract.objects.count(), 0)


class FormLimitTests(TestCase):
    def test_contract_form_limits_payment_due_day_to_days_of_month(self):
        form = ContractForm(
            data={
                "customer_name": "Limit Customer",
                "supplier_name": "",
                "product_name": "Limit Product",
                "actual_cost": "1000.00",
                "customer_price": "2000.00",
                "down_payment": "0.00",
                "calculation_mode": Contract.MODE_B,
                "interest_rate": "10.00",
                "months_count": "3",
                "installment_amount": "700.00",
                "start_date": "2026-07-01",
                "payment_due_day": "32",
                "status": Contract.STATUS_ACTIVE,
                "notes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("payment_due_day", form.errors)

    def test_contract_form_rejects_money_above_global_limit(self):
        form = ContractForm(
            data={
                "customer_name": "Limit Customer",
                "supplier_name": "",
                "product_name": "Limit Product",
                "actual_cost": "100000.01",
                "customer_price": "2000.00",
                "down_payment": "0.00",
                "calculation_mode": Contract.MODE_B,
                "interest_rate": "10.00",
                "months_count": "3",
                "installment_amount": "700.00",
                "start_date": "2026-07-01",
                "payment_due_day": "31",
                "status": Contract.STATUS_ACTIVE,
                "notes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("actual_cost", form.errors)

    def test_expense_form_rejects_money_above_global_limit(self):
        form = ExpenseForm(
            data={
                "title": "Large expense",
                "amount": "100000.01",
                "expense_date": "2026-07-01",
                "category": "",
                "notes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_text_like_fields_expose_max_lengths_in_html(self):
        form = CustomerForm()

        self.assertEqual(form.fields["name"].widget.attrs["maxlength"], "255")
        self.assertEqual(form.fields["phone"].widget.attrs["maxlength"], "50")
        self.assertEqual(form.fields["national_id"].widget.attrs["maxlength"], "50")


class ActivityLogTests(TestCase):
    def setUp(self):
        self.user, self.account = _auth_client(self.client)
        self.customer = Customer.objects.create(name="Audit Customer", phone="0123456789", account=self.account)

    def test_customer_creation_logs_activity(self):
        response = self.client.post(
            reverse("core:customer_create"),
            data={
                "name": "New Audit Customer",
                "phone": "0987654321",
                "national_id": "",
                "address": "",
                "whatsapp": "",
            }
        )
        self.assertEqual(response.status_code, 302)
        log = ActivityLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, ActivityLog.ACTION_CREATE)
        self.assertEqual(log.model_name, "Customer")
        self.assertIn("New Audit Customer", log.description)
        self.assertEqual(log.user, "testadmin")

    def test_payment_logs_activity(self):
        contract = Contract.objects.create(
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
            account=self.account,
        )
        installment = Installment.objects.create(
            contract=contract,
            installment_number=1,
            due_date=date(2026, 7, 1),
            amount=Decimal("3300.00"),
            paid_amount=Decimal("0.00"),
            status=Installment.STATUS_PENDING,
            account=self.account,
        )
        response = self.client.post(
            reverse("core:installment_pay", args=[installment.id]),
            data={
                "paid_amount": "3300.00",
                "paid_date": "2026-07-03",
                "payment_method": "cash",
                "received_by": "Test Receiver",
                "notes": "",
            }
        )
        self.assertEqual(response.status_code, 302)
        log = ActivityLog.objects.filter(action=ActivityLog.ACTION_PAYMENT).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.model_name, "Installment")
        self.assertIn("3300.00", log.description)
        self.assertEqual(log.user, "testadmin")

    def test_installment_receipt_renders_correctly(self):
        contract = Contract.objects.create(
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
            account=self.account,
        )
        installment = Installment.objects.create(
            contract=contract,
            installment_number=1,
            due_date=date(2026, 7, 1),
            amount=Decimal("3300.00"),
            paid_amount=Decimal("3300.00"),
            paid_date=date(2026, 7, 3),
            status=Installment.STATUS_PAID,
            payment_method=Installment.PAYMENT_CASH,
            account=self.account,
        )
        response = self.client.get(reverse("core:installment_receipt", args=[installment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Customer")
        self.assertContains(response, "3300")
        self.assertContains(response, "الشهر المستحق عنه")



