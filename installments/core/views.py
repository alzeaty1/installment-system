import calendar
import json
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .calculations import calculate_mode_a, calculate_mode_b, calculate_mode_c
from .models import (
    Account,
    ActivityLog,
    Contract,
    Customer,
    Expense,
    Installment,
    MAX_MONEY_AMOUNT,
    MonthlyIncome,
    Notification,
    Product,
    ProductType,
    Receiver,
    Settings,
    Supplier,
    SupplierCategory,
    SupplierPurchase,
)


MONEY_ZERO = Decimal("0.00")
TEXT_FIELD_LIMITS = {
    "name": 255,
    "customer_name": 255,
    "supplier_name": 255,
    "product_name": 255,
    "phone": 50,
    "national_id": 50,
    "whatsapp": 50,
    "brand": 255,
    "title": 255,
    "category": 255,
    "business_name": 255,
}
MONEY_FIELD_NAMES = {
    "estimated_price",
    "purchase_price",
    "actual_cost",
    "customer_price",
    "down_payment",
    "remaining_amount",
    "total_interest",
    "total_amount",
    "installment_amount",
    "amount",
    "paid_amount",
}
DAY_FIELD_NAMES = {"payment_due_day", "default_payment_due_day"}


def _sum(queryset, field):
    return queryset.aggregate(total=Sum(field, default=MONEY_ZERO))["total"] or MONEY_ZERO


def _remaining_installments_total(queryset):
    total = (
        queryset.aggregate(total=Sum(F("amount") - F("paid_amount"), default=MONEY_ZERO))["total"]
        or MONEY_ZERO
    )
    return max(total, MONEY_ZERO)


def _receipt_remaining_balance(installment):
    """Historical remaining balance for this receipt moment.

    A receipt should reflect the contract balance *after this installment's payment*,
    not the current live balance after later installments may have been paid.
    """
    paid_through_this_installment = (
        installment.contract.installments.filter(
            installment_number__lte=installment.installment_number
        ).aggregate(total=Sum("paid_amount", default=MONEY_ZERO))["total"]
        or MONEY_ZERO
    )
    return max((installment.contract.total_amount or MONEY_ZERO) - paid_through_this_installment, MONEY_ZERO)


def _settings():
    settings, _created = Settings.objects.get_or_create(pk=1)
    return settings


def _get_or_create_monthly_income(account, year, month):
    """Return the MonthlyIncome row for the given (account, year, month), creating it if needed."""
    obj, _created = MonthlyIncome.objects.get_or_create(
        account=account, year=year, month=month,
    )
    return obj


def _monthly_income_context(account, today):
    """Compute the expected/collected monthly income pair for the dashboard.

    Returns a dict with expected, collected, is_override flags for the current
    month, used by the dashboard card.
    """
    income_row = _get_or_create_monthly_income(account, today.year, today.month)
    auto_collected = (
        Installment.objects
        .filter(account=account, paid_date__year=today.year, paid_date__month=today.month)
        .aggregate(total=Sum("paid_amount", default=MONEY_ZERO))["total"]
    )
    collected_display = income_row.get_collected_amount(auto_collected)
    return {
        "income_row": income_row,
        "expected_monthly_income": income_row.expected_monthly_income,
        "collected_amount_display": collected_display,
        "collected_is_override": income_row.is_override,
        "collected_auto": auto_collected,
    }


def _today():
    return timezone.localdate()


def _add_months(source_date, months, due_day):
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return source_date.replace(year=year, month=month, day=min(int(due_day), last_day))


def _apply_bootstrap(form):
    for name, field in form.fields.items():
        current = field.widget.attrs.get("class", "")
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = (current + " form-check-input").strip()
        elif isinstance(field.widget, forms.Select):
            field.widget.attrs["class"] = (current + " form-select").strip()
        else:
            field.widget.attrs["class"] = (current + " form-control").strip()

        if name in TEXT_FIELD_LIMITS:
            field.widget.attrs.setdefault("maxlength", str(TEXT_FIELD_LIMITS[name]))
        if name in MONEY_FIELD_NAMES:
            field.min_value = Decimal("0.00")
            field.max_value = MAX_MONEY_AMOUNT
            field.widget.attrs.setdefault("min", "0")
            field.widget.attrs.setdefault("max", str(MAX_MONEY_AMOUNT))
            field.widget.attrs.setdefault("step", "0.01")
        if name in DAY_FIELD_NAMES:
            field.min_value = 1
            field.max_value = 31
            field.widget.attrs.setdefault("min", "1")
            field.widget.attrs.setdefault("max", "31")
    return form


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class CustomerForm(BootstrapModelForm):
    new_product_image = forms.ImageField(
        label="صورة المنتج أو السيريال أو فاتورة الشراء",
        required=False,
    )

    class Meta:
        model = Customer
        fields = ["name", "phone", "national_id", "address", "whatsapp"]
        labels = {
            "name": "اسم العميل",
            "phone": "رقم الهاتف",
            "national_id": "الرقم القومي",
            "address": "العنوان",
            "whatsapp": "واتساب",
        }
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class SupplierForm(BootstrapModelForm):
    category_name = forms.CharField(
        label="الفئة",
        required=False,
        widget=forms.TextInput(attrs={"list": "categorySuggestions", "placeholder": "اكتب اسم الفئة للبحث أو إضافة جديد"}),
    )

    class Meta:
        model = Supplier
        fields = ["name", "phone", "address", "notes"]
        labels = {
            "name": "اسم التاجر",
            "phone": "رقم الهاتف",
            "address": "العنوان",
            "notes": "ملاحظات",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.category:
            self.fields["category_name"].initial = self.instance.category.name

    def clean(self):
        cleaned_data = super().clean()
        category_name = (cleaned_data.get("category_name") or "").strip()
        if category_name:
            category = SupplierCategory.objects.filter(name__iexact=category_name).order_by("id").first()
            if not category:
                category = SupplierCategory.objects.create(name=category_name)
            cleaned_data["category"] = category
        else:
            cleaned_data["category"] = None
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "category" in self.cleaned_data:
            instance.category = self.cleaned_data["category"]
        if commit:
            instance.save()
        return instance


class ProductForm(BootstrapModelForm):
    new_product_image = forms.ImageField(
        label="صورة المنتج أو السيريال أو فاتورة الشراء",
        required=False,
    )

    class Meta:
        model = Product
        fields = ["name", "brand", "category", "product_type", "model_name", "estimated_price", "image"]
        labels = {
            "name": "اسم المنتج",
            "brand": "الماركة",
            "category": "الفئة",
            "product_type": "النوع",
            "model_name": "الموديل",
            "estimated_price": "السعر التقديري",
            "image": "الصورة",
        }


class ContractForm(BootstrapModelForm):
    # Single text fields for customer, product, supplier — typed name with datalist
    customer_name = forms.CharField(
        label="العميل",
        required=False,
        widget=forms.TextInput(attrs={"list": "customerSuggestions", "placeholder": "اكتب اسم العميل للبحث أو إضافة جديد"}),
    )
    supplier_name = forms.CharField(
        label="التاجر (المورد)",
        required=False,
        widget=forms.TextInput(attrs={"list": "supplierSuggestions", "placeholder": "اكتب اسم التاجر للبحث أو إضافة جديد"}),
    )
    product_name = forms.CharField(
        label="المنتج",
        required=False,
        widget=forms.TextInput(attrs={"list": "productSuggestions", "placeholder": "اكتب اسم المنتج للبحث أو إضافة جديد"}),
    )

    new_product_image = forms.ImageField(
        label="صورة المنتج أو السيريال أو فاتورة الشراء",
        required=False,
    )
    purchase_date = forms.DateField(
        label="تاريخ الشراء",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    product_type = forms.ModelChoiceField(
        queryset=ProductType.objects.none(),
        label="نوع المنتج",
        required=False,
        empty_label="اختر النوع",
    )
    model_name = forms.CharField(
        label="الموديل",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "اكتب رقم/اسم الموديل"}),
    )

    class Meta:
        model = Contract
        fields = [
            "actual_cost",
            "customer_price",
            "down_payment",
            "calculation_mode",
            "interest_rate",
            "months_count",
            "installment_amount",
            "start_date",
            "payment_due_day",
            "status",
            "notes",
        ]
        labels = {
            "actual_cost": "سعر الشراء الفعلي",
            "customer_price": "السعر للعميل",
            "down_payment": "المقدم",
            "calculation_mode": "طريقة الحساب",
            "interest_rate": "نسبة الفائدة %",
            "months_count": "عدد الشهور",
            "installment_amount": "القسط الشهري",
            "start_date": "تاريخ البداية",
            "payment_due_day": "يوم الاستحقاق",
            "status": "الحالة",
            "notes": "ملاحظات",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        allow_inline_create = kwargs.pop("allow_inline_create", True)
        account = kwargs.pop("account", None)
        super().__init__(*args, **kwargs)
        self.fields["calculation_mode"].choices = [
            ("A", "A - القسط وعدد الشهور"),
            ("B", "B - النسبة وعدد الشهور"),
            ("C", "C - اقتراح النسبة"),
        ]
        self.fields["status"].choices = [
            ("active", "نشط"),
            ("completed", "مكتمل"),
            ("overdue", "متأخر"),
            ("cancelled", "ملغي"),
        ]
        self.fields["interest_rate"].required = False
        self.fields["installment_amount"].required = False
        self.fields["payment_due_day"].min_value = 1
        self.fields["payment_due_day"].max_value = 31
        if not self.instance.pk:
            self.fields["purchase_date"].initial = _today()

        # Set product_type queryset for current account
        if "product_type" in self.fields:
            if account:
                self.fields["product_type"].queryset = ProductType.objects.filter(account=account).order_by("name")
            else:
                self.fields["product_type"].queryset = ProductType.objects.none()

        # Pre-fill on edit
        if self.instance and self.instance.pk:
            if self.instance.customer:
                self.fields["customer_name"].initial = self.instance.customer.name
            if self.instance.supplier:
                self.fields["supplier_name"].initial = self.instance.supplier.name
            if self.instance.product:
                self.fields["product_name"].initial = self.instance.product.name
                if self.instance.product.product_type:
                    self.fields["product_type"].initial = self.instance.product.product_type
                if self.instance.product.model_name:
                    self.fields["model_name"].initial = self.instance.product.model_name
            elif self.instance.product_name:
                self.fields["product_name"].initial = self.instance.product_name

        if not allow_inline_create:
            for field_name in ["new_product_image", "purchase_date", "product_type", "model_name"]:
                self.fields.pop(field_name, None)
        else:
            self.order_fields(
                [
                    "customer_name",
                    "supplier_name",
                    "product_name",
                    "product_type",
                    "model_name",
                    "new_product_image",
                    "purchase_date",
                    "actual_cost",
                    "customer_price",
                    "down_payment",
                    "calculation_mode",
                    "interest_rate",
                    "months_count",
                    "installment_amount",
                    "start_date",
                    "payment_due_day",
                    "status",
                    "notes",
                ]
            )

    def clean(self):
        cleaned_data = super().clean()
        customer_name = (cleaned_data.get("customer_name") or "").strip()
        supplier_name = (cleaned_data.get("supplier_name") or "").strip()
        product_name = (cleaned_data.get("product_name") or "").strip()

        if not customer_name:
            self.add_error("customer_name", "اكتب اسم العميل.")
        if not product_name:
            self.add_error("product_name", "اكتب اسم المنتج.")

        return cleaned_data


class InstallmentPaymentForm(BootstrapModelForm):

    class Meta:
        model = Installment
        fields = ["paid_amount", "paid_date", "payment_method", "transfer_sender_account", "transfer_sender_name", "transfer_image", "received_by", "notes"]
        labels = {
            "paid_amount": "مبلغ الدفعة",
            "paid_date": "تاريخ الدفع",
            "payment_method": "طريقة الدفع",
            "transfer_sender_account": "رقم الحساب/المحفظة",
            "transfer_sender_name": "اسم المرسل",
            "transfer_image": "صورة التحويل",
            "received_by": "المستلم (كاش)",
            "notes": "ملاحظات",
        }
        widgets = {
            "paid_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("payment_method")
        
        if method in ["instapay", "wallet"]:
            if not cleaned_data.get("transfer_sender_account"):
                self.add_error("transfer_sender_account", "يجب إدخال رقم الحساب أو المحفظة.")
            if not cleaned_data.get("transfer_sender_name"):
                self.add_error("transfer_sender_name", "يجب إدخال اسم المرسل.")
        
        elif method == "cash":
            receiver_id = self.data.get("receiver")
            if receiver_id:
                try:
                    from .models import Receiver
                    receiver = Receiver.objects.get(id=int(receiver_id), account=self.instance.account)
                    cleaned_data["received_by"] = receiver.name
                except (ValueError, TypeError, Receiver.DoesNotExist):
                    pass
            if not cleaned_data.get("received_by"):
                self.add_error(None, "يجب اختيار المستلم أو إدخال اسمه.")
        
        return cleaned_data

    def clean_paid_amount(self):
        paid_amount = self.cleaned_data["paid_amount"]
        if paid_amount <= 0:
            raise forms.ValidationError("مبلغ الدفعة يجب أن يكون أكبر من صفر.")
        return paid_amount


class InstallmentEditForm(BootstrapModelForm):
    """Edit an installment's amount/due date, and correct a mis-typed payment amount."""

    class Meta:
        model = Installment
        fields = ["amount", "due_date", "notes", "paid_amount"]
        labels = {
            "amount": "قيمة القسط",
            "due_date": "تاريخ الاستحقاق",
            "notes": "ملاحظات",
            "paid_amount": "المبلغ المدفوع (تصحيح خطأ إدخال)",
        }
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paid_amount"].help_text = (
            "استخدمه لتصحيح رقم دفعة اتكتبت غلط فقط — مش لإلغاء الدفعة "
            "(للإلغاء استخدم زر إلغاء الدفع في صفحة العقد)."
        )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("قيمة القسط يجب أن تكون أكبر من صفر.")
        return amount

    def clean_paid_amount(self):
        paid = self.cleaned_data["paid_amount"]
        if paid is None or paid < 0:
            raise forms.ValidationError("المدفوع لا يمكن أن يكون سالبًا.")
        amount = self.cleaned_data.get("amount") or self.initial.get("amount")
        if amount and paid > amount * 2:
            raise forms.ValidationError(
                f"المدفوع ({paid}) أكبر من ضعف قيمة القسط — راجع الرقم، "
                "ولو الزيادة مقصودة وزعها من شاشة الدفع."
            )
        return paid


class ExpenseForm(BootstrapModelForm):
    new_product_image = forms.ImageField(
        label="صورة المنتج أو السيريال أو فاتورة الشراء",
        required=False,
    )

    class Meta:
        model = Expense
        fields = ["title", "amount", "expense_date", "category", "notes"]
        labels = {
            "title": "البند",
            "amount": "المبلغ",
            "expense_date": "تاريخ المصروف",
            "category": "الفئة",
            "notes": "ملاحظات",
        }
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class SettingsForm(BootstrapModelForm):
    new_product_image = forms.ImageField(
        label="صورة المنتج أو السيريال أو فاتورة الشراء",
        required=False,
    )

    class Meta:
        model = Settings
        fields = [
            "business_name",
            "default_interest_rate",
            "default_payment_due_day",
            "whatsapp_enabled",
        ]
        labels = {
            "business_name": "اسم النشاط",
            "default_interest_rate": "النسبة الشهرية الافتراضية %",
            "default_payment_due_day": "يوم الاستحقاق الافتراضي",
            "whatsapp_enabled": "تفعيل واتساب",
        }


def _calculate_contract_values(data):
    customer_price = Decimal(str(data.get("customer_price") or 0))
    down_payment = Decimal(str(data.get("down_payment") or 0))
    remaining = customer_price - down_payment
    months_count = int(data.get("months_count") or 0)
    mode = data.get("calculation_mode") or "B"

    if mode == "A":
        result = calculate_mode_a(remaining, data.get("installment_amount") or 0, months_count)
    elif mode == "C":
        result = calculate_mode_c(remaining, months_count, _settings().default_interest_rate)
    else:
        result = calculate_mode_b(remaining, data.get("interest_rate") or 0, months_count)

    for field_name in [
        "remaining_amount",
        "total_interest",
        "total_amount",
        "installment_amount",
    ]:
        if result[field_name] > MAX_MONEY_AMOUNT:
            raise ValueError("لا يمكن أن يزيد أي مبلغ عن 100000 جنيه.")
    return result


def _set_contract_calculations(contract, cleaned_data):
    result = _calculate_contract_values(cleaned_data)
    contract.remaining_amount = result["remaining_amount"]
    contract.interest_rate = result["interest_rate"]
    contract.total_interest = result["total_interest"]
    contract.total_amount = result["total_amount"]
    contract.installment_amount = result["installment_amount"]
    contract.months_count = result["months_count"]
    return result


def _generate_installments(contract):
    installments = []
    for index in range(contract.months_count):
        installments.append(
            Installment(
                contract=contract,
                installment_number=index + 1,
                due_date=_add_months(contract.start_date, index, contract.payment_due_day),
                amount=contract.installment_amount,
                account=contract.account,
            )
        )
    Installment.objects.bulk_create(installments)


def _apply_contract_form_entities(contract, cleaned_data, files=None):
    """Handle customer, supplier & product via single text fields — lookup-or-create.
    
    All three are plain CharFields with <datalist>. We look up existing entities 
    by name (case-insensitive) to prevent duplicates. If not found, create new ones.
    """
    customer_name = (cleaned_data.get("customer_name") or "").strip()
    supplier_name = (cleaned_data.get("supplier_name") or "").strip()
    product_name = (cleaned_data.get("product_name") or "").strip()
    new_product_image = cleaned_data.get("new_product_image")
    files = files or {}

    # --- Customer: lookup by name within the current account, create if new ---
    if customer_name:
        customer = Customer.objects.filter(
            account=contract.account,
            name__iexact=customer_name,
        ).order_by("id").first()
        if not customer:
            customer = Customer.objects.create(name=customer_name, phone="", account=contract.account)
        contract.customer = customer

    # --- Supplier: lookup by name within the current account, create if new ---
    if supplier_name:
        supplier = Supplier.objects.filter(
            account=contract.account,
            name__iexact=supplier_name,
        ).order_by("id").first()
        if not supplier:
            supplier = Supplier.objects.create(name=supplier_name, phone="", account=contract.account)
        contract.supplier = supplier

    # --- Product: lookup by name within the current account, create if new ---
    if product_name:
        product = Product.objects.filter(
            account=contract.account,
            name__iexact=product_name,
        ).order_by("id").first()
        product_type = cleaned_data.get("product_type")
        model_name = cleaned_data.get("model_name")
        if not product:
            product = Product.objects.create(
                name=product_name,
                brand="",
                image=new_product_image or None,
                account=contract.account,
                product_type=product_type,
                model_name=model_name,
            )
        elif new_product_image and not product.image:
            product.image = new_product_image
            product.save(update_fields=["image"])
        # Update type/model if provided and not set
        if product_type and not product.product_type:
            product.product_type = product_type
        if model_name and not product.model_name:
            product.model_name = model_name
            product.save(update_fields=["product_type", "model_name"])
        contract.product = product
        contract.product_name = product.name

    return contract


def _create_contract_purchase_record(contract, cleaned_data):
    if not contract.product:
        return None

    purchase_date = cleaned_data.get("purchase_date") or contract.start_date or _today()
    invoice_image = cleaned_data.get("new_product_image")
    return SupplierPurchase.objects.create(
        supplier=contract.supplier,
        customer=contract.customer,
        product=contract.product,
        contract=contract,
        product_name=contract.product_name,
        purchase_price=contract.actual_cost,
        purchase_date=purchase_date,
        image=invoice_image or None,
        notes=f"تم إنشاء سجل الشراء من العقد {contract.contract_number}",
        account=contract.account,
    )


CONTRACT_SCHEDULE_FIELDS = [
    "customer_price",
    "down_payment",
    "calculation_mode",
    "interest_rate",
    "months_count",
    "installment_amount",
    "start_date",
    "payment_due_day",
]


def _contract_schedule_values(contract):
    return {field: getattr(contract, field) for field in CONTRACT_SCHEDULE_FIELDS}


def _contract_schedule_fields_changed(original_values, cleaned_data):
    return any(
        original_values[field] != cleaned_data.get(field)
        for field in CONTRACT_SCHEDULE_FIELDS
    )


def _mark_late_installments():
    late_qs = Installment.objects.filter(
        due_date__lt=_today(),
        status=Installment.STATUS_PENDING,
    ).exclude(contract__status=Contract.STATUS_EARLY_COMPLETED)
    late_contract_ids = list(late_qs.values_list("contract_id", flat=True).distinct())
    late_qs.update(status=Installment.STATUS_LATE)
    Contract.objects.filter(id__in=late_contract_ids, status=Contract.STATUS_ACTIVE).update(
        status=Contract.STATUS_OVERDUE,
    )


def _refresh_contract_status(contract):
    if contract.status == Contract.STATUS_EARLY_COMPLETED:
        return  # early-completed contracts stay closed
    installments = contract.installments.all()
    if installments.exists() and not installments.exclude(status=Installment.STATUS_PAID).exists():
        contract.status = Contract.STATUS_COMPLETED
    elif installments.filter(due_date__lt=_today()).exclude(status=Installment.STATUS_PAID).exists():
        contract.status = Contract.STATUS_OVERDUE
    elif contract.status != Contract.STATUS_CANCELLED:
        contract.status = Contract.STATUS_ACTIVE
    contract.save(update_fields=["status"])


def _maybe_auto_close(contract):
    """أقفل العقد تلقائيًا لحظة وصول إجمالي المسدد لقيمة العقد (من أي مسار).

    يرجع True لو حصل إقفال الآن. العقود المغلقة مبكرًا مستثناة.
    """
    if contract.status == Contract.STATUS_EARLY_COMPLETED:
        return False
    if not contract.installments.exists():
        return False
    if contract.total_paid >= contract.total_amount:
        if contract.status != Contract.STATUS_COMPLETED:
            contract.status = Contract.STATUS_COMPLETED
            contract.save(update_fields=["status"])
        return True
    return False


def _contract_profit(contract):
    return (contract.customer_price - contract.actual_cost) + contract.total_interest


def _contract_report_queryset(account=None):
    qs = Contract.objects.select_related("customer", "product").annotate(collected=Sum("installments__paid_amount", default=MONEY_ZERO))
    if account:
        qs = qs.filter(account=account)
    return qs.order_by("-created_at")


def _pdf_response(template, context, filename):
    html = render_to_string(template, context)
    try:
        from weasyprint import HTML
        pdf = HTML(string=html, base_url=context["request"].build_absolute_uri("/")).write_pdf()
    except Exception as exc:
        messages.error(context["request"], f"تعذر إنشاء ملف PDF: {exc}")
        return redirect("core:reports_dashboard")
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


# --- Authorization helpers ---
def logout_view(request):
    """Custom logout that accepts GET (not just POST)."""
    from django.contrib.auth import logout
    from django.shortcuts import redirect
    logout(request)
    return redirect('/login/')
def require_write(view_func):
    """Decorator: viewers can't create/edit/delete. Redirects all requests."""
    def _wrapped(request, *args, **kwargs):
        if request.user.groups.filter(name='viewer').exists():
            messages.error(request, "صلاحية المشاهدة فقط. لا يمكنك التعديل.")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        return view_func(request, *args, **kwargs)
    return _wrapped

def dashboard(request):
    _mark_late_installments()
    today = _today()
    contracts = Contract.objects.filter(account=request.current_account)
    installments = Installment.objects.select_related("contract", "contract__customer").filter(account=request.current_account)
    
    # أقساط اليوم
    due_today = installments.filter(due_date=today).exclude(status__in=[Installment.STATUS_PAID, Installment.STATUS_CLOSED])
    for inst in due_today:
        inst.whatsapp_url = _get_whatsapp_url(inst, "reminder")
    
    # المتأخرات - مجمعة حسب العميل (عدد الأقساط + إجمالي المبالغ)
    overdue_installments = installments.filter(status=Installment.STATUS_LATE)
    overdue_by_customer = (
        overdue_installments
        .values("contract__customer_id", "contract__customer__name")
        .annotate(
            count=Count("id"),
            total_amount=Sum("amount", default=MONEY_ZERO),
        )
        .order_by("-total_amount")
    )
    overdue_count = overdue_installments.count()
    
    # إجمالي المتوقع اليوم
    total_expected_today = due_today.aggregate(total=Sum("amount", default=MONEY_ZERO))["total"]

    monthly = (
        installments.filter(paid_date__isnull=False)
        .annotate(month=TruncMonth("paid_date"))
        .values("month")
        .annotate(total=Sum("paid_amount", default=MONEY_ZERO))
        .order_by("month")
    )

    # Income collected this month
    income_this_month = (
        installments.filter(
            paid_date__year=today.year,
            paid_date__month=today.month,
        ).aggregate(total=Sum("paid_amount", default=MONEY_ZERO))["total"]
    )

    # Expected vs Collected monthly income (Task 1)
    income_ctx = _monthly_income_context(request.current_account, today)

    # New & completed contracts this month
    new_contracts_count = contracts.filter(
        created_at__year=today.year,
        created_at__month=today.month,
    ).count()
    completed_count = contracts.filter(
        status=Contract.STATUS_COMPLETED,
        updated_at__year=today.year,
        updated_at__month=today.month,
    ).count()

    # Installments due this month
    due_this_qs = installments.filter(
        due_date__year=today.year,
        due_date__month=today.month,
    )
    expected_this_month = due_this_qs.count()
    collected_this_month = due_this_qs.filter(status=Installment.STATUS_PAID).count()
    overdue_this_month = due_this_qs.filter(status=Installment.STATUS_LATE).count()
    pending_this_month = due_this_qs.filter(status=Installment.STATUS_PENDING).count()

    # Aggregate totals (single query instead of loading all contracts into memory)
    profit_data = contracts.aggregate(
        total_price=Sum("customer_price", default=MONEY_ZERO),
        total_cost=Sum("actual_cost", default=MONEY_ZERO),
        total_interest=Sum("total_interest", default=MONEY_ZERO),
    )
    total_profit = (profit_data["total_price"] - profit_data["total_cost"]) + profit_data["total_interest"]

    # Recent payments should mean latest payment actions, not highest paid_date.
    # A payment can be recorded with a future/old paid_date, so use ActivityLog.created_at.
    recent_payment_logs = list(
        ActivityLog.objects.filter(
            account=request.current_account,
            action=ActivityLog.ACTION_PAYMENT,
            model_name="Installment",
            object_id__isnull=False,
        ).order_by("-created_at")[:20]
    )
    recent_payment_installment_ids = [log.object_id for log in recent_payment_logs]
    recent_payment_installments = {
        inst.id: inst for inst in Installment.objects.filter(
            account=request.current_account,
            id__in=recent_payment_installment_ids,
        ).select_related("contract", "contract__customer")
    }
    recent_payments = []
    for log in recent_payment_logs:
        inst = recent_payment_installments.get(log.object_id)
        if not inst:
            continue
        try:
            payment_amount = Decimal(log.new_value.get("paid_amount", "0")) - Decimal(log.previous_value.get("paid_amount", "0"))
        except Exception:
            payment_amount = inst.paid_amount
        recent_payments.append({
            "contract_number": inst.contract.contract_number,
            "customer_name": inst.contract.customer.name,
            "amount": payment_amount,
            "created_at": log.created_at,
        })
        if len(recent_payments) >= 5:
            break

    status_qs = contracts.values("status").annotate(count=Count("id"))

    context = {
        "due_today": due_today,
        "overdue_by_customer": overdue_by_customer,
        "overdue_count": overdue_count,
        "total_expected_today": total_expected_today,
        "income_this_month": income_this_month,
        "expected_monthly_income": income_ctx["expected_monthly_income"],
        "collected_amount_display": income_ctx["collected_amount_display"],
        "collected_is_override": income_ctx["collected_is_override"],
        "collected_auto": income_ctx["collected_auto"],
        "monthly_income_id": income_ctx["income_row"].id,
        "new_contracts_count": new_contracts_count,
        "completed_count": completed_count,
        "expected_this_month": expected_this_month,
        "collected_this_month": collected_this_month,
        "overdue_this_month": overdue_this_month,
        "pending_this_month": pending_this_month,
        "active_contracts": contracts.filter(status=Contract.STATUS_ACTIVE).count(),
        "total_completed": contracts.filter(status=Contract.STATUS_COMPLETED).count(),
        "total_cancelled": contracts.filter(status=Contract.STATUS_CANCELLED).count(),
        "due_today_count": due_today.count(),
        "overdue_count": overdue_count,
        "total_invested": _sum(contracts, "actual_cost"),
        "total_collected": _sum(installments, "paid_amount"),
        "total_profit": total_profit,
        "total_customers": Customer.objects.filter(account=request.current_account).count(),
        "total_contracts": contracts.count(),
        "recent_contracts": contracts.select_related("customer").order_by("-created_at")[:5],
        "recent_payments": recent_payments,
        "get_whatsapp_url": _get_whatsapp_url,
        "chart_labels": json.dumps([item["month"].strftime("%Y-%m") for item in monthly]),
        "chart_values": json.dumps([float(item["total"]) for item in monthly]),
        "status_labels": json.dumps(["نشط", "مكتمل", "متأخر", "ملغي"]),
        "status_values": json.dumps([
            contracts.filter(status=Contract.STATUS_ACTIVE).count(),
            contracts.filter(status=Contract.STATUS_COMPLETED).count(),
            contracts.filter(status=Contract.STATUS_OVERDUE).count(),
            contracts.filter(status=Contract.STATUS_CANCELLED).count(),
        ]),
    }
    return render(request, "core/dashboard.html", context)


def customer_list(request):
    query = request.GET.get("q", "").strip()
    customers = (
        Customer.objects.filter(account=request.current_account)
        .annotate(
            contracts_count=Count("contract"),
            open_contracts_count=Count(
                "contract",
                filter=~Q(contract__status__in=[Contract.STATUS_COMPLETED, Contract.STATUS_EARLY_COMPLETED]),
            ),
        )
        .order_by("-created_at")
    )
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    paginator = Paginator(customers, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/customers_list.html", {"customers": page, "query": query})


@require_write
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.account = request.current_account
        customer.save()

        # Log creation
        _log_activity(
            request,
            action=ActivityLog.ACTION_CREATE,
            model_name="Customer",
            obj=customer,
            description=f"إضافة عميل جديد: {customer.name}، هاتف: {customer.phone}",
            new_value={"name": customer.name, "phone": customer.phone}
        )

        messages.success(request, "تم حفظ العميل.")
        return redirect("core:customer_detail", id=customer.id)
    return render(request, "core/customers_form.html", {"form": form, "title": "إضافة عميل"})


def customer_detail(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    contracts = (
        Contract.objects
        .filter(customer=customer, account=request.current_account)
        .select_related("product")
        .order_by("-created_at")
    )
    installments = Installment.objects.filter(contract__customer=customer, account=request.current_account).select_related("contract").order_by("due_date")
    
    late_installments = list(installments.filter(status=Installment.STATUS_LATE))
    for inst in late_installments:
        inst.whatsapp_url = _get_whatsapp_url(inst, "overdue")
    
    total_paid = _sum(installments, "paid_amount")
    total_due = _remaining_installments_total(installments)
    total_amount = _sum(installments, "amount")
    
    commitment = 0
    if total_amount > 0:
        commitment = (total_paid / total_amount) * 100

    context = {
        "customer": customer,
        "contracts": contracts,
        "installments": installments,
        "late_installments": late_installments,
        "total_paid": total_paid,
        "total_due": total_due,
        "contracts_count": contracts.count(),
        "late_installments_count": installments.filter(status=Installment.STATUS_LATE).count(),
        "commitment": commitment,
    }
    return render(request, "core/customers_detail.html", context)


@require_write
def customer_edit(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    old_values = {"name": customer.name, "phone": customer.phone}
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()

        # Log update
        new_values = {"name": customer.name, "phone": customer.phone}
        _log_activity(
            request,
            action=ActivityLog.ACTION_UPDATE,
            model_name="Customer",
            obj=customer,
            description=f"تعديل بيانات العميل: {customer.name}",
            previous_value=old_values,
            new_value=new_values
        )

        messages.success(request, "تم تحديث العميل.")
        return redirect("core:customer_detail", id=customer.id)
    return render(request, "core/customers_form.html", {"form": form, "title": "تعديل عميل"})


@require_write
def customer_delete(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    if request.method == "POST":
        # Log delete
        _log_activity(
            request,
            action=ActivityLog.ACTION_DELETE,
            model_name="Customer",
            obj=customer,
            description=f"حذف العميل: {customer.name} مع جميع البيانات المرتبطة به",
            previous_value={"name": customer.name, "phone": customer.phone}
        )
        customer.delete()
        messages.success(request, "تم حذف العميل وكل البيانات المرتبطة به.")
        return redirect("core:customer_list")
    return redirect("core:customer_detail", id=customer.id)


def supplier_list(request):
    query = request.GET.get("q", "").strip()
    suppliers = Supplier.objects.filter(account=request.current_account).select_related("category").order_by("-created_at")
    if query:
        suppliers = suppliers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    return render(request, "core/suppliers_list.html", {"suppliers": suppliers, "query": query})


@require_write
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save(commit=False)
        supplier.account = request.current_account
        supplier.save()
        form.save_m2m()
        messages.success(request, "تم حفظ التاجر.")
        return redirect("core:supplier_detail", id=supplier.id)
    category_suggestions = SupplierCategory.objects.order_by("name")
    return render(request, "core/suppliers_form.html", {"form": form, "title": "إضافة تاجر", "category_suggestions": category_suggestions})


def supplier_detail(request, id):
    supplier = get_object_or_404(Supplier, id=id, account=request.current_account)
    purchases = SupplierPurchase.objects.filter(supplier=supplier, account=request.current_account).select_related("product").order_by("-purchase_date")
    return render(
        request,
        "core/suppliers_detail.html",
        {"supplier": supplier, "purchases": purchases, "total_spent": _sum(purchases, "purchase_price")},
    )


@require_write
def supplier_edit(request, id):
    supplier = get_object_or_404(Supplier, id=id, account=request.current_account)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث التاجر.")
        return redirect("core:supplier_detail", id=supplier.id)
    category_suggestions = SupplierCategory.objects.order_by("name")
    return render(request, "core/suppliers_form.html", {"form": form, "title": "تعديل تاجر", "category_suggestions": category_suggestions})


@require_write
def supplier_delete(request, id):
    supplier = get_object_or_404(Supplier, id=id, account=request.current_account)
    if request.method == "POST":
        supplier.delete()
        messages.success(request, "تم حذف التاجر.")
        return redirect("core:supplier_list")
    return redirect("core:supplier_detail", id=supplier.id)


def product_list(request):
    query = request.GET.get("q", "").strip()
    type_id = request.GET.get("type", "").strip()
    model_query = request.GET.get("model", "").strip()

    products = (
        Product.objects.filter(account=request.current_account).select_related("category", "product_type")
        .annotate(
            purchases_count=Count("purchase_records"),
            last_purchase_date=Max("purchase_records__purchase_date"),
        )
        .order_by("-created_at")
    )
    if query:
        products = products.filter(Q(name__icontains=query) | Q(brand__icontains=query))
    if type_id:
        products = products.filter(product_type_id=type_id)
    if model_query:
        products = products.filter(model_name__icontains=model_query)

    product_types = ProductType.objects.filter(account=request.current_account).order_by("name")

    return render(
        request,
        "core/products_list.html",
        {
            "products": products,
            "query": query,
            "selected_type": type_id,
            "model_query": model_query,
            "product_types": product_types,
        },
    )


@require_write
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.account = request.current_account
        product.save()
        messages.success(request, "تم حفظ المنتج.")
        return redirect("core:product_detail", id=product.id)
    return render(request, "core/products_form.html", {"form": form, "title": "إضافة منتج"})


def product_detail(request, id):
    product = get_object_or_404(Product, id=id, account=request.current_account)
    contracts = Contract.objects.filter(product=product, account=request.current_account).select_related("customer").order_by("-created_at")
    purchases = (
        SupplierPurchase.objects.filter(product=product, account=request.current_account)
        .select_related("supplier", "customer", "contract")
        .order_by("-purchase_date", "-created_at")
    )
    return render(
        request,
        "core/products_detail.html",
        {
            "product": product,
            "contracts": contracts,
            "purchases": purchases,
            "purchase_count": purchases.count(),
            "contracts_count": contracts.count(),
            "total_purchase_cost": _sum(purchases, "purchase_price"),
        },
    )


@require_write
def product_edit(request, id):
    product = get_object_or_404(Product, id=id, account=request.current_account)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث المنتج.")
        return redirect("core:product_detail", id=product.id)
    return render(request, "core/products_form.html", {"form": form, "title": "تعديل منتج"})


@require_write
def product_delete(request, id):
    product = get_object_or_404(Product, id=id, account=request.current_account)
    if request.method == "POST":
        product.delete()
        messages.success(request, "تم حذف المنتج. العقود القديمة ستحتفظ باسم المنتج المسجل عليها.")
        return redirect("core:product_list")
    return redirect("core:product_detail", id=product.id)


def contract_list(request):
    _mark_late_installments()
    status = request.GET.get("status", "")
    customer_id = request.GET.get("customer", "")
    contracts = Contract.objects.filter(account=request.current_account).select_related("customer", "product").order_by("-created_at")
    if status:
        contracts = contracts.filter(status=status)
    if customer_id:
        contracts = contracts.filter(customer_id=customer_id)
    paginator = Paginator(contracts, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/contracts_list.html", {"contracts": page, "customers": Customer.objects.filter(account=request.current_account).order_by("name"), "status": status, "customer_id": customer_id})


def _contract_form_context(form, title, is_create, account=None):
    return {
        "form": form,
        "title": title,
        "is_create": is_create,
        "customer_suggestions": Customer.objects.filter(account=account).order_by("name") if account else Customer.objects.order_by("name"),
        "supplier_suggestions": Supplier.objects.filter(account=account).order_by("name") if account else Supplier.objects.order_by("name"),
        "product_suggestions": Product.objects.filter(account=account).order_by("name", "brand") if account else Product.objects.order_by("name", "brand"),
        "product_types": ProductType.objects.filter(account=account).order_by("name") if account else ProductType.objects.order_by("name"),
    }


@require_write
def contract_create(request):
    if request.GET.get("calculate") == "1":
        try:
            result = _calculate_contract_values(request.GET)
            return JsonResponse({key: str(value) for key, value in result.items()})
        except Exception as exc:
            return JsonResponse({"success": False, "error": str(exc)})

    settings = _settings()
    initial = {
        "start_date": _add_months(_today(), 1, _today().day),
        "payment_due_day": settings.default_payment_due_day,
        "interest_rate": settings.default_interest_rate,
        "calculation_mode": "B",
    }
    form = ContractForm(request.POST or None, request.FILES or None, initial=initial, allow_inline_create=True, account=request.current_account)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                contract = form.save(commit=False)
                contract.account = request.current_account
                _apply_contract_form_entities(contract, form.cleaned_data, request.FILES)
                _set_contract_calculations(contract, form.cleaned_data)
                contract.save()
                _create_contract_purchase_record(contract, form.cleaned_data)
                _generate_installments(contract)
            
            # Log contract creation
            _log_activity(
                request,
                action=ActivityLog.ACTION_CREATE,
                model_name="Contract",
                obj=contract,
                description=f"إنشاء عقد جديد برقم {contract.contract_number} للعميل {contract.customer.name} بقيمة إجمالية {contract.total_amount} جنيه",
                new_value={
                    "total_amount": str(contract.total_amount),
                    "customer": contract.customer.name,
                    "product": contract.product_name,
                }
            )

            messages.success(request, "تم حفظ العقد وتوليد الأقساط.")
            return redirect("core:contract_detail", id=contract.id)
        except Exception as exc:
            form.add_error(None, f"تعذر حساب العقد: {exc}")
    return render(request, "core/contracts_form.html", _contract_form_context(form, "إضافة عقد", True, request.current_account))


def contract_detail(request, id):
    contract = get_object_or_404(Contract.objects.select_related("customer", "product"), id=id, account=request.current_account)
    installments = contract.installments.order_by("installment_number")
    
    # إضافة روابط الواتساب للأقساط + المتبقي التراكمي بعد كل قسط
    running_paid = Decimal("0.00")
    for inst in installments:
        inst.whatsapp_reminder = _get_whatsapp_url(inst, "reminder")
        inst.whatsapp_overdue = _get_whatsapp_url(inst, "overdue")
        inst.whatsapp_payment = _get_whatsapp_url(inst, "payment")
        running_paid += inst.paid_amount or MONEY_ZERO
        inst.remaining_after_this = max((contract.total_amount or MONEY_ZERO) - running_paid, MONEY_ZERO)
    
    # حساب التقدم
    total_paid = _sum(installments, "paid_amount")
    paid_count = installments.filter(
        paid_amount__gt=0
    ).count()
    total_count = installments.count()
    progress = contract.progress_percentage

    return render(request, "core/contracts_detail.html", {
        "contract": contract,
        "installments": installments,
        "profit": _contract_profit(contract),
        "total_paid": total_paid,
        "remaining_str": int(contract.total_amount - total_paid),
        "paid_count": paid_count,
        "total_count": total_count,
        "progress": progress,
    })


def _humanize_delay(expected_date, actual_date):
    """Human-readable delay between two dates, e.g. 'ب شهر و 15 يوم'."""
    from calendar import monthrange
    if actual_date <= expected_date:
        return None
    months = 0
    y, m = expected_date.year, expected_date.month
    # count full months between expected and actual
    while True:
        m += 1
        if m > 12:
            m = 1
            y += 1
        anchor_day = min(expected_date.day, monthrange(y, m)[1])
        anchor = expected_date.replace(year=y, month=m, day=anchor_day)
        if anchor > actual_date:
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            break
        months += 1
    # remaining days after full months
    last_valid_day = monthrange(y, m)[1]
    anchor = expected_date.replace(year=y, month=m, day=min(expected_date.day, last_valid_day))
    days = (actual_date - anchor).days

    parts = []
    if months:
        parts.append(f"{'شهر' if months == 1 else f'{months} شهور'}")
    if days or not parts:
        parts.append(f"{'يوم' if days == 1 else 'يومين' if days == 2 else f'{days} يوم'}")
    return " و ".join(parts)


def contract_summary(request, id):
    contract = get_object_or_404(Contract.objects.select_related("customer", "product"), id=id, account=request.current_account)
    installments = contract.installments.order_by("installment_number")
    total_paid = _sum(installments, "paid_amount")
    
    # حساب التقدم — نسبة الفلوس المدفوعة من إجمالي العقد
    paid_count = installments.filter(
        paid_amount__gt=0
    ).count()
    total_count = installments.count()
    progress = contract.progress_percentage

    total_remaining = contract.total_amount - total_paid

    # إعداد رسالة واتساب للشيت
    from urllib.parse import quote
    lines = [
        f"عقد: {contract.contract_number}",
        f"العميل: {contract.customer.name}",
        f"المنتج: {contract.product_name}",
        f"سعر المنتج: {contract.customer_price} جنيه",
    ]
    if contract.down_payment:
        lines.append(f"المقدم: {contract.down_payment} جنيه")
    lines.append(f"النسبة: {contract.interest_rate}%")
    lines.append(f"الإجمالي: {contract.total_amount} جنيه")
    lines.append(f"عدد الأقساط: {contract.months_count}")
    lines.append(f"القسط الشهري: {contract.installment_amount} جنيه")
    lines.append(f"المدفوع: {total_paid} من {contract.total_amount} جنيه")
    whatsapp_msg = quote("\n".join(lines))
    phone = contract.customer.whatsapp or contract.customer.phone
    phone_digits = "".join(filter(str.isdigit, phone))
    whatsapp_url = f"https://wa.me/{phone_digits}?text={whatsapp_msg}"
    
    # جدول الأقساط مع التقدم
    today = _today()
    schedule_rows = []
    carried = Decimal("0.00")
    for inst in installments:
        expected = inst.amount + carried
        paid_now = inst.paid_amount
        carried = expected - paid_now
        schedule_rows.append({
            "inst": inst,
            "expected": expected,
            "carried": carried,
            "remaining": max(inst.amount - inst.paid_amount, Decimal("0.00")),
        })

    # تأخر إتمام العقد: مقارنة آخر قسط مستحق مع تاريخ آخر دفع فعلي (أو اليوم لو لسه)
    contract_delay_text = None
    last_due = installments.order_by("-due_date").first()
    if last_due and total_paid >= contract.total_amount and total_count:
        # العقد مكتمل — اقفل على تاريخ الدفعة الأخيرة الفعلية
        last_paid_date = (
            installments.filter(paid_date__isnull=False)
            .order_by("-paid_date")
            .values_list("paid_date", flat=True)
            .first()
        )
        if last_paid_date and last_paid_date > last_due.due_date:
            contract_delay_text = _humanize_delay(last_due.due_date, last_paid_date)
    elif last_due and total_paid < contract.total_amount and today > last_due.due_date:
        # العقد لسه ماشي وعدى موعد إتمامه
        contract_delay_text = _humanize_delay(last_due.due_date, today)
    
    context = {
        "contract": contract,
        "installments": installments,
        "schedule_rows": schedule_rows,
        "total_paid": total_paid,
        "total_remaining": contract.total_amount - total_paid,
        "paid_count": paid_count,
        "total_count": total_count,
        "progress": progress,
        "whatsapp_url": whatsapp_url,
        "contract_delay_text": contract_delay_text,
        "today": today,
    }
    return render(request, "core/contract_summary.html", context)


@require_write
def contract_edit(request, id):
    if request.GET.get("calculate") == "1":
        try:
            result = _calculate_contract_values(request.GET)
            return JsonResponse({key: str(value) for key, value in result.items()})
        except Exception as exc:
            return JsonResponse({"success": False, "error": str(exc)})

    contract = get_object_or_404(Contract, id=id, account=request.current_account)
    original_schedule_values = _contract_schedule_values(contract)
    
    # Store old values for audit logging
    old_values = {
        "customer_price": str(contract.customer_price),
        "total_amount": str(contract.total_amount),
        "months_count": contract.months_count,
        "status": contract.status,
    }

    form = ContractForm(request.POST or None, request.FILES or None, instance=contract, allow_inline_create=False, account=request.current_account)
    if request.method == "POST" and form.is_valid():
        try:
            schedule_changed = _contract_schedule_fields_changed(
                original_schedule_values,
                form.cleaned_data,
            )
            has_payments = contract.installments.filter(paid_amount__gt=0).exists()
            if schedule_changed and has_payments:
                form.add_error(
                    None,
                    "لا يمكن تعديل حسابات أو جدول عقد عليه مدفوعات مسجلة.",
                )
                raise ValueError("contract schedule has existing payments")

            with transaction.atomic():
                contract = form.save(commit=False)
                _apply_contract_form_entities(contract, form.cleaned_data, request.FILES)
                _set_contract_calculations(contract, form.cleaned_data)
                contract.save()
                if schedule_changed:
                    contract.installments.all().delete()
                    _generate_installments(contract)

            # Log edit activity
            new_values = {
                "customer_price": str(contract.customer_price),
                "total_amount": str(contract.total_amount),
                "months_count": contract.months_count,
                "status": contract.status,
            }
            _log_activity(
                request,
                action=ActivityLog.ACTION_UPDATE,
                model_name="Contract",
                obj=contract,
                description=f"تعديل العقد رقم {contract.contract_number} للعميل {contract.customer.name}",
                previous_value=old_values,
                new_value=new_values,
            )

            messages.success(request, "تم تحديث العقد.")
            return redirect("core:contract_detail", id=contract.id)
        except Exception as exc:
            if not form.non_field_errors():
                form.add_error(None, f"تعذر حساب العقد: {exc}")
    return render(request, "core/contracts_form.html", _contract_form_context(form, "تعديل عقد", False, request.current_account))


@require_write
def contract_mark_completed(request, id):
    contract = get_object_or_404(Contract, id=id, account=request.current_account)
    if request.method == "POST":
        old_status = contract.status
        had_unpaid = contract.installments.exclude(status=Installment.STATUS_PAID).exists()
        if had_unpaid:
            # إغلاق مبكر: اقفل الأقساط المتبقية بدون تسجيل دفع وهمي
            contract.status = Contract.STATUS_EARLY_COMPLETED
            contract.installments.exclude(status=Installment.STATUS_PAID).update(
                status=Installment.STATUS_CLOSED,
            )
            msg = "تم إغلاق العقد مبكرًا — الأقساط المتبقية اعتبرت معفاة ولن تُحسب عليه."
        else:
            contract.status = Contract.STATUS_COMPLETED
            msg = "تم تعليم العقد كمكتمل."
        contract.save(update_fields=["status"])

        # Log completion
        _log_activity(
            request,
            action=ActivityLog.ACTION_MARK_COMPLETED,
            model_name="Contract",
            obj=contract,
            description=f"تعليم العقد رقم {contract.contract_number} للعميل {contract.customer.name} كمكتمل" + (" (إغلاق مبكر مع أقساط معفاة)" if had_unpaid else " وتسوية جميع الأقساط المتبقية"),
            previous_value={"status": old_status},
            new_value={"status": contract.status}
        )

        messages.success(request, msg)
    return redirect("core:contract_detail", id=contract.id)


@require_write
def contract_delete(request, id):
    contract = get_object_or_404(Contract.objects.select_related("customer"), id=id, account=request.current_account)
    if request.method == "POST":
        # Log deletion BEFORE deleting from database
        _log_activity(
            request,
            action=ActivityLog.ACTION_DELETE,
            model_name="Contract",
            obj=contract,
            description=f"حذف العقد رقم {contract.contract_number} للعميل {contract.customer.name} مع جميع الأقساط المرتبطة به",
            previous_value={
                "contract_number": contract.contract_number,
                "customer": contract.customer.name,
                "total_amount": str(contract.total_amount)
            }
        )
        contract.delete()
        messages.success(request, "تم حذف العقد والأقساط المرتبطة به.")
        return redirect("core:contract_list")
    return redirect("core:contract_detail", id=contract.id)


def installment_list(request):
    _mark_late_installments()
    installments = Installment.objects.filter(account=request.current_account).select_related("contract", "contract__customer").order_by("due_date")
    status = request.GET.get("status", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")
    if status:
        installments = installments.filter(status=status)
    if date_from:
        installments = installments.filter(due_date__gte=date_from)
    if date_to:
        installments = installments.filter(due_date__lte=date_to)
    paginator = Paginator(installments, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/installments_list.html", {"installments": page, "status": status, "date_from": date_from, "date_to": date_to})


def _apply_payment(contract, amount, pay_date, payment_method="", receiver=None, received_by="", sender_account="", sender_name="", transfer_image=None, notes=""):
    """وزّع مبلغ الدفعة على أقساط العقد بالترتيب: الناقص أولًا ثم المعلق/المتأخر.

    يرجع (applied_list, last_installment) — applied_list = [(installment, applied_amount)]
    يرفض المبلغ إذا كان أكبر من إجمالي المتبقي على العقد.
    """
    remaining_due = contract.total_amount - contract.total_paid
    if amount > remaining_due:
        raise ValueError(f"المبلغ أكبر من إجمالي المتبقي على العقد ({remaining_due} جنيه).")

    applied = []
    last_inst = None
    left = amount
    for inst in contract.installments.order_by("installment_number"):
        if left <= 0:
            break
        shortfall = inst.amount - inst.paid_amount
        if shortfall <= 0:
            continue  # مدفوع/معفي
        take = min(shortfall, left)
        inst.paid_amount += take
        inst.paid_date = pay_date
        if payment_method:
            inst.payment_method = payment_method
        if receiver is not None:
            inst.receiver = receiver
        if received_by:
            inst.received_by = received_by
        if sender_account:
            inst.transfer_sender_account = sender_account
        if sender_name:
            inst.transfer_sender_name = sender_name
        if transfer_image is not None:
            inst.transfer_image = transfer_image
        if notes:
            inst.notes = notes

        if inst.paid_amount >= inst.amount:
            inst.status = Installment.STATUS_PAID
        else:
            inst.status = Installment.STATUS_PARTIAL
        inst.save()
        applied.append((inst, take))
        last_inst = inst
        left -= take

    _refresh_contract_status(contract)
    return applied, last_inst


@require_write
def installment_pay(request, id):
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id, account=request.current_account)
    contract = installment.contract
    if contract.status == Contract.STATUS_EARLY_COMPLETED:
        messages.error(request, "العقد مغلق مبكرًا — لا يمكن تسجيل دفعات عليه.")
        return redirect("core:contract_detail", id=contract.id)
    initial = {"paid_amount": installment.amount - installment.paid_amount, "paid_date": _today(), "payment_method": Installment.PAYMENT_CASH}
    form = InstallmentPaymentForm(request.POST or None, request.FILES or None, instance=installment, initial=initial)

    # Receivers for combobox
    receivers = Receiver.objects.filter(account=request.current_account, is_active=True)
    last_receiver_id = request.session.get("last_receiver_id")

    if request.method == "POST" and form.is_valid():
        payment_amount = form.cleaned_data["paid_amount"]
        pay_date = form.cleaned_data["paid_date"]
        method = form.cleaned_data.get("payment_method") or ""

        receiver_id = request.POST.get("receiver")
        receiver_obj = None
        received_by = ""
        if receiver_id:
            try:
                receiver_obj = Receiver.objects.get(id=int(receiver_id), account=request.current_account)
                request.session["last_receiver_id"] = int(receiver_id)
                received_by = receiver_obj.name
            except (ValueError, TypeError, Receiver.DoesNotExist):
                receiver_obj = None

        try:
            applied, last_inst = _apply_payment(
                contract,
                Decimal(str(payment_amount)),
                pay_date,
                payment_method=method,
                receiver=receiver_obj,
                received_by=received_by,
                sender_account=form.cleaned_data.get("transfer_sender_account", ""),
                sender_name=form.cleaned_data.get("transfer_sender_name", ""),
                transfer_image=form.cleaned_data.get("transfer_image"),
                notes=form.cleaned_data.get("notes", ""),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("core:installment_pay", id=installment.id)

        touched_numbers = ", ".join(f"#{i.installment_number}" for i, _ in applied)
        _log_activity(
            request,
            action=ActivityLog.ACTION_PAYMENT,
            model_name="Installment",
            obj=last_inst or installment,
            description=f"تسجيل دفع {payment_amount} جنيه على العقد {contract.contract_number} للعميل {contract.customer.name} — وزّع على الأقساط: {touched_numbers}",
            previous_value={"total_paid": str(contract.total_paid - payment_amount)},
            new_value={"total_paid": str(contract.total_paid)},
        )

        # إقفال تلقائي عند اكتمال قيمة العقد
        if contract.status != Contract.STATUS_EARLY_COMPLETED and contract.total_paid >= contract.total_amount:
            contract.status = Contract.STATUS_COMPLETED
            contract.save(update_fields=["status"])
            messages.success(request, f"🎉 تم سداد كامل قيمة العقد ({contract.total_amount} جنيه) — العقد اتقفل. يمكنك طباعة الإيصال أدناه.")
        else:
            messages.success(request, "تم تسجيل الدفع وتوزيعه على الأقساط. يمكنك طباعة الإيصال أدناه.")
        return redirect("core:installment_receipt", id=(last_inst or installment).id)
    return render(request, "core/installments_pay.html", {
        "form": form,
        "installment": installment,
        "receivers": receivers,
        "last_receiver_id": last_receiver_id,
        "remaining_total": max(contract.total_amount - contract.total_paid, MONEY_ZERO),
    })


def installment_receipt(request, id):
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id, account=request.current_account)
    remaining_balance = _receipt_remaining_balance(installment)
    business_name = _settings().business_name
    
    # الشهر بالعربي
    arabic_months = {
        1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
        7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }
    month_num = installment.due_date.month
    due_month = f"{arabic_months[month_num]} - شهر {month_num}"
    
    is_late = installment.due_date < _today() and installment.status != Installment.STATUS_PAID
    
    # حساب المرحّل (carryover) من الأقساط السابقة
    previous_paid = Decimal("0.00")
    previous_expected = Decimal("0.00")
    prev_installments = installment.contract.installments.filter(
        installment_number__lt=installment.installment_number
    ).order_by("installment_number")
    for prev in prev_installments:
        previous_expected += prev.amount
        previous_paid += prev.paid_amount
    
    carryover = previous_paid - previous_expected
    overpaid = max(installment.paid_amount - installment.amount, Decimal("0"))
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
    return render(request, "core/receipt_detail.html", context)


def _get_whatsapp_url(installment, message_type):
    phone = installment.contract.customer.whatsapp or installment.contract.customer.phone
    phone = "".join(filter(str.isdigit, phone))
    base_url = f"https://wa.me/{phone}?text="
    
    if message_type == "reminder":
        msg = f"مرحباً {installment.contract.customer.name}، نذكركم بقرب موعد استحقاق القسط رقم {installment.installment_number} بقيمة {installment.amount} جنيه في عقد {installment.contract.contract_number} بتاريخ {installment.due_date}."
    elif message_type == "overdue":
        msg = f"مرحباً {installment.contract.customer.name}، نود تذكيركم بأن القسط رقم {installment.installment_number} في عقد {installment.contract.contract_number} قد تجاوز موعد استحقاقه بتاريخ {installment.due_date} بمبلغ {installment.amount} جنيه. برجاء السداد."
    elif message_type == "payment":
        msg = f"مرحباً {installment.contract.customer.name}، تم استلام مبلغ {installment.paid_amount} جنيه كدفعة للقسط رقم {installment.installment_number} في عقد {installment.contract.contract_number}. شكراً لتعاملكم معنا."
    else:
        msg = "مرحباً."
        
    import urllib.parse
    return base_url + urllib.parse.quote(msg)


@require_write
def installment_reset_payment(request, id):
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id, account=request.current_account)
    if request.method == "POST":
        previous_paid = installment.paid_amount
        installment.paid_amount = MONEY_ZERO
        installment.paid_date = None
        installment.payment_method = ""
        installment.status = (
            Installment.STATUS_LATE
            if installment.due_date < _today()
            else Installment.STATUS_PENDING
        )
        installment.save(
            update_fields=["paid_amount", "paid_date", "payment_method", "status"]
        )
        _refresh_contract_status(installment.contract)
        # لو الإلغاء خلّى المدفوع أقل من قيمة العقد → العقد يرجع نشط (مش مكتمل)
        contract = installment.contract
        contract.refresh_from_db()
        if contract.status == Contract.STATUS_COMPLETED and contract.total_paid < contract.total_amount:
            contract.status = Contract.STATUS_ACTIVE
            contract.save(update_fields=["status"])

        # Log reset activity
        _log_activity(
            request,
            action=ActivityLog.ACTION_RESET,
            model_name="Installment",
            obj=installment,
            description=f"إلغاء دفع القسط رقم {installment.installment_number} في العقد {installment.contract.contract_number} للعميل {installment.contract.customer.name}",
            previous_value={"paid_amount": str(previous_paid)},
            new_value={"paid_amount": "0.00"}
        )

        messages.success(request, "تم إلغاء دفع القسط ورجوعه للحالة الصحيحة.")
    return redirect("core:contract_detail", id=installment.contract_id)


@require_write
def installment_edit(request, id):
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id, account=request.current_account)
    if installment.contract.status == Contract.STATUS_EARLY_COMPLETED:
        messages.error(request, "العقد مغلق مبكرًا — لا يمكن تعديل أقساطه.")
        return redirect("core:contract_detail", id=installment.contract_id)
    old_amount, old_due = installment.amount, installment.due_date
    old_paid = installment.paid_amount
    form = InstallmentEditForm(request.POST or None, instance=installment)
    if request.method == "POST" and form.is_valid():
        installment = form.save(commit=False)
        # keep payment-derived status consistent with the new amount
        if installment.paid_amount > installment.amount:
            installment.status = Installment.STATUS_OVERPAID
        elif installment.paid_amount >= installment.amount and installment.paid_amount > 0:
            installment.status = Installment.STATUS_PAID
        elif installment.paid_amount > 0:
            installment.status = Installment.STATUS_PARTIAL
        elif installment.due_date < _today():
            installment.status = Installment.STATUS_LATE
        else:
            installment.status = Installment.STATUS_PENDING
        installment.save(update_fields=["amount", "due_date", "notes", "paid_amount", "status"])
        _refresh_contract_status(installment.contract)
        _maybe_auto_close(installment.contract)

        changes = {}
        if old_amount != installment.amount:
            changes["amount"] = f"{old_amount} → {installment.amount}"
        if old_due != installment.due_date:
            changes["due_date"] = f"{old_due} → {installment.due_date}"
        if old_paid != installment.paid_amount:
            changes["paid_amount"] = f"تصحيح دفعة: {old_paid} → {installment.paid_amount}"
        _log_activity(
            request,
            action=ActivityLog.ACTION_UPDATE,
            model_name="Installment",
            obj=installment,
            description=f"تعديل القسط رقم {installment.installment_number} في العقد {installment.contract.contract_number} للعميل {installment.contract.customer.name}",
            previous_value={"amount": str(old_amount), "due_date": str(old_due), "paid_amount": str(old_paid)},
            new_value={"amount": str(installment.amount), "due_date": str(installment.due_date), "paid_amount": str(installment.paid_amount)},
        )

        messages.success(request, "تم تعديل القسط بنجاح." + (f" ({changes['amount']})" if "amount" in changes else "") + (f" ({changes['paid_amount']})" if "paid_amount" in changes else ""))
        return redirect("core:contract_detail", id=installment.contract_id)
    return render(request, "core/installments_edit.html", {"form": form, "installment": installment})


@require_write
def installment_due_today(request):
    installments = (
        Installment.objects
        .filter(account=request.current_account)
        .select_related("contract", "contract__customer")
        .filter(due_date=_today())
        .exclude(status__in=[Installment.STATUS_PAID, Installment.STATUS_CLOSED])
    )
    return render(request, "core/installments_list.html", {"installments": installments, "title": "أقساط اليوم"})


@require_write
def installment_overdue(request):
    _mark_late_installments()
    installments = Installment.objects.filter(account=request.current_account).select_related("contract", "contract__customer").filter(status=Installment.STATUS_LATE)
    return render(request, "core/installments_list.html", {"installments": installments, "title": "الأقساط المتأخرة"})


def reports_dashboard(request):
    contracts = Contract.objects.filter(account=request.current_account)
    installments = Installment.objects.filter(account=request.current_account)
    expenses = Expense.objects.filter(account=request.current_account)
    return render(request, "core/reports_index.html", {"contracts_count": contracts.count(), "total_invested": _sum(contracts, "actual_cost"), "total_collected": _sum(installments, "paid_amount"), "total_expenses": _sum(expenses, "amount"), "total_profit": sum((_contract_profit(c) for c in contracts), MONEY_ZERO)})


@require_write
def profit_report(request):
    contracts = list(_contract_report_queryset(request.current_account))
    rows = [{"contract": contract, "profit": _contract_profit(contract)} for contract in contracts]
    return render(request, "core/reports_profit.html", {"rows": rows, "total_profit": sum((r["profit"] for r in rows), MONEY_ZERO)})


@require_write
def profit_report_pdf(request):
    contracts = list(_contract_report_queryset(request.current_account))
    rows = [{"contract": contract, "profit": _contract_profit(contract)} for contract in contracts]
    return _pdf_response("core/reports_profit_pdf.html", {"request": request, "rows": rows, "total_profit": sum((r["profit"] for r in rows), MONEY_ZERO)}, "profit-report.pdf")


@require_write
def customer_statement(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    contracts = Contract.objects.filter(customer=customer, account=request.current_account).order_by("-created_at")
    installments = Installment.objects.filter(contract__customer=customer, account=request.current_account).select_related("contract").order_by("due_date")
    return render(request, "core/reports_customer_statement.html", {"customer": customer, "contracts": contracts, "installments": installments, "total_paid": _sum(installments, "paid_amount"), "total_remaining": _remaining_installments_total(installments)})


@require_write
def customer_statement_pdf(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    installments = Installment.objects.filter(contract__customer=customer, account=request.current_account).select_related("contract").order_by("due_date")
    return _pdf_response("core/reports_customer_statement_pdf.html", {"request": request, "customer": customer, "installments": installments, "total_paid": _sum(installments, "paid_amount"), "total_remaining": _remaining_installments_total(installments)}, f"customer-{customer.id}-statement.pdf")


@require_write
def investment_report(request):
    contracts = Contract.objects.filter(account=request.current_account).select_related("customer").order_by("-created_at")
    return render(request, "core/reports_investment.html", {"contracts": contracts, "total_invested": _sum(contracts, "actual_cost"), "total_customer_price": _sum(contracts, "customer_price"), "total_collected": _sum(Installment.objects.filter(account=request.current_account), "paid_amount")})


@require_write
def suppliers_report(request):
    suppliers = Supplier.objects.filter(account=request.current_account).annotate(total_spent=Sum("supplierpurchase__purchase_price", default=MONEY_ZERO)).order_by("-total_spent")
    return render(request, "core/reports_suppliers.html", {"suppliers": suppliers, "total_spent": _sum(SupplierPurchase.objects.filter(account=request.current_account), "purchase_price")})


@require_write
def monthly_report(request):
    payments = (
        Installment.objects.filter(account=request.current_account, paid_date__isnull=False)
        .annotate(month=TruncMonth("paid_date"))
        .values("month")
        .annotate(total_collected=Sum("paid_amount", default=MONEY_ZERO), count=Count("id"))
        .order_by("-month")
    )
    expenses = Expense.objects.filter(account=request.current_account).annotate(month=TruncMonth("expense_date")).values("month").annotate(total_expenses=Sum("amount", default=MONEY_ZERO))
    expense_by_month = {item["month"]: item["total_expenses"] for item in expenses}
    rows = []
    for item in payments:
        total_expenses = expense_by_month.get(item["month"], MONEY_ZERO)
        rows.append({"month": item["month"], "total_collected": item["total_collected"], "total_expenses": total_expenses, "net": item["total_collected"] - total_expenses, "count": item["count"]})
    return render(request, "core/reports_monthly.html", {"rows": rows})


@require_write
def notification_list(request):
    notifications = Notification.objects.filter(account=request.current_account).select_related("contract", "installment").order_by("-created_at")
    return render(request, "core/notifications.html", {"notifications": notifications})


@require_write
def notification_read(request, id):
    notification = get_object_or_404(Notification, id=id, account=request.current_account)
    if request.method == "POST":
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        messages.success(request, "تم تعليم التنبيه كمقروء.")
    return redirect("core:notification_list")


@require_write
def notification_check_due(request):
    if request.method == "POST":
        _mark_late_installments()
        created = 0
        due_installments = (
            Installment.objects
            .filter(account=request.current_account)
            .select_related("contract", "contract__customer")
            .filter(due_date__lte=_today())
            .exclude(status__in=[Installment.STATUS_PAID, Installment.STATUS_CLOSED])
        )
        for installment in due_installments:
            notification_type = Notification.TYPE_OVERDUE if installment.due_date < _today() else Notification.TYPE_REMINDER
            message = f"قسط مستحق للعميل {installment.contract.customer.name} في عقد {installment.contract.contract_number}"
            if not Notification.objects.filter(installment=installment, message=message, account=request.current_account).exists():
                Notification.objects.create(contract=installment.contract, installment=installment, message=message, notification_type=notification_type, account=request.current_account)
                created += 1
        messages.success(request, f"تم إنشاء {created} تنبيه.")
    return redirect("core:notification_list")


@require_write
def search(request):
    query = request.GET.get("q", "").strip()
    customers = []
    contracts = []
    if query:
        customers = Customer.objects.filter(account=request.current_account).filter(Q(name__icontains=query) | Q(phone__icontains=query))
        contracts = Contract.objects.filter(account=request.current_account).filter(
            Q(contract_number__icontains=query)
            | Q(product_name__icontains=query)
            | Q(customer__name__icontains=query)
        ).select_related("customer", "product")
    return render(request, "core/search_results.html", {"customers": customers, "contracts": contracts, "query": query})


@require_write
def expense_list(request):
    expenses = Expense.objects.filter(account=request.current_account).order_by("-expense_date")
    return render(request, "core/expenses_list.html", {"expenses": expenses, "total": _sum(expenses, "amount")})


@require_write
def expense_create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.account = request.current_account
        expense.save()

        # Log create
        _log_activity(
            request,
            action=ActivityLog.ACTION_CREATE,
            model_name="Expense",
            obj=expense,
            description=f"إضافة مصروف جديد: {expense.title} بقيمة {expense.amount} جنيه",
            new_value={"title": expense.title, "amount": str(expense.amount)}
        )

        messages.success(request, "تم حفظ المصروف.")
        return redirect("core:expense_list")
    return render(request, "core/expenses_form.html", {"form": form, "title": "إضافة مصروف"})


@require_write
def expense_edit(request, id):
    expense = get_object_or_404(Expense, id=id, account=request.current_account)
    old_values = {"title": expense.title, "amount": str(expense.amount)}
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        form.save()

        # Log update
        new_values = {"title": expense.title, "amount": str(expense.amount)}
        _log_activity(
            request,
            action=ActivityLog.ACTION_UPDATE,
            model_name="Expense",
            obj=expense,
            description=f"تعديل المصروف: {expense.title}",
            previous_value=old_values,
            new_value=new_values
        )

        messages.success(request, "تم تحديث المصروف.")
        return redirect("core:expense_list")
    return render(request, "core/expenses_form.html", {"form": form, "title": "تعديل مصروف"})


@require_write
def expense_delete(request, id):
    expense = get_object_or_404(Expense, id=id, account=request.current_account)
    if request.method == "POST":
        # Log delete
        _log_activity(
            request,
            action=ActivityLog.ACTION_DELETE,
            model_name="Expense",
            obj=expense,
            description=f"حذف المصروف: {expense.title} بقيمة {expense.amount} جنيه",
            previous_value={"title": expense.title, "amount": str(expense.amount)}
        )
        expense.delete()
        messages.success(request, "تم حذف المصروف.")
    return redirect("core:expense_list")


@require_POST
@require_write
def account_create(request):
    name = request.POST.get("name", "").strip()
    if name:
        account = Account.objects.create(name=name)
        request.session["account_id"] = account.id
        messages.success(request, f"تم إنشاء الحساب: {name}")
    return redirect("core:settings")


def account_switch(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    request.session["account_id"] = account.id
    messages.success(request, f"تم التبديل إلى: {account.name}")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
@require_write
def product_type_create(request):
    name = request.POST.get("name", "").strip()
    if name:
        ProductType.objects.get_or_create(name=name, account=request.current_account)
        messages.success(request, f"تم إضافة النوع: {name}")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
@require_write
def product_type_delete(request, id):
    pt = get_object_or_404(ProductType, id=id, account=request.current_account)
    name = pt.name
    pt.delete()
    messages.success(request, f"تم حذف النوع: {name}")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_write
def settings_view(request):
    instance = _settings()
    form = SettingsForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم حفظ الإعدادات.")
        return redirect("core:settings")
    from .backup_utils import list_backups

    backups = list_backups() if request.user.is_staff else []
    product_types = ProductType.objects.filter(account=request.current_account).order_by("name")
    return render(request, "core/settings.html", {"form": form, "backups": backups, "product_types": product_types})


@require_write
def collected_installments(request):
    """List installments actually paid this month, with date/tag filters."""
    from django.db.models import Sum
    today = _today()
    qs = (
        Installment.objects
        .filter(account=request.current_account, paid_date__isnull=False)
        .exclude(paid_amount=0)
        .filter(paid_date__year=today.year, paid_date__month=today.month)
        .select_related("contract", "contract__customer", "contract__product")
        .order_by("-paid_date", "-id")
    )

    tag = request.GET.get("tag", "")
    if tag == "late":
        # paid this month but was due in an earlier month
        qs = qs.exclude(due_date__year=today.year, due_date__month=today.month)
    elif tag == "ontime":
        qs = qs.filter(due_date__year=today.year, due_date__month=today.month)

    date_from = request.GET.get("from", "").strip()
    date_to = request.GET.get("to", "").strip()
    if date_from:
        qs = qs.filter(paid_date__gte=date_from)
    if date_to:
        qs = qs.filter(paid_date__lte=date_to)

    total = qs.aggregate(total=Sum("paid_amount", default=MONEY_ZERO))["total"]

    # goal: total amount of installments DUE this month (what should be collected)
    goal_qs = Installment.objects.filter(
        account=request.current_account,
        due_date__year=today.year, due_date__month=today.month,
    )
    goal_total = goal_qs.aggregate(total=Sum("amount", default=MONEY_ZERO))["total"]
    collected_of_goal = goal_qs.aggregate(total=Sum("paid_amount", default=MONEY_ZERO))["total"]

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    querystring = ""
    if tag:
        querystring += f"tag={tag}&"
    if date_from:
        querystring += f"from={date_from}&"
    if date_to:
        querystring += f"to={date_to}&"

    return render(request, "core/collected_installments.html", {
        "installments": page,
        "total": total,
        "tag": tag,
        "date_from": date_from,
        "date_to": date_to,
        "querystring": querystring,
        "current_year": today.year,
        "current_month": today.month,
        "goal_total": goal_total,
        "collected_of_goal": collected_of_goal,
    })


def monthly_income_edit(request, id):
    """Update expected monthly income and/or the collected amount override (Task 1)."""
    from django.utils import timezone
    today = timezone.now().date()
    income = get_object_or_404(MonthlyIncome, id=id, account=request.current_account)

    expected_raw = request.POST.get("expected_monthly_income")
    override_raw = request.POST.get("collected_amount_override")
    reset_override = request.POST.get("reset_override") == "1"

    try:
        if expected_raw is not None and expected_raw.strip() != "":
            income.expected_monthly_income = Decimal(expected_raw)
        if reset_override:
            income.collected_amount_override = None
        elif override_raw is not None and override_raw.strip() != "":
            income.collected_amount_override = Decimal(override_raw)
    except Exception:
        messages.error(request, "القيمة المدخلة غير صحيحة.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    income.save()
    messages.success(request, "تم تحديث الدخل الشهري.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


def _overdue_report_context(account, query_params):
    """Build the filtered overdue rows shared by report and editable export views."""
    today = _today()
    qs = (
        Installment.objects
        .filter(account=account, status=Installment.STATUS_LATE)
        .select_related("contract", "contract__customer")
    )

    min_days = query_params.get("min_days_overdue")
    date_from = query_params.get("date_from")
    date_to = query_params.get("date_to")
    customer_id = query_params.get("customer")
    sort = query_params.get("sort", "-total_amount")

    if min_days:
        try:
            cutoff = today - timedelta(days=int(min_days))
            qs = qs.filter(due_date__lte=cutoff)
        except ValueError:
            pass
    if date_from:
        qs = qs.filter(due_date__gte=date_from)
    if date_to:
        qs = qs.filter(due_date__lte=date_to)
    if customer_id:
        qs = qs.filter(contract__customer_id=customer_id)

    customers_map = {}
    for inst in qs:
        cid = inst.contract.customer_id
        cname = inst.contract.customer.name
        due_day = inst.contract.payment_due_day
        if cid not in customers_map:
            customers_map[cid] = {
                "customer_id": cid,
                "customer_name": cname,
                "due_day": due_day,
                "installments": [],
                "total_amount": MONEY_ZERO,
                "max_days_overdue": 0,
                "count": 0,
            }
        row = customers_map[cid]
        row["installments"].append({
            "id": inst.id,
            "amount": inst.amount,
            "paid_amount": inst.paid_amount,
            "due_date": inst.due_date,
            "days_overdue": (today - inst.due_date).days,
            "contract_number": inst.contract.contract_number,
        })
        row["total_amount"] += inst.amount - inst.paid_amount
        row["count"] += 1
        row["max_days_overdue"] = max(row["max_days_overdue"], (today - inst.due_date).days)

    rows = list(customers_map.values())

    if sort == "-max_days_overdue":
        rows.sort(key=lambda r: r["max_days_overdue"], reverse=True)
    elif sort == "total_amount":
        rows.sort(key=lambda r: r["total_amount"])
    elif sort == "-total_amount":
        rows.sort(key=lambda r: r["total_amount"], reverse=True)
    else:
        rows.sort(key=lambda r: r["max_days_overdue"], reverse=True)

    grand_total = sum((r["total_amount"] for r in rows), MONEY_ZERO)
    total_installments = sum(r["count"] for r in rows)
    customers = Customer.objects.filter(account=account).order_by("name")

    return {
        "rows": rows,
        "grand_total": grand_total,
        "total_installments": total_installments,
        "customers": customers,
        "filters": {
            "min_days_overdue": min_days or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
            "customer": customer_id or "",
            "sort": sort,
        },
        "today": today,
    }


@require_write
def overdue_report(request):
    """Filterable overdue installments report (Task 2)."""
    _mark_late_installments()
    return render(
        request,
        "core/reports_overdue.html",
        _overdue_report_context(request.current_account, request.GET),
    )


@require_write
def overdue_export_edit(request):
    """Editable, display-only overdue sheet for customer-facing export/print."""
    _mark_late_installments()
    return render(
        request,
        "core/reports_overdue_export_edit.html",
        _overdue_report_context(request.current_account, request.GET),
    )


@require_write
def backup_create_view(request):
    if request.method == "POST":
        from .backup_utils import create_backup

        try:
            name = create_backup()
            messages.success(request, f"تم إنشاء النسخة الاحتياطية: {name}")
        except Exception as exc:
            messages.error(request, f"خطأ في إنشاء النسخة الاحتياطية: {exc}")
    return redirect("core:settings")


def backup_download_view(request, filename):
    from .backup_utils import _backup_dir
    from django.http import FileResponse, Http404

    filepath = _backup_dir() / filename
    if not filepath.exists() or not filepath.name.startswith("db_backup_") or not filepath.name.endswith(".sqlite3"):
        raise Http404
    return FileResponse(open(filepath, "rb"), as_attachment=True, filename=filename)


@require_write
def backup_delete_view(request, filename):
    if request.method == "POST":
        from .backup_utils import delete_backup

        if delete_backup(filename):
            messages.success(request, f"تم حذف النسخة الاحتياطية: {filename}")
        else:
            messages.error(request, "لم يتم العثور على النسخة الاحتياطية.")
    return redirect("core:settings")


@require_write
def backup_restore_view(request, filename):
    if request.method == "POST":
        from .backup_utils import restore_backup

        if restore_backup(filename):
            messages.success(request, f"تم استعادة النسخة الاحتياطية: {filename}")
        else:
            messages.error(request, "لم يتم العثور على النسخة الاحتياطية.")
    return redirect("core:settings")


def _log_activity(
    request,
    *,
    action,
    model_name,
    description,
    obj=None,
    previous_value=None,
    new_value=None,
):
    user_repr = request.user.username if request.user.is_authenticated else ""
    object_id = obj.pk if obj is not None and hasattr(obj, "pk") else None
    object_repr = str(obj) if obj is not None else ""
    try:
        ActivityLog.objects.create(
            user=user_repr,
            action=action,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr[:255],
            description=description,
            previous_value=previous_value,
            new_value=new_value,
            account=request.current_account,
        )
    except Exception:
        pass


@require_write
def activity_log_list(request):
    logs = ActivityLog.objects.filter(account=request.current_account)[:500]
    action_filter = request.GET.get("action", "")
    if action_filter:
        logs = ActivityLog.objects.filter(account=request.current_account, action=action_filter)[:500]
    counts = ActivityLog.objects.filter(account=request.current_account).values("action").annotate(count=Count("id"))
    counts_map = {item["action"]: item["count"] for item in counts}
    context = {
        "logs": logs,
        "action_filter": action_filter,
        "total_logs": ActivityLog.objects.filter(account=request.current_account).count(),
        "count_create": counts_map.get(ActivityLog.ACTION_CREATE, 0),
        "count_update": counts_map.get(ActivityLog.ACTION_UPDATE, 0),
        "count_delete": counts_map.get(ActivityLog.ACTION_DELETE, 0),
        "count_payment": counts_map.get(ActivityLog.ACTION_PAYMENT, 0),
        "count_reset": counts_map.get(ActivityLog.ACTION_RESET, 0),
    }
    return render(request, "core/activity_log.html", context)


@require_write
def receiver_list(request):
    receivers = Receiver.objects.filter(
        account=request.current_account
    ).annotate(
        total_received=Sum("installments__paid_amount"),
        payment_count=Count("installments"),
    ).order_by("-total_received")
    return render(request, "core/receivers/receiver_list.html", {"receivers": receivers})


@require_write
def receiver_detail(request, pk):
    receiver = get_object_or_404(Receiver, pk=pk, account=request.current_account)
    installments = receiver.installments.select_related(
        "contract", "contract__customer"
    ).order_by("-paid_date", "-due_date")
    total = installments.aggregate(t=Sum("paid_amount"))["t"] or 0
    return render(request, "core/receivers/receiver_detail.html", {
        "receiver": receiver,
        "installments": installments,
        "total": total,
    })


@require_write
def receiver_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            Receiver.objects.get_or_create(
                account=request.current_account,
                name=name,
            )
            messages.success(request, f"تم إضافة المستلم {name}")
        else:
            messages.error(request, "يرجى إدخال اسم المستلم")
    return redirect("core:receiver_list")



