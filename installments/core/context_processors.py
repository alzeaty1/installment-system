from .models import Account


def accounts_processor(request):
    accounts = Account.objects.all() if request.user.is_authenticated else []
    return {
        "accounts": accounts,
        "current_account": getattr(request, "current_account", None),
    }
