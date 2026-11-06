from django.contrib import admin, messages
from django.db import transaction
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("book", "title", "unit_price", "quantity", "subtotal_display")
    fields = readonly_fields

    @admin.display(description="Subtotal")
    def subtotal_display(self, obj):
        return obj.subtotal if obj.pk else "—"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference_display", "user", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "phone", "user__username")
    readonly_fields = ("user", "full_name", "phone", "address", "city", "notes", "payment_method", "total", "created_at")
    inlines = (OrderItemInline,)
    actions = ("mark_confirmed", "mark_delivered", "cancel_and_restock")

    @admin.display(description="Reference", ordering="id")
    def reference_display(self, obj):
        return obj.reference

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        # Let a defence user search for the displayed reference (for example BH-000123).
        digits = search_term.upper().removeprefix("BH-").lstrip("0")
        if digits.isdigit():
            queryset |= self.model.objects.filter(pk=int(digits))
        return queryset, use_distinct

    @admin.action(description="Mark selected orders confirmed")
    def mark_confirmed(self, request, queryset):
        queryset.exclude(status=Order.Status.CANCELLED).update(status=Order.Status.CONFIRMED)

    @admin.action(description="Mark selected orders delivered")
    def mark_delivered(self, request, queryset):
        queryset.exclude(status=Order.Status.CANCELLED).update(status=Order.Status.DELIVERED)

    @admin.action(description="Cancel orders and restock items")
    def cancel_and_restock(self, request, queryset):
        count = 0
        with transaction.atomic():
            for order in queryset.select_for_update().prefetch_related("items"):
                if order.status == Order.Status.CANCELLED:
                    continue
                for item in order.items.all():
                    if item.book_id:
                        item.book.stock += item.quantity
                        item.book.save(update_fields=("stock", "updated_at"))
                order.status = Order.Status.CANCELLED
                order.save(update_fields=("status",))
                count += 1
        self.message_user(request, f"Cancelled and restocked {count} order(s).", messages.SUCCESS)
