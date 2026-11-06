from decimal import Decimal
from catalog.models import Book

SESSION_KEY = "cart"
MAX_QUANTITY = 999


class Cart:
    """Session cart stores only IDs and quantities; price is always read live."""
    def __init__(self, request):
        self.session = request.session
        self.data = self.session.get(SESSION_KEY, {})
        self.adjustments = []
        if not isinstance(self.data, dict):
            self.data = {}
            self.session[SESSION_KEY] = self.data

    def _save(self):
        self.session[SESSION_KEY] = self.data
        self.session.modified = True

    @staticmethod
    def _quantity(value):
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError):
            return 1
        return max(1, min(number, MAX_QUANTITY))

    def add(self, book, quantity=1):
        if not book.is_active or book.stock < 1:
            return 0
        requested = self._quantity(quantity)
        current = self._quantity(self.data.get(str(book.pk), 0)) if str(book.pk) in self.data else 0
        final = min(book.stock, current + requested)
        self.data[str(book.pk)] = final
        self._save()
        return final

    def set_quantity(self, book, quantity):
        key = str(book.pk)
        if not book.is_active or book.stock < 1:
            self.data.pop(key, None)
            self._save()
            return 0
        try:
            requested = int(quantity)
        except (TypeError, ValueError, OverflowError):
            requested = 1
        if requested <= 0:
            self.data.pop(key, None)
            self._save()
            return 0
        final = min(requested, book.stock, MAX_QUANTITY)
        self.data[key] = final
        self._save()
        return final

    def remove(self, book):
        self.data.pop(str(book.pk), None)
        self._save()

    def clear(self):
        self.data = {}
        self.session[SESSION_KEY] = self.data
        self.session.modified = True

    def __iter__(self):
        ids = []
        for key in self.data:
            try:
                ids.append(int(key))
            except (TypeError, ValueError):
                continue
        books = Book.objects.filter(pk__in=ids, is_active=True).select_related("category")
        available = {str(book.pk): book for book in books}
        changed = False
        self.adjustments = []
        rows = []
        for key, raw_quantity in list(self.data.items()):
            book = available.get(str(key))
            if book is None:
                self.data.pop(key, None)
                changed = True
                continue
            quantity = self._quantity(raw_quantity)
            if book.stock < 1:
                self.adjustments.append((book, quantity, 0))
                self.data.pop(key, None)
                changed = True
                continue
            if quantity > book.stock:
                self.adjustments.append((book, quantity, book.stock))
                quantity = book.stock
                self.data[key] = quantity
                changed = True
            unit_price = book.price
            rows.append({"book": book, "quantity": quantity, "unit_price": unit_price,
                         "subtotal": unit_price * quantity})
        if changed:
            self._save()
        return iter(rows)

    @property
    def total(self):
        return sum((item["subtotal"] for item in self), Decimal("0.00"))

    @property
    def count(self):
        return sum(item["quantity"] for item in self)

    def __len__(self):
        return self.count
