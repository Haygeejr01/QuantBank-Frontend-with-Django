from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def naira(value):
    try:
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0.00")
    return f"NGN {amount:,.2f}"
