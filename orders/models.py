from decimal import Decimal
from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    address = models.TextField()
    city = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=30, default="pay_on_delivery", editable=False)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    @property
    def reference(self):
        return f"BH-{self.pk:06d}" if self.pk else "BH-PENDING"

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey("catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items")
    title = models.CharField(max_length=300)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.title} × {self.quantity}"
