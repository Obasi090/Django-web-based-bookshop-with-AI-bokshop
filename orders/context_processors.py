from .cart import Cart
from catalog.models import Category


def cart_summary(request):
    cart = Cart(request)
    return {"cart_count": cart.count, "cart_total": cart.total, "nav_categories": Category.objects.all()}
