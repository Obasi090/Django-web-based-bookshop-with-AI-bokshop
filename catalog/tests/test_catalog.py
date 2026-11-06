import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from catalog.models import Book, Category, BookEmbedding
from catalog.services.reefapi import normalise_book
from catalog.management.commands.import_books import Command


class NormaliseBookTests(TestCase):
    def test_normalises_authors_series_whitespace_and_description(self):
        record = normalise_book({
            "id": "123", "title": "  A   Story ",
            "authors": [{"name": "Author   One", "role": "Author"},
                        {"name": "Editor Name", "role": "Editor"}],
            "series": [{"title": " A   Series ", "placement": 2}],
            "description": "Hello<br>world\r\n&amp; friends",
            "genres": ["Fantasy"], "avg_rating": 4.2,
            "reviews": ["should be dropped"], "buy_links": ["should be dropped"],
        })
        self.assertEqual(record["title"], "A Story")
        self.assertEqual(record["author"], "Author One")
        self.assertEqual(record["series_name"], "A Series")
        self.assertEqual(record["description"], "Hello\nworld\n& friends")
        self.assertNotIn("reviews", record)
        self.assertNotIn("buy_links", record)
        self.assertEqual(record["goodreads_id"], "123")

    def test_missing_fields_are_safe(self):
        record = normalise_book({"id": "9", "title": "Book"})
        self.assertEqual(record["author"], "")
        self.assertEqual(record["genres"], [])
        self.assertEqual(record["ratings_count"], 0)


class CatalogueViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fantasy", slug="fantasy")
        for i in range(13):
            Book.objects.create(goodreads_id=str(i), title=f"Book {i}", author="Test Author",
                                description="Description", category=self.category,
                                price=Decimal("4000.00"), stock=5)
        self.inactive = Book.objects.create(goodreads_id="inactive", title="Hidden book", is_active=False)

    def test_list_search_filter_pagination_and_invalid_page(self):
        response = self.client.get(reverse("catalog:book_list"), {"q": "Book 1", "category": "fantasy", "page": "not-a-page"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book 1")
        self.assertNotContains(response, "Hidden book")
        self.assertEqual(response.context["page"].number, 1)
        response = self.client.get(reverse("catalog:book_list"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].number, 2)

    def test_detail_and_inactive_404(self):
        book = Book.objects.filter(is_active=True).first()
        self.assertEqual(self.client.get(reverse("catalog:book_detail", args=[book.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("catalog:book_detail", args=[self.inactive.pk])).status_code, 404)


class ImportCommandTests(TestCase):
    def setUp(self):
        self.command = Command()
        self.record = {"goodreads_id": "55", "title": "Title", "author": "Writer",
                       "description": "Description", "genres": [], "series_name": "",
                       "series_position": "", "isbn": "", "isbn13": "", "publisher": "",
                       "publish_year": None, "num_pages": 100, "language": "English",
                       "avg_rating": None, "ratings_count": 0, "cover_url": "", "source_url": "",
                       "category": "fantasy"}

    def test_import_does_not_overwrite_shop_fields(self):
        book = Book.objects.create(goodreads_id="55", title="Old", price=Decimal("9999.00"), stock=2, is_active=False)
        self.command.save_record(self.record)
        book.refresh_from_db()
        self.assertEqual(book.title, "Title")
        self.assertEqual(book.price, Decimal("9999.00"))
        self.assertEqual(book.stock, 2)
        self.assertFalse(book.is_active)

    def test_snapshot_import(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            path.write_text(json.dumps([self.record]), encoding="utf-8")
            call_command("import_books", from_snapshot=path, verbosity=0)
        self.assertTrue(Book.objects.filter(goodreads_id="55").exists())
