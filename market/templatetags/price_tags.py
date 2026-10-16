from decimal import Decimal

from django import template

register = template.Library()

DEAL_NAMES = {
    "great_deal": "Sangat murah",
    "good_deal": "Murah",
    "fair": "Wajar",
    "rich": "Sedikit mahal",
    "overpriced": "Mahal",
}

TRUST_NAMES = {
    "high_trust": "Kepercayaan tinggi",
    "review": "Perlu dicek",
    "caution": "Waspada",
}

TRANS_NAMES = {
    "automatic": "Matic",
    "manual": "Manual",
}

FUEL_NAMES = {
    "petrol": "Bensin",
    "electric": "Listrik",
}

CONDITION_NAMES = {
    "excellent": "Istimewa",
    "good": "Baik",
    "fair": "Cukup",
    "poor": "Kurang",
}

SENTIMENT_NAMES = {
    "professional": "Jelas & profesional",
    "mixed": "Campuran",
    "caution": "Agresif / spam",
}

ANOMALY_NAMES = {
    "ok": "OK pasar",
    "waspada": "Waspada",
    "waspada_tinggi": "Waspada tinggi",
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


@register.filter
def trust_name(value):
    return TRUST_NAMES.get(value, value or "")


@register.filter
def trans_name(value):
    return TRANS_NAMES.get(value, value or "")


@register.filter
def fuel_name(value):
    return FUEL_NAMES.get(value, value or "")


@register.filter
def condition_name(value):
    return CONDITION_NAMES.get(value, value or "")


@register.filter
def anomaly_name(value):
    return ANOMALY_NAMES.get(value, value or "")


@register.filter
def abs_num(value):
    try:
        return abs(value)
    except Exception:
        return value


@register.simple_tag
def querystring(request, **overrides):
    params = request.GET.copy()
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


@register.filter
def sentiment_name(value):
    return SENTIMENT_NAMES.get(value, value or "")


@register.filter
def stars(value):
    """Render 1–5 score as ★/☆ string."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return "—"
    n = max(0, min(5, n))
    return "★" * n + "☆" * (5 - n)
