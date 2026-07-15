from django import template
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter
def mask_money(value):
    """Format money as whole number (no decimals)."""
    try:
        return floatformat(value, 0)
    except (ValueError, TypeError):
        return "0"
