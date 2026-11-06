from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.inclusion_tag("catalog/_stars.html")
def stars(value):
    """Render safely clamped fractional stars for Decimal or string ratings."""
    try:
        rating = Decimal(str(value)) if value is not None else Decimal("0")
        if not rating.is_finite():
            rating = Decimal("0")
    except (InvalidOperation, TypeError, ValueError):
        rating = Decimal("0")
    rating = max(Decimal("0"), min(Decimal("5"), rating))
    return {"rating": rating, "fill": rating / Decimal("5") * Decimal("100")}
