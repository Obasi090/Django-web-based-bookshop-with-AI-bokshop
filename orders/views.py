from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Book
from .cart import Cart
from .forms import CheckoutForm
from .models import Order, OrderItem


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def cart_detail(request):
    cart = Cart(request)
    items = list(cart)
    for book, old_quantity, available in cart.adjustments:
        if available <= 0:
            cart.data.pop(str(book.pk), None)
        else:
            cart.data[str(book.pk)] = available
        cart._save()
        if available <= 0:
            messages.warning(request, f"{book.title} was removed from your cart because it is out of stock.")
        else:
            messages.warning(request, f"Quantity for {book.title} was reduced from {old_quantity} to {available}, the available stock.")
    return render(request, "orders/cart.html", {"items": items, "cart": cart, "cart_total": cart.total})


@require_POST
def cart_add(request, book_id):
    book = get_object_or_404(Book, pk=book_id, is_active=True)
    cart = Cart(request)
    if not book.in_stock:
        message = f"{book.title} is currently out of stock."
        added = False
    else:
        raw = request.POST.get("quantity", "1")
        try:
            quantity = int(raw)
            if quantity < 1:
                quantity = 1
        except (TypeError, ValueError, OverflowError):
            quantity = 1
        before = cart.data.get(str(book.pk), 0)
        try:
            before_quantity = int(before or 0)
        except (TypeError, ValueError, OverflowError):
            before_quantity = 0
        final = cart.add(book, quantity)
        added = final > 0
        if final < before_quantity + quantity:
            message = f"Quantity for {book.title} was limited to available stock ({final})."
        else:
            message = f"Added {book.title} to your cart."
    if _wants_json(request):
        return JsonResponse({"ok": added, "message": message, "cart_count": cart.count,
                             "cart_total": str(cart.total)}, status=200 if added else 400)
    (messages.success if added else messages.warning)(request, message)
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect("orders:cart_detail")


@require_POST
def cart_update(request, book_id):
    cart = Cart(request)
    book = get_object_or_404(Book, pk=book_id)
    old = cart.data.get(str(book.pk), 0)
    raw = request.POST.get("quantity", "1")
    try:
        requested = int(raw)
    except (TypeError, ValueError, OverflowError):
        requested = 1
    final = cart.set_quantity(book, requested)
    if final == 0:
        messages.info(request, f"{book.title} was removed from your cart because it is unavailable or quantity was zero.")
    elif final < requested:
        messages.warning(request, f"Quantity for {book.title} was reduced to {final}, the available stock.")
    elif final != old:
        messages.success(request, f"Updated quantity for {book.title}.")
    return redirect("orders:cart_detail")


@require_POST
def cart_remove(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    Cart(request).remove(book)
    messages.info(request, f"Removed {book.title} from your cart.")
    return redirect("orders:cart_detail")


@login_required
def checkout(request):
    cart = Cart(request)
    # Check raw session quantities before iteration can clamp them to current stock.
    if request.method == "POST":
        requested_quantities = dict(cart.data)
        ids = []
        for key in requested_quantities:
            try:
                ids.append(int(key))
            except (TypeError, ValueError):
                continue
        current_books = {str(book.pk): book for book in Book.objects.filter(pk__in=ids)}
        unavailable = []
        for key, raw_quantity in requested_quantities.items():
            book = current_books.get(str(key))
            try:
                quantity = int(raw_quantity)
            except (TypeError, ValueError, OverflowError):
                quantity = 0
            if book is None or not book.is_active or quantity < 1 or book.stock < quantity:
                unavailable.append(book.title if book else "A book in your cart")
        if unavailable:
            messages.warning(request, "Stock changed for: " + ", ".join(unavailable) + ". Please review your cart.")
            return redirect("orders:cart_detail")
    items = list(cart)
    if cart.adjustments:
        messages.warning(request, "Stock changed for one or more books. Please review the adjusted quantities before checkout.")
        return redirect("orders:cart_detail")
    if not items:
        messages.info(request, "Your cart is empty. Add a book before checkout.")
        return redirect("orders:cart_detail")

    form = CheckoutForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        # A transaction keeps the order, stock changes and cart clear together. Row locks
        # protect the last copy on databases that support them; SQLite serialises writes.
        with transaction.atomic():
            cart = Cart(request)
            requested_quantities = dict(cart.data)
            raw_ids = []
            for key in requested_quantities:
                try:
                    raw_ids.append(int(key))
                except (TypeError, ValueError):
                    continue
            locked_books = {
                str(book.pk): book for book in Book.objects.select_for_update().filter(pk__in=raw_ids)
            }
            problems = []
            for key, raw_quantity in requested_quantities.items():
                book = locked_books.get(str(key))
                try:
                    quantity = int(raw_quantity)
                except (TypeError, ValueError, OverflowError):
                    quantity = 0
                if book is None or not book.is_active or quantity < 1 or book.stock < quantity:
                    problems.append(book.title if book else "A book in your cart")
            if problems:
                messages.warning(request, "Stock changed before checkout for: " + ", ".join(problems) + ". Please review your cart.")
                return redirect("orders:cart_detail")
            cart_rows = []
            for key, raw_quantity in requested_quantities.items():
                book = locked_books.get(str(key))
                if book is None:
                    continue
                quantity = int(raw_quantity)
                cart_rows.append({"book": book, "quantity": quantity, "unit_price": book.price,
                                  "subtotal": book.price * quantity})
            if not cart_rows:
                messages.warning(request, "Your cart changed before checkout. Please review it and try again.")
                return redirect("orders:cart_detail")

            order = Order.objects.create(user=request.user, **form.cleaned_data, total=Decimal("0.00"))
            total = Decimal("0.00")
            for row in cart_rows:
                book = row["book"]
                price = book.price
                quantity = row["quantity"]
                OrderItem.objects.create(order=order, book=book, title=book.title,
                                         unit_price=price, quantity=quantity)
                book.stock -= quantity
                book.save(update_fields=["stock", "updated_at"])
                total += price * quantity
            order.total = total
            order.save(update_fields=["total"])
            cart.clear()
        messages.success(request, f"Your order {order.reference} has been placed. Payment is due on delivery.")
        return redirect("orders:order_detail", pk=order.pk)

    return render(request, "orders/checkout.html", {"form": form, "items": items, "cart_total": cart.total})


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, user=request.user)
    return render(request, "orders/order_detail.html", {"order": order})
