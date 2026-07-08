from django.urls import path
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView

from . import views


app_name = "core"

urlpatterns = [
    path(
        "login/",
        login_not_required(LoginView.as_view(template_name="core/login.html")),
        name="login",
    ),
    path(
        "logout/",
        login_not_required(LogoutView.as_view(next_page="login")),
        name="logout",
    ),
    path("", views.dashboard, name="dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/create/", views.customer_create, name="customer_create"),
    path("customers/<int:id>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:id>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:id>/delete/", views.customer_delete, name="customer_delete"),
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/create/", views.supplier_create, name="supplier_create"),
    path("suppliers/<int:id>/", views.supplier_detail, name="supplier_detail"),
    path("suppliers/<int:id>/edit/", views.supplier_edit, name="supplier_edit"),
    path("suppliers/<int:id>/delete/", views.supplier_delete, name="supplier_delete"),
    path("products/", views.product_list, name="product_list"),
    path("products/create/", views.product_create, name="product_create"),
    path("products/<int:id>/", views.product_detail, name="product_detail"),
    path("products/<int:id>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:id>/delete/", views.product_delete, name="product_delete"),
    path("contracts/", views.contract_list, name="contract_list"),
    path("contracts/create/", views.contract_create, name="contract_create"),
    path("contracts/<int:id>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:id>/summary/", views.contract_summary, name="contract_summary"),
    path("contracts/<int:id>/edit/", views.contract_edit, name="contract_edit"),
    path("contracts/<int:id>/delete/", views.contract_delete, name="contract_delete"),
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
        "installments/<int:id>/receipt/",
        views.installment_receipt,
        name="installment_receipt",
    ),
    path(
        "installments/<int:id>/reset-payment/",
        views.installment_reset_payment,
        name="installment_reset_payment",
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
    path("search/", views.search, name="search"),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/create/", views.expense_create, name="expense_create"),
    path("expenses/<int:id>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:id>/delete/", views.expense_delete, name="expense_delete"),
    path("accounts/create/", views.account_create, name="account_create"),
    path("accounts/switch/<int:account_id>/", views.account_switch, name="account_switch"),
    path("product-types/create/", views.product_type_create, name="product_type_create"),
    path("product-types/<int:id>/delete/", views.product_type_delete, name="product_type_delete"),
    path("settings/", views.settings_view, name="settings"),
    path("activity-log/", views.activity_log_list, name="activity_log"),
    path(
        "settings/backup/create/",
        views.backup_create_view,
        name="backup_create",
    ),
    path(
        "settings/backup/download/<str:filename>/",
        views.backup_download_view,
        name="backup_download",
    ),
    path(
        "settings/backup/delete/<str:filename>/",
        views.backup_delete_view,
        name="backup_delete",
    ),
    path(
        "settings/backup/restore/<str:filename>/",
        views.backup_restore_view,
        name="backup_restore",
    ),
    path("receivers/", views.receiver_list, name="receiver_list"),
    path("receivers/create/", views.receiver_create, name="receiver_create"),
    path("receivers/<int:pk>/", views.receiver_detail, name="receiver_detail"),
]
