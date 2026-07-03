import calendar
import json
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .calculations import calculate_mode_a, calculate_mode_b, calculate_mode_c
from .models import (
    Contract,
    Customer,
    Expense,
    Installment,
    Notification,
    Product,
    Settings,
    Supplier,
    SupplierPurchase,
)


MONEY_ZERO = Decimal("0.00")


def _sum(queryset, field):
    return queryset.aggregate(total=Sum(field, default=MONEY_ZERO))["total"] or MONEY_ZERO


def _settings():
    return Settings.objects.first() or Settings.objects.create()


def _today():
    return timezone.localdate()


def _add_months(source_date, months, due_day):
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return source_date.replace(year=year, month=month, day=min(int(due_day), last_day))


def _apply_bootstrap(form):
    for field in form.fields.values():
        current = field.widget.attrs.get("class", "")
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = (current + " form-check-input").strip()
        elif isinstance(field.widget, forms.Select):
            field.widget.attrs["class"] = (current + " form-select").strip()
        else:
            field.widget.attrs["class"] = (current + " form-control").strip()
    return form


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap(self)


class CustomerForm(BootstrapModelForm):
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
    class Meta:
        model = Product
        fields = ["name", "brand", "category", "estimated_price", "image"]
        labels = {
            "name": "اسم المنتج",
            "brand": "الماركة",
            "category": "الفئة",
            "estimated_price": "السعر التقديري",
            "image": "الصورة",
        }


class SupplierPurchaseForm(BootstrapModelForm):
    class Meta:
        model = SupplierPurchase
        fields = [
            "supplier",
            "product",
            "product_name",
            "purchase_price",
            "purchase_date",
            "image",
            "notes",
        ]
        labels = {
            "supplier": "التاجر",
            "product": "منتج مسجل",
            "product_name": "اسم المنتج",
            "purchase_price": "سعر الشراء",
            "purchase_date": "تاريخ الشراء",
            "image": "الصورة",
            "notes": "ملاحظات",
        }
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ContractForm(BootstrapModelForm):
    class Meta:
        model = Contract
        fields = [
            "customer",
            "product",
            "product_name",
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
            "customer": "العميل",
            "product": "منتج مسجل",
            "product_name": "اسم المنتج",
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


class InstallmentPaymentForm(BootstrapModelForm):
    class Meta:
        model = Installment
        fields = ["paid_amount", "paid_date", "payment_method", "notes"]
        labels = {
            "paid_amount": "مبلغ الدفعة",
            "paid_date": "تاريخ الدفع",
            "payment_method": "طريقة الدفع",
            "notes": "ملاحظات",
        }
        widgets = {
            "paid_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].choices = [
            ("cash", "نقدي"),
            ("wallet", "محفظة"),
            ("instapay", "إنستاباي"),
        ]


class ExpenseForm(BootstrapModelForm):
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
        return calculate_mode_a(remaining, data.get("installment_amount") or 0, months_count)
    if mode == "C":
        return calculate_mode_c(remaining, months_count, _settings().default_interest_rate)
    return calculate_mode_b(remaining, data.get("interest_rate") or 0, months_count)


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
            )
        )
    Installment.objects.bulk_create(installments)


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


def _contract_profit(contract):
    return (contract.customer_price - contract.actual_cost) + contract.total_interest


def _contract_report_queryset():
    return (
        Contract.objects.select_related("customer", "product")
        .annotate(collected=Sum("installments__paid_amount", default=MONEY_ZERO))
        .order_by("-created_at")
    )


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
    contracts = Contract.objects.all()
    installments = Installment.objects.select_related("contract", "contract__customer")
    monthly = (
        installments.filter(paid_date__isnull=False)
        .annotate(month=TruncMonth("paid_date"))
        .values("month")
        .annotate(total=Sum("paid_amount", default=MONEY_ZERO))
        .order_by("month")
    )
    context = {
        "active_contracts": contracts.filter(status=Contract.STATUS_ACTIVE).count(),
        "due_today_count": installments.filter(due_date=_today()).exclude(status=Installment.STATUS_PAID).count(),
        "overdue_count": installments.filter(status=Installment.STATUS_LATE).count(),
        "total_invested": _sum(contracts, "actual_cost"),
        "total_collected": _sum(installments, "paid_amount"),
        "total_profit": sum((_contract_profit(c) for c in contracts), MONEY_ZERO),
        "recent_contracts": contracts.select_related("customer").order_by("-created_at")[:5],
        "recent_payments": installments.filter(status=Installment.STATUS_PAID).order_by("-paid_date")[:5],
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
    customers = Customer.objects.annotate(contracts_count=Count("contract")).order_by("-created_at")
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    return render(request, "core/customers_list.html", {"customers": customers, "query": query})


def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        messages.success(request, "تم حفظ العميل.")
        return redirect("core:customer_detail", id=customer.id)
    return render(request, "core/customers_form.html", {"form": form, "title": "إضافة عميل"})


def customer_detail(request, id):
    customer = get_object_or_404(Customer, id=id)
    contracts = Contract.objects.filter(customer=customer).order_by("-created_at")
    installments = Installment.objects.filter(contract__customer=customer).select_related("contract").order_by("due_date")
    context = {
        "customer": customer,
        "contracts": contracts,
        "installments": installments,
        "total_paid": _sum(installments, "paid_amount"),
        "total_due": _sum(installments.exclude(status=Installment.STATUS_PAID), "amount"),
    }
    return render(request, "core/customers_detail.html", context)


def customer_edit(request, id):
    customer = get_object_or_404(Customer, id=id)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث العميل.")
        return redirect("core:customer_detail", id=customer.id)
    return render(request, "core/customers_form.html", {"form": form, "title": "تعديل عميل"})


def supplier_list(request):
    query = request.GET.get("q", "").strip()
    suppliers = Supplier.objects.select_related("category").order_by("-created_at")
    if query:
        suppliers = suppliers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    return render(request, "core/suppliers_list.html", {"suppliers": suppliers, "query": query})


def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, "تم حفظ التاجر.")
        return redirect("core:supplier_detail", id=supplier.id)
    return render(request, "core/suppliers_form.html", {"form": form, "title": "إضافة تاجر"})


def supplier_detail(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    purchases = SupplierPurchase.objects.filter(supplier=supplier).select_related("product").order_by("-purchase_date")
    return render(
        request,
        "core/suppliers_detail.html",
        {"supplier": supplier, "purchases": purchases, "total_spent": _sum(purchases, "purchase_price")},
    )


def supplier_edit(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث التاجر.")
        return redirect("core:supplier_detail", id=supplier.id)
    return render(request, "core/suppliers_form.html", {"form": form, "title": "تعديل تاجر"})


def product_list(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category").order_by("-created_at")
    if query:
        products = products.filter(Q(name__icontains=query) | Q(brand__icontains=query))
    return render(request, "core/products_list.html", {"products": products, "query": query})


def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, "تم حفظ المنتج.")
        return redirect("core:product_detail", id=product.id)
    return render(request, "core/products_form.html", {"form": form, "title": "إضافة منتج"})


def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    contracts = Contract.objects.filter(product=product).select_related("customer").order_by("-created_at")
    purchases = SupplierPurchase.objects.filter(product=product).select_related("supplier").order_by("-purchase_date")
    return render(request, "core/products_detail.html", {"product": product, "contracts": contracts, "purchases": purchases})


def purchase_list(request):
    purchases = SupplierPurchase.objects.select_related("supplier", "product").order_by("-purchase_date")
    return render(request, "core/purchases_list.html", {"purchases": purchases, "total": _sum(purchases, "purchase_price")})


def purchase_create(request):
    form = SupplierPurchaseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم حفظ عملية الشراء.")
        return redirect("core:purchase_list")
    return render(request, "core/purchases_form.html", {"form": form, "title": "إضافة شراء"})


def contract_list(request):
    _mark_late_installments()
    status = request.GET.get("status", "")
    customer_id = request.GET.get("customer", "")
    contracts = Contract.objects.select_related("customer", "product").order_by("-created_at")
    if status:
        contracts = contracts.filter(status=status)
    if customer_id:
        contracts = contracts.filter(customer_id=customer_id)
    return render(request, "core/contracts_list.html", {"contracts": contracts, "customers": Customer.objects.order_by("name"), "status": status, "customer_id": customer_id})


def contract_create(request):
    if request.GET.get("calculate") == "1":
        try:
            result = _calculate_contract_values(request.GET)
            return JsonResponse({key: str(value) for key, value in result.items()})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    settings = _settings()
    initial = {
        "start_date": _today(),
        "payment_due_day": settings.default_payment_due_day,
        "interest_rate": settings.default_interest_rate,
        "calculation_mode": "B",
    }
    form = ContractForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                contract = form.save(commit=False)
                _set_contract_calculations(contract, form.cleaned_data)
                contract.save()
                _generate_installments(contract)
            messages.success(request, "تم حفظ العقد وتوليد الأقساط.")
            return redirect("core:contract_detail", id=contract.id)
        except Exception as exc:
            form.add_error(None, f"تعذر حساب العقد: {exc}")
    return render(request, "core/contracts_form.html", {"form": form, "title": "إضافة عقد", "is_create": True})


def contract_detail(request, id):
    contract = get_object_or_404(Contract.objects.select_related("customer", "product"), id=id)
    installments = contract.installments.order_by("installment_number")
    return render(request, "core/contracts_detail.html", {"contract": contract, "installments": installments, "profit": _contract_profit(contract), "total_paid": _sum(installments, "paid_amount")})


def contract_edit(request, id):
    if request.GET.get("calculate") == "1":
        try:
            result = _calculate_contract_values(request.GET)
            return JsonResponse({key: str(value) for key, value in result.items()})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    contract = get_object_or_404(Contract, id=id)
    form = ContractForm(request.POST or None, instance=contract)
    if request.method == "POST" and form.is_valid():
        try:
            contract = form.save(commit=False)
            _set_contract_calculations(contract, form.cleaned_data)
            contract.save()
            messages.success(request, "تم تحديث العقد.")
            return redirect("core:contract_detail", id=contract.id)
        except Exception as exc:
            form.add_error(None, f"تعذر حساب العقد: {exc}")
    return render(request, "core/contracts_form.html", {"form": form, "title": "تعديل عقد", "is_create": False})


def contract_mark_completed(request, id):
    contract = get_object_or_404(Contract, id=id)
    if request.method == "POST":
        contract.status = Contract.STATUS_COMPLETED
        contract.save(update_fields=["status"])
        messages.success(request, "تم تعليم العقد كمكتمل.")
    return redirect("core:contract_detail", id=contract.id)


def installment_list(request):
    _mark_late_installments()
    installments = Installment.objects.select_related("contract", "contract__customer").order_by("due_date")
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
    installment = get_object_or_404(Installment.objects.select_related("contract", "contract__customer"), id=id)
    previous_paid = installment.paid_amount
    initial = {"paid_amount": installment.amount - installment.paid_amount, "paid_date": _today(), "payment_method": Installment.PAYMENT_CASH}
    form = InstallmentPaymentForm(request.POST or None, instance=installment, initial=initial)
    if request.method == "POST" and form.is_valid():
        payment_amount = form.cleaned_data["paid_amount"]
        installment = form.save(commit=False)
        installment.paid_amount = previous_paid + payment_amount
        if installment.paid_amount >= installment.amount:
            installment.status = Installment.STATUS_PAID
        elif installment.paid_amount > 0:
            installment.status = Installment.STATUS_PARTIAL
        else:
            installment.status = Installment.STATUS_PENDING
        installment.save()
        if not installment.contract.installments.exclude(status=Installment.STATUS_PAID).exists():
            installment.contract.status = Contract.STATUS_COMPLETED
            installment.contract.save(update_fields=["status"])
        messages.success(request, "تم تسجيل الدفع.")
        return redirect("core:contract_detail", id=installment.contract_id)
    return render(request, "core/installments_pay.html", {"form": form, "installment": installment})


def installment_due_today(request):
    installments = Installment.objects.select_related("contract", "contract__customer").filter(due_date=_today()).exclude(status=Installment.STATUS_PAID)
    return render(request, "core/installments_list.html", {"installments": installments, "title": "أقساط اليوم"})


def installment_overdue(request):
    _mark_late_installments()
    installments = Installment.objects.select_related("contract", "contract__customer").filter(status=Installment.STATUS_LATE)
    return render(request, "core/installments_list.html", {"installments": installments, "title": "الأقساط المتأخرة"})


def reports_dashboard(request):
    contracts = Contract.objects.all()
    installments = Installment.objects.all()
    expenses = Expense.objects.all()
    return render(request, "core/reports_index.html", {"contracts_count": contracts.count(), "total_invested": _sum(contracts, "actual_cost"), "total_collected": _sum(installments, "paid_amount"), "total_expenses": _sum(expenses, "amount"), "total_profit": sum((_contract_profit(c) for c in contracts), MONEY_ZERO)})


def profit_report(request):
    contracts = list(_contract_report_queryset())
    rows = [{"contract": contract, "profit": _contract_profit(contract)} for contract in contracts]
    return render(request, "core/reports_profit.html", {"rows": rows, "total_profit": sum((r["profit"] for r in rows), MONEY_ZERO)})


def profit_report_pdf(request):
    contracts = list(_contract_report_queryset())
    rows = [{"contract": contract, "profit": _contract_profit(contract)} for contract in contracts]
    return _pdf_response("core/reports_profit_pdf.html", {"request": request, "rows": rows, "total_profit": sum((r["profit"] for r in rows), MONEY_ZERO)}, "profit-report.pdf")


def customer_statement(request, id):
    customer = get_object_or_404(Customer, id=id)
    contracts = Contract.objects.filter(customer=customer).order_by("-created_at")
    installments = Installment.objects.filter(contract__customer=customer).select_related("contract").order_by("due_date")
    return render(request, "core/reports_customer_statement.html", {"customer": customer, "contracts": contracts, "installments": installments, "total_paid": _sum(installments, "paid_amount"), "total_remaining": _sum(installments.exclude(status=Installment.STATUS_PAID), "amount")})


def customer_statement_pdf(request, id):
    customer = get_object_or_404(Customer, id=id)
    installments = Installment.objects.filter(contract__customer=customer).select_related("contract").order_by("due_date")
    return _pdf_response("core/reports_customer_statement_pdf.html", {"request": request, "customer": customer, "installments": installments, "total_paid": _sum(installments, "paid_amount"), "total_remaining": _sum(installments.exclude(status=Installment.STATUS_PAID), "amount")}, f"customer-{customer.id}-statement.pdf")


def investment_report(request):
    contracts = Contract.objects.select_related("customer").order_by("-created_at")
    return render(request, "core/reports_investment.html", {"contracts": contracts, "total_invested": _sum(contracts, "actual_cost"), "total_customer_price": _sum(contracts, "customer_price"), "total_collected": _sum(Installment.objects.all(), "paid_amount")})


def suppliers_report(request):
    suppliers = Supplier.objects.annotate(total_spent=Sum("supplierpurchase__purchase_price", default=MONEY_ZERO)).order_by("-total_spent")
    return render(request, "core/reports_suppliers.html", {"suppliers": suppliers, "total_spent": _sum(SupplierPurchase.objects.all(), "purchase_price")})


def monthly_report(request):
    payments = (
        Installment.objects.filter(paid_date__isnull=False)
        .annotate(month=TruncMonth("paid_date"))
        .values("month")
        .annotate(total_collected=Sum("paid_amount", default=MONEY_ZERO), count=Count("id"))
        .order_by("-month")
    )
    expenses = Expense.objects.annotate(month=TruncMonth("expense_date")).values("month").annotate(total_expenses=Sum("amount", default=MONEY_ZERO))
    expense_by_month = {item["month"]: item["total_expenses"] for item in expenses}
    rows = []
    for item in payments:
        total_expenses = expense_by_month.get(item["month"], MONEY_ZERO)
        rows.append({"month": item["month"], "total_collected": item["total_collected"], "total_expenses": total_expenses, "net": item["total_collected"] - total_expenses, "count": item["count"]})
    return render(request, "core/reports_monthly.html", {"rows": rows})


def notification_list(request):
    notifications = Notification.objects.select_related("contract", "installment").order_by("-created_at")
    return render(request, "core/notifications.html", {"notifications": notifications})


def notification_read(request, id):
    notification = get_object_or_404(Notification, id=id)
    if request.method == "POST":
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        messages.success(request, "تم تعليم التنبيه كمقروء.")
    return redirect("core:notification_list")


def notification_check_due(request):
    if request.method == "POST":
        created = 0
        due_installments = Installment.objects.select_related("contract", "contract__customer").filter(due_date__lte=_today()).exclude(status=Installment.STATUS_PAID)
        for installment in due_installments:
            notification_type = Notification.TYPE_OVERDUE if installment.due_date < _today() else Notification.TYPE_REMINDER
            message = f"قسط مستحق للعميل {installment.contract.customer.name} في عقد {installment.contract.contract_number}"
            if not Notification.objects.filter(installment=installment, message=message).exists():
                Notification.objects.create(contract=installment.contract, installment=installment, message=message, notification_type=notification_type)
                created += 1
        messages.success(request, f"تم إنشاء {created} تنبيه.")
    return redirect("core:notification_list")


def expense_list(request):
    expenses = Expense.objects.order_by("-expense_date")
    return render(request, "core/expenses_list.html", {"expenses": expenses, "total": _sum(expenses, "amount")})


def expense_create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم حفظ المصروف.")
        return redirect("core:expense_list")
    return render(request, "core/expenses_form.html", {"form": form, "title": "إضافة مصروف"})


def settings_view(request):
    instance = _settings()
    form = SettingsForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم حفظ الإعدادات.")
        return redirect("core:settings")
    return render(request, "core/settings.html", {"form": form})



