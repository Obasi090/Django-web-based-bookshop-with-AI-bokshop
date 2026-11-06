# Initial order schema. Prices and titles are snapshots so old orders stay accurate.
import decimal
import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ("catalog", "0002_bookembedding"),
    ]
    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=150)),
                ("phone", models.CharField(max_length=30)),
                ("address", models.TextField()),
                ("city", models.CharField(max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("delivered", "Delivered"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
                ("payment_method", models.CharField(default="pay_on_delivery", editable=False, max_length=30)),
                ("total", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=300)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("quantity", models.PositiveIntegerField()),
                ("book", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="catalog.book")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order")),
            ],
        ),
    ]
