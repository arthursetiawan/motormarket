from decimal import Decimal

from django import template

register = template.Library()

DEAL_NAMES = {
    "great_deal": "Great deal",
    "good_deal": "Good deal",
    "fair": "Fair",
    "rich": "Above market",
    "overpriced": "Overpriced",
}


@register.filter
def currency_idr(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("1"))
    except Exception:
        return value
    return f"Rp {int(amount):,}".replace(",", ".")


@register.filter
def deal_name(value):
    return DEAL_NAMES.get(value, value or "")


@register.simple_tag
def querystring(request, **overrides):
    params = request.GET.copy()
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
