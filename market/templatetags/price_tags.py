from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def currency_idr(value):
    try:
        amount = Decimal(value)
    except Exception:
        return value
    # Format without decimals if .00, else keep two decimals
    if amount == amount.quantize(Decimal('1')):
        s = f"{int(amount):,}"
    else:
        s = f"{amount:,.2f}"
    return f"Rp {s.replace(',', '.')}"  # use dot as thousand separator typical in Indonesia
