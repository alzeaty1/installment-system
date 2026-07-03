from decimal import Decimal, ROUND_HALF_UP


MONEY_PLACES = Decimal("0.01")
RATE_PLACES = Decimal("0.01")


def _decimal(value):
    return Decimal(str(value))


def _quantize_money(value):
    return _decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _quantize_rate(value):
    return _decimal(value).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def _validate_remaining_and_months(remaining, months_count):
    remaining = _decimal(remaining)
    months_count = int(months_count)

    if remaining <= 0:
        raise ValueError("remaining must be greater than zero")
    if months_count <= 0:
        raise ValueError("months_count must be greater than zero")

    return remaining, months_count


def calculate_mode_a(remaining, installment_amount, months_count):
    remaining, months_count = _validate_remaining_and_months(
        remaining,
        months_count,
    )
    installment_amount = _decimal(installment_amount)

    if installment_amount <= 0:
        raise ValueError("installment_amount must be greater than zero")

    total_payable = installment_amount * months_count
    interest = total_payable - remaining
    rate = (interest / remaining) * Decimal("100")

    return {
        "remaining_amount": _quantize_money(remaining),
        "interest_rate": _quantize_rate(rate),
        "total_interest": _quantize_money(interest),
        "total_amount": _quantize_money(total_payable),
        "installment_amount": _quantize_money(installment_amount),
        "months_count": months_count,
    }


def calculate_mode_b(remaining, interest_rate, months_count):
    remaining, months_count = _validate_remaining_and_months(
        remaining,
        months_count,
    )
    interest_rate = _decimal(interest_rate)

    if interest_rate < 0:
        raise ValueError("interest_rate must not be negative")

    interest = remaining * (interest_rate / Decimal("100"))
    total = remaining + interest
    installment = total / months_count

    return {
        "remaining_amount": _quantize_money(remaining),
        "interest_rate": _quantize_rate(interest_rate),
        "total_interest": _quantize_money(interest),
        "total_amount": _quantize_money(total),
        "installment_amount": _quantize_money(installment),
        "months_count": months_count,
    }


def calculate_mode_c(remaining, months_count, default_monthly_rate=Decimal("3.5")):
    remaining, months_count = _validate_remaining_and_months(
        remaining,
        months_count,
    )
    rate = _decimal(default_monthly_rate) * months_count
    return calculate_mode_b(remaining, rate, months_count)
