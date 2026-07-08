import calendar
import json
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
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
    Notification,
    Product,
    ProductType,
    Settings,
    Supplier,
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
    return (
        queryset.exclude(status=Installment.STATUS_PAID)
        .aggregate(total=Sum(F("amount") - F("paid_amount"), default=MONEY_ZERO))["total"]
        or MONEY_ZERO
    )


def _settings():
    settings, _created = Settings.objects.get_or_create(pk=1)
    return settings


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
    new_product_image = forms.ImageField(
        label="صورة المنتج أو السيريال أو فاتورة الشراء",
        required=False,
    )

    class Meta:
        model = Supplier
        fields = ["name", "phone", "address", "category", "notes"]
        labels = {
            "name": "اسم التاجر",
            "phone": "رقم الهاتف",
            "address": "العنوان",
            "category": "الفئة",
            "notes": "ملاحظات",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


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
            if not cleaned_data.get("received_by"):
                self.add_error("received_by", "يجب إدخال اسم المستلم.")
        
        return cleaned_data

    def clean_paid_amount(self):
        paid_amount = self.cleaned_data["paid_amount"]
        if paid_amount <= 0:
            raise forms.ValidationError("مبلغ الدفعة يجب أن يكون أكبر من صفر.")
        return paid_amount


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

    # --- Customer: lookup by name, create if new ---
    if customer_name:
        customer = Customer.objects.filter(name__iexact=customer_name).order_by("id").first()
        if not customer:
            customer = Customer.objects.create(name=customer_name, phone="", account=contract.account)
        contract.customer = customer

    # --- Supplier: lookup by name, create if new ---
    if supplier_name:
        supplier = Supplier.objects.filter(name__iexact=supplier_name).order_by("id").first()
        if not supplier:
            supplier = Supplier.objects.create(name=supplier_name, phone="", account=contract.account)
        contract.supplier = supplier

    # --- Product: lookup by name, create if new ---
    if product_name:
        product = Product.objects.filter(name__iexact=product_name).order_by("id").first()
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
    )
    late_contract_ids = list(late_qs.values_list("contract_id", flat=True).distinct())
    late_qs.update(status=Installment.STATUS_LATE)
    Contract.objects.filter(id__in=late_contract_ids, status=Contract.STATUS_ACTIVE).update(
        status=Contract.STATUS_OVERDUE,
    )


def _refresh_contract_status(contract):
    installments = contract.installments.all()
    if installments.exists() and not installments.exclude(status=Installment.STATUS_PAID).exists():
        contract.status = Contract.STATUS_COMPLETED
    elif installments.filter(due_date__lt=_today()).exclude(status=Installment.STATUS_PAID).exists():
        contract.status = Contract.STATUS_OVERDUE
    elif contract.status != Contract.STATUS_CANCELLED:
        contract.status = Contract.STATUS_ACTIVE
    contract.save(update_fields=["status"])


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


def dashboard(request):
    _mark_late_installments()
    today = _today()
    contracts = Contract.objects.filter(account=request.current_account)
    installments = Installment.objects.select_related("contract", "contract__customer").filter(account=request.current_account)
    
    # أقساط اليوم
    due_today = installments.filter(due_date=today).exclude(status=Installment.STATUS_PAID)
    for inst in due_today:
        inst.whatsapp_url = _get_whatsapp_url(inst, "reminder")
    
    # المتأخرات
    overdue_installments = installments.filter(status=Installment.STATUS_LATE)
    for inst in overdue_installments:
        inst.whatsapp_url = _get_whatsapp_url(inst, "overdue")
    
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

    status_qs = contracts.values("status").annotate(count=Count("id"))

    context = {
        "due_today": due_today,
        "overdue_installments": overdue_installments,
        "total_expected_today": total_expected_today,
        "income_this_month": income_this_month,
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
        "overdue_count": overdue_installments.count(),
        "total_invested": _sum(contracts, "actual_cost"),
        "total_collected": _sum(installments, "paid_amount"),
        "total_profit": total_profit,
        "total_customers": Customer.objects.filter(account=request.current_account).count(),
        "total_contracts": contracts.count(),
        "recent_contracts": contracts.select_related("customer").order_by("-created_at")[:5],
        "recent_payments": installments.filter(status=Installment.STATUS_PAID).order_by("-paid_date")[:5],
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
    customers = Customer.objects.filter(account=request.current_account).annotate(contracts_count=Count("contract")).order_by("-created_at")
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    return render(request, "core/customers_list.html", {"customers": customers, "query": query})


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
    contracts = Contract.objects.filter(customer=customer, account=request.current_account).order_by("-created_at")
    installments = Installment.objects.filter(contract__customer=customer, account=request.current_account).select_related("contract").order_by("due_date")
    
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
        "total_paid": total_paid,
        "total_due": total_due,
        "contracts_count": contracts.count(),
        "late_installments_count": installments.filter(status=Installment.STATUS_LATE).count(),
        "commitment": commitment,
    }
    return render(request, "core/customers_detail.html", context)


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


def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save(commit=False)
        supplier.account = request.current_account
        supplier.save()
        messages.success(request, "تم حفظ التاجر.")
        return redirect("core:supplier_detail", id=supplier.id)
    return render(request, "core/suppliers_form.html", {"form": form, "title": "إضافة تاجر"})


def supplier_detail(request, id):
    supplier = get_object_or_404(Supplier, id=id, account=request.current_account)
    purchases = SupplierPurchase.objects.filter(supplier=supplier, account=request.current_account).select_related("product").order_by("-purchase_date")
    return render(
        request,
        "core/suppliers_detail.html",
        {"supplier": supplier, "purchases": purchases, "total_spent": _sum(purchases, "purchase_price")},
    )


def supplier_edit(request, id):
    supplier = get_object_or_404(Supplier, id=id, account=request.current_account)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث التاجر.")
        return redirect("core:supplier_detail", id=supplier.id)
    return render(request, "core/suppliers_form.html", {"form": form, "title": "تعديل تاجر"})


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


def product_edit(request, id):
    product = get_object_or_404(Product, id=id, account=request.current_account)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث المنتج.")
        return redirect("core:product_detail", id=product.id)
    return render(request, "core/products_form.html", {"form": form, "title": "تعديل منتج"})


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
    return render(request, "core/contracts_list.html", {"contracts": contracts, "customers": Customer.objects.filter(account=request.current_account).order_by("name"), "status": status, "customer_id": customer_id})


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
    
    # إضافة روابط الواتساب للأقساط
    for inst in installments:
        inst.whatsapp_reminder = _get_whatsapp_url(inst, "reminder")
        inst.whatsapp_overdue = _get_whatsapp_url(inst, "overdue")
        inst.whatsapp_payment = _get_whatsapp_url(inst, "payment")
    
    # حساب التقدم
    total_paid = _sum(installments, "paid_amount")
    paid_count = installments.filter(status=Installment.STATUS_PAID).count()
    total_count = installments.count()
    progress = 0
    if total_count > 0:
        progress = int((paid_count / total_count) * 100)
        
    return render(request, "core/contracts_detail.html", {
        "contract": contract,
        "installments": installments,
        "profit": _contract_profit(contract),
        "total_paid": total_paid,
        "paid_count": paid_count,
        "total_count": total_count,
        "progress": progress,
    })


def contract_summary(request, id):
    contract = get_object_or_404(Contract.objects.select_related("customer", "product"), id=id, account=request.current_account)
    installments = contract.installments.order_by("installment_number")
    total_paid = _sum(installments, "paid_amount")
    
    # حساب التقدم
    paid_count = installments.filter(status=Installment.STATUS_PAID).count()
    total_count = installments.count()
    progress = 0
    if total_count > 0:
        progress = int((paid_count / total_count) * 100)
    
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
    schedule_rows = []
    carried = Decimal("0.00")
    for inst in installments:
        expected = inst.amount + carried
        paid_now = inst.paid_amount
        carried = expected - paid_now
        if carried < 0:
            carried = Decimal("0.00")
        schedule_rows.append({
            "inst": inst,
            "expected": expected,
            "carried": carried if inst.status == Installment.STATUS_PENDING else Decimal("0.00"),
        })
    
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
    }
    return render(request, "core/contract_summary.html", context)


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


def contract_mark_completed(request, id):
    contract = get_object_or_404(Contract, id=id, account=request.current_account)
    if request.method == "POST":
        old_status = contract.status
        contract.status = Contract.STATUS_COMPLETED
        contract.save(update_fields=["status"])
        contract.installments.exclude(status=Installment.STATUS_PAID).update(
            paid_amount=F("amount"),
            paid_date=_today(),
            status=Installment.STATUS_PAID,
        )

        # Log completion
        _log_activity(
            request,
            action=ActivityLog.ACTION_MARK_COMPLETED,
            model_name="Contract",
            obj=contract,
            description=f"تعليم العقد رقم {contract.contract_number} للعميل {contract.customer.name} كمكتمل وتسوية جميع الأقساط المتبقية",
            previous_value={"status": old_status},
            new_value={"status": Contract.STATUS_COMPLETED}
        )

        messages.success(request, "تم تعليم العقد كمكتمل.")
    return redirect("core:contract_detail", id=contract.id)


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
    return render(request, "core/installments_list.html", {"installments": installments, "status": status, "date_from": date_from, "date_to": date_to})


def installment_pay(request, id):
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id, account=request.current_account)
    previous_paid = installment.paid_amount
    initial = {"paid_amount": installment.amount - installment.paid_amount, "paid_date": _today(), "payment_method": Installment.PAYMENT_CASH}
    form = InstallmentPaymentForm(request.POST or None, instance=installment, initial=initial)
    if request.method == "POST" and form.is_valid():
        payment_amount = form.cleaned_data["paid_amount"]
        installment = form.save(commit=False)
        installment.paid_amount = previous_paid + payment_amount
        excess_pay = Decimal("0")
        if installment.paid_amount >= installment.amount:
            installment.status = Installment.STATUS_PAID
            excess_pay = installment.paid_amount - installment.amount
            if excess_pay > 0:
                next_installments = Installment.objects.filter(
                    contract=installment.contract,
                    installment_number__gt=installment.installment_number,
                    account=request.current_account,
                ).order_by("installment_number")
                for nx in next_installments:
                    available = nx.amount - nx.paid_amount
                    if available <= 0:
                        continue
                    if excess_pay >= available:
                        excess_pay -= available
                        nx.paid_amount = nx.amount
                        nx.status = Installment.STATUS_PAID
                        nx.save(update_fields=["paid_amount", "status"])
                    else:
                        nx.paid_amount += excess_pay
                        if nx.paid_amount >= nx.amount:
                            nx.status = Installment.STATUS_PAID
                        else:
                            nx.status = Installment.STATUS_PARTIAL
                        nx.save(update_fields=["paid_amount", "status"])
                        excess_pay = Decimal("0")
                        break
                if excess_pay > 0:
                    messages.info(request, f"تم ترحيل {excess_pay} جنيه كرصيد للأقساط القادمة.")
        elif installment.paid_amount > 0:
            installment.status = Installment.STATUS_PARTIAL
        else:
            installment.status = Installment.STATUS_PENDING
        installment.save()
        if not installment.contract.installments.exclude(status=Installment.STATUS_PAID).exists():
            installment.contract.status = Contract.STATUS_COMPLETED
            installment.contract.save(update_fields=["status"])
        
        _log_activity(
            request,
            action=ActivityLog.ACTION_PAYMENT,
            model_name="Installment",
            obj=installment,
            description=f"تسجيل دفع مبلغ {payment_amount} جنيه للقسط رقم {installment.installment_number} في العقد {installment.contract.contract_number} للعميل {installment.contract.customer.name}",
            previous_value={"paid_amount": str(previous_paid)},
            new_value={"paid_amount": str(installment.paid_amount)}
        )

        messages.success(request, "تم تسجيل الدفع. يمكنك طباعة الإيصال أدناه.")
        return redirect("core:installment_receipt", id=installment.id)
    return render(request, "core/installments_pay.html", {"form": form, "installment": installment})


def installment_receipt(request, id):
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id, account=request.current_account)
    remaining_balance = _remaining_installments_total(installment.contract.installments.all())
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
    
    context = {
        "installment": installment,
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


def installment_due_today(request):
    installments = Installment.objects.filter(account=request.current_account).select_related("contract", "contract__customer").filter(due_date=_today()).exclude(status=Installment.STATUS_PAID)
    return render(request, "core/installments_list.html", {"installments": installments, "title": "أقساط اليوم"})


def installment_overdue(request):
    _mark_late_installments()
    installments = Installment.objects.filter(account=request.current_account).select_related("contract", "contract__customer").filter(status=Installment.STATUS_LATE)
    return render(request, "core/installments_list.html", {"installments": installments, "title": "الأقساط المتأخرة"})


def reports_dashboard(request):
    contracts = Contract.objects.filter(account=request.current_account)
    installments = Installment.objects.filter(account=request.current_account)
    expenses = Expense.objects.filter(account=request.current_account)
    return render(request, "core/reports_index.html", {"contracts_count": contracts.count(), "total_invested": _sum(contracts, "actual_cost"), "total_collected": _sum(installments, "paid_amount"), "total_expenses": _sum(expenses, "amount"), "total_profit": sum((_contract_profit(c) for c in contracts), MONEY_ZERO)})


def profit_report(request):
    contracts = list(_contract_report_queryset(request.current_account))
    rows = [{"contract": contract, "profit": _contract_profit(contract)} for contract in contracts]
    return render(request, "core/reports_profit.html", {"rows": rows, "total_profit": sum((r["profit"] for r in rows), MONEY_ZERO)})


def profit_report_pdf(request):
    contracts = list(_contract_report_queryset(request.current_account))
    rows = [{"contract": contract, "profit": _contract_profit(contract)} for contract in contracts]
    return _pdf_response("core/reports_profit_pdf.html", {"request": request, "rows": rows, "total_profit": sum((r["profit"] for r in rows), MONEY_ZERO)}, "profit-report.pdf")


def customer_statement(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    contracts = Contract.objects.filter(customer=customer, account=request.current_account).order_by("-created_at")
    installments = Installment.objects.filter(contract__customer=customer, account=request.current_account).select_related("contract").order_by("due_date")
    return render(request, "core/reports_customer_statement.html", {"customer": customer, "contracts": contracts, "installments": installments, "total_paid": _sum(installments, "paid_amount"), "total_remaining": _remaining_installments_total(installments)})


def customer_statement_pdf(request, id):
    customer = get_object_or_404(Customer, id=id, account=request.current_account)
    installments = Installment.objects.filter(contract__customer=customer, account=request.current_account).select_related("contract").order_by("due_date")
    return _pdf_response("core/reports_customer_statement_pdf.html", {"request": request, "customer": customer, "installments": installments, "total_paid": _sum(installments, "paid_amount"), "total_remaining": _remaining_installments_total(installments)}, f"customer-{customer.id}-statement.pdf")


def investment_report(request):
    contracts = Contract.objects.filter(account=request.current_account).select_related("customer").order_by("-created_at")
    return render(request, "core/reports_investment.html", {"contracts": contracts, "total_invested": _sum(contracts, "actual_cost"), "total_customer_price": _sum(contracts, "customer_price"), "total_collected": _sum(Installment.objects.filter(account=request.current_account), "paid_amount")})


def suppliers_report(request):
    suppliers = Supplier.objects.filter(account=request.current_account).annotate(total_spent=Sum("supplierpurchase__purchase_price", default=MONEY_ZERO)).order_by("-total_spent")
    return render(request, "core/reports_suppliers.html", {"suppliers": suppliers, "total_spent": _sum(SupplierPurchase.objects.filter(account=request.current_account), "purchase_price")})


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


def notification_list(request):
    notifications = Notification.objects.filter(account=request.current_account).select_related("contract", "installment").order_by("-created_at")
    return render(request, "core/notifications.html", {"notifications": notifications})


def notification_read(request, id):
    notification = get_object_or_404(Notification, id=id, account=request.current_account)
    if request.method == "POST":
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        messages.success(request, "تم تعليم التنبيه كمقروء.")
    return redirect("core:notification_list")


def notification_check_due(request):
    if request.method == "POST":
        _mark_late_installments()
        created = 0
        due_installments = Installment.objects.filter(account=request.current_account).select_related("contract", "contract__customer").filter(due_date__lte=_today()).exclude(status=Installment.STATUS_PAID)
        for installment in due_installments:
            notification_type = Notification.TYPE_OVERDUE if installment.due_date < _today() else Notification.TYPE_REMINDER
            message = f"قسط مستحق للعميل {installment.contract.customer.name} في عقد {installment.contract.contract_number}"
            if not Notification.objects.filter(installment=installment, message=message, account=request.current_account).exists():
                Notification.objects.create(contract=installment.contract, installment=installment, message=message, notification_type=notification_type, account=request.current_account)
                created += 1
        messages.success(request, f"تم إنشاء {created} تنبيه.")
    return redirect("core:notification_list")


def search(request):
    query = request.GET.get("q", "").strip()
    customers = []
    contracts = []
    if query:
        customers = Customer.objects.filter(account=request.current_account).filter(Q(name__icontains=query) | Q(phone__icontains=query))
        contracts = Contract.objects.filter(account=request.current_account).filter(Q(contract_number__icontains=query) | Q(product_name__icontains=query))
    return render(request, "core/search_results.html", {"customers": customers, "contracts": contracts, "query": query})


def expense_list(request):
    expenses = Expense.objects.filter(account=request.current_account).order_by("-expense_date")
    return render(request, "core/expenses_list.html", {"expenses": expenses, "total": _sum(expenses, "amount")})


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
def product_type_create(request):
    name = request.POST.get("name", "").strip()
    if name:
        ProductType.objects.get_or_create(name=name, account=request.current_account)
        messages.success(request, f"تم إضافة النوع: {name}")
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def product_type_delete(request, id):
    pt = get_object_or_404(ProductType, id=id, account=request.current_account)
    name = pt.name
    pt.delete()
    messages.success(request, f"تم حذف النوع: {name}")
    return redirect(request.META.get("HTTP_REFERER", "/"))


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


def backup_delete_view(request, filename):
    if request.method == "POST":
        from .backup_utils import delete_backup

        if delete_backup(filename):
            messages.success(request, f"تم حذف النسخة الاحتياطية: {filename}")
        else:
            messages.error(request, "لم يتم العثور على النسخة الاحتياطية.")
    return redirect("core:settings")


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



