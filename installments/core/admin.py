from django.contrib import admin

from .models import (
    Contract,
    Customer,
    Expense,
    Installment,
    Notification,
    Product,
    ProductCategory,
    Settings,
    Supplier,
    SupplierCategory,
    SupplierPurchase,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "national_id", "whatsapp", "created_at")
    search_fields = ("name", "phone", "national_id", "whatsapp")
    list_filter = ("created_at",)


@admin.register(SupplierCategory)
class SupplierCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "category", "created_at")
    search_fields = ("name", "phone", "address", "notes")
    list_filter = ("category", "created_at")


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class ProductPurchaseInline(admin.TabularInline):
    model = SupplierPurchase
    extra = 0
    fields = (
        "customer",
        "contract",
        "supplier",
        "purchase_price",
        "purchase_date",
        "image",
        "notes",
    )
    readonly_fields = ("contract",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "category",
        "estimated_price",
        "created_at",
    )
    search_fields = ("name", "brand")
    list_filter = ("category", "brand", "created_at")
    inlines = (ProductPurchaseInline,)


@admin.register(SupplierPurchase)
class SupplierPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "contract",
        "supplier",
        "product",
        "product_name",
        "purchase_price",
        "purchase_date",
    )
    search_fields = (
        "customer__name",
        "contract__contract_number",
        "supplier__name",
        "product__name",
        "product_name",
        "notes",
    )
    list_filter = ("supplier", "product", "purchase_date", "created_at")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_number",
        "customer",
        "product_name",
        "customer_price",
        "down_payment",
        "remaining_amount",
        "interest_rate",
        "months_count",
        "installment_amount",
        "calculation_mode",
        "status",
        "start_date",
    )
    search_fields = (
        "contract_number",
        "customer__name",
        "customer__phone",
        "product__name",
        "product_name",
        "notes",
    )
    list_filter = ("status", "calculation_mode", "start_date", "created_at")


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = (
        "contract",
        "installment_number",
        "due_date",
        "amount",
        "paid_amount",
        "paid_date",
        "status",
        "payment_method",
    )
    search_fields = ("contract__contract_number", "contract__customer__name", "notes")
    list_filter = ("status", "payment_method", "due_date", "paid_date")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "amount", "expense_date", "category")
    search_fields = ("title", "category", "notes")
    list_filter = ("category", "expense_date")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "notification_type",
        "contract",
        "installment",
        "is_read",
        "created_at",
    )
    search_fields = ("message", "contract__contract_number")
    list_filter = ("notification_type", "is_read", "created_at")


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "default_interest_rate",
        "default_payment_due_day",
        "whatsapp_enabled",
    )
    search_fields = ("business_name",)
