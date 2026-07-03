from django.urls import path

from . import views


app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/create/", views.customer_create, name="customer_create"),
    path("customers/<int:id>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:id>/edit/", views.customer_edit, name="customer_edit"),
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/create/", views.supplier_create, name="supplier_create"),
    path("suppliers/<int:id>/", views.supplier_detail, name="supplier_detail"),
    path("suppliers/<int:id>/edit/", views.supplier_edit, name="supplier_edit"),
    path("products/", views.product_list, name="product_list"),
    path("products/create/", views.product_create, name="product_create"),
    path("products/<int:id>/", views.product_detail, name="product_detail"),
    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/create/", views.purchase_create, name="purchase_create"),
    path("contracts/", views.contract_list, name="contract_list"),
    path("contracts/create/", views.contract_create, name="contract_create"),
    path("contracts/<int:id>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:id>/edit/", views.contract_edit, name="contract_edit"),
    path(
        "contracts/<int:id>/mark-completed/",
        views.contract_mark_completed,
        name="contract_mark_completed",
    ),
    path("installments/", views.installment_list, name="installment_list"),
    path(
        "installments/<int:id>/pay/",
        views.installment_pay,
        name="installment_pay",
    ),
    path(
        "installments/due-today/",
        views.installment_due_today,
        name="installment_due_today",
    ),
    path(
        "installments/overdue/",
        views.installment_overdue,
        name="installment_overdue",
    ),
    path("reports/", views.reports_dashboard, name="reports_dashboard"),
    path("reports/profit/", views.profit_report, name="profit_report"),
    path("reports/profit/pdf/", views.profit_report_pdf, name="profit_report_pdf"),
    path(
        "reports/customer-statement/<int:id>/",
        views.customer_statement,
        name="customer_statement",
    ),
    path(
        "reports/customer-statement/<int:id>/pdf/",
        views.customer_statement_pdf,
        name="customer_statement_pdf",
    ),
    path("reports/investment/", views.investment_report, name="investment_report"),
    path("reports/suppliers/", views.suppliers_report, name="suppliers_report"),
    path("reports/monthly/", views.monthly_report, name="monthly_report"),
    path("notifications/", views.notification_list, name="notification_list"),
    path(
        "notifications/<int:id>/read/",
        views.notification_read,
        name="notification_read",
    ),
    path(
        "notifications/check-due/",
        views.notification_check_due,
        name="notification_check_due",
    ),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/create/", views.expense_create, name="expense_create"),
    path("settings/", views.settings_view, name="settings"),
]
