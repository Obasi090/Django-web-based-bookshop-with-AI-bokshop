from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.urls import reverse

from catalog.models import Book
from orders.admin import OrderAdmin
from orders.cart import Cart
from orders.models import Order, OrderItem

User = get_user_model()


class AccountFlowTests(TestCase):
    def test_signup_logs_user_in(self):
        response = self.client.post(reverse("accounts:signup"), {
            "username": "reader", "password1": "StrongPass!9482", "password2": "StrongPass!9482",
        })
        self.assertRedirects(response, reverse("catalog:book_list"))
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_login_and_post_logout(self):
        user = User.objects.create_user(username="reader", password="StrongPass!9482")
        self.assertFalse(self.client.login(username="reader", password="WrongPassword!"))
        self.assertTrue(self.client.login(username="reader", password="StrongPass!9482"))
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class CartTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(goodreads_id="book-1", title="Test Book", price=Decimal("1250.50"), stock=3)

    def test_add_update_remove_and_decimal_total(self):
        response = self.client.post(reverse("orders:cart_add", args=[self.book.pk]), {"quantity": "99"})
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertEqual(session["cart"][str(self.book.pk)], 3)
        self.assertEqual(Cart(type("Request", (), {"session": session})()).total, Decimal("3751.50"))
        self.client.post(reverse("orders:cart_update", args=[self.book.pk]), {"quantity": "2"})
        self.assertEqual(self.client.session["cart"][str(self.book.pk)], 2)
        self.client.post(reverse("orders:cart_remove", args=[self.book.pk]))
        self.assertNotIn(str(self.book.pk), self.client.session["cart"])

    def test_anonymous_cart_drops_inactive_book(self):
        self.client.post(reverse("orders:cart_add", args=[self.book.pk]), {"quantity": 1})
        self.book.is_active = False
        self.book.save()
        session = self.client.session
        cart = Cart(type("Request", (), {"session": session})())
        self.assertEqual(list(cart), [])
        self.assertNotIn(str(self.book.pk), session["cart"])


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="StrongPass!9482")
        self.book = Book.objects.create(goodreads_id="book-2", title="Snapshot Book", price=Decimal("2400.00"), stock=5)
        self.client.login(username="reader", password="StrongPass!9482")
        self.checkout_data = {"full_name": "Reader Person", "phone": "+234 801 234 5678",
                              "address": "1 Example Street", "city": "Nsukka", "notes": "Call on arrival"}

    def _add_to_cart(self, quantity=2):
        self.client.post(reverse("orders:cart_add", args=[self.book.pk]), {"quantity": quantity})

    def test_checkout_creates_order_snapshots_and_decrements_stock(self):
        self._add_to_cart(2)
        response = self.client.post(reverse("orders:checkout"), self.checkout_data)
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:order_detail", args=[order.pk]))
        self.assertEqual(order.total, Decimal("4800.00"))
        item = order.items.get()
        self.assertEqual(item.title, "Snapshot Book")
        self.assertEqual(item.unit_price, Decimal("2400.00"))
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 3)
        self.assertEqual(self.client.session.get("cart", {}), {})
        self.book.price = Decimal("9900.00")
        self.book.save()
        self.assertEqual(order.items.get().unit_price, Decimal("2400.00"))

    def test_insufficient_stock_creates_no_order_and_does_not_decrement(self):
        self._add_to_cart(3)
        self.book.stock = 1
        self.book.save()
        response = self.client.post(reverse("orders:checkout"), self.checkout_data)
        self.assertRedirects(response, reverse("orders:cart_detail"))
        self.assertEqual(Order.objects.count(), 0)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock, 1)

    def test_login_required_and_other_user_gets_404(self):
        self._add_to_cart(1)
        self.client.post(reverse("orders:checkout"), self.checkout_data)
        order = Order.objects.get()
        other = User.objects.create_user(username="other", password="StrongPass!9482")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("orders:order_detail", args=[order.pk])).status_code, 404)


class AdminOrderActionTests(TestCase):
    def test_confirm_and_deliver_actions(self):
        user = User.objects.create_user(username="reader", password="StrongPass!9482")
        order = Order.objects.create(user=user, full_name="Reader", phone="12345678", address="Road", city="Town")
        model_admin = OrderAdmin(Order, AdminSite())
        request = type("Request", (), {"user": user})()
        model_admin.mark_confirmed(request, Order.objects.filter(pk=order.pk))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        model_admin.mark_delivered(request, Order.objects.filter(pk=order.pk))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_cancel_restock_only_once(self):
        user = User.objects.create_user(username="reader", password="StrongPass!9482")
        book = Book.objects.create(goodreads_id="book-3", title="Restock Book", price=Decimal("1000.00"), stock=4)
        order = Order.objects.create(user=user, full_name="Reader", phone="12345678", address="Road", city="Town", total=Decimal("2000.00"))
        OrderItem.objects.create(order=order, book=book, title=book.title, unit_price=book.price, quantity=2)
        book.stock = 2
        book.save()
        model_admin = OrderAdmin(Order, AdminSite())
        request = type("Request", (), {"user": user})()
        with patch.object(model_admin, "message_user"):
            model_admin.cancel_and_restock(request, Order.objects.filter(pk=order.pk))
            model_admin.cancel_and_restock(request, Order.objects.filter(pk=order.pk))
        book.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(book.stock, 4)
        self.assertEqual(order.status, Order.Status.CANCELLED)
