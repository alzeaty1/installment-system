from django.http import HttpResponse


def placeholder_view(request, *args, **kwargs):
    return HttpResponse("Placeholder view")


dashboard = placeholder_view
customer_list = placeholder_view
customer_create = placeholder_view
customer_detail = placeholder_view
customer_edit = placeholder_view
supplier_list = placeholder_view
supplier_create = placeholder_view
supplier_detail = placeholder_view
supplier_edit = placeholder_view
product_list = placeholder_view
product_create = placeholder_view
product_detail = placeholder_view
purchase_list = placeholder_view
purchase_create = placeholder_view
contract_list = placeholder_view
contract_create = placeholder_view
contract_detail = placeholder_view
contract_edit = placeholder_view
contract_mark_completed = placeholder_view
installment_list = placeholder_view
installment_pay = placeholder_view
installment_due_today = placeholder_view
installment_overdue = placeholder_view
reports_dashboard = placeholder_view
profit_report = placeholder_view
profit_report_pdf = placeholder_view
customer_statement = placeholder_view
customer_statement_pdf = placeholder_view
investment_report = placeholder_view
suppliers_report = placeholder_view
monthly_report = placeholder_view
notification_list = placeholder_view
notification_read = placeholder_view
notification_check_due = placeholder_view
expense_list = placeholder_view
expense_create = placeholder_view
settings_view = placeholder_view
