"""Import books from ReefAPI (Goodreads) into the local database.

Examples:
    python manage.py import_books --genre fantasy --per-genre 3
    python manage.py import_books --genre fantasy --genre mystery --per-genre 25 \
        --save-snapshot catalog/fixtures/books_snapshot.json
    python manage.py import_books --from-snapshot catalog/fixtures/books_snapshot.json
"""
import json
import random
import time
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Book, Category
from catalog.services.reefapi import (
    ReefAPIError,
    fetch_book_detail,
    fetch_genre,
    normalise_book,
)


def placeholder_price(num_pages):
    """PLACEHOLDER rule (NGN): base 3000 + 8 per page, rounded to nearest 100."""
    pages = num_pages or 300
    return Decimal(round(3000 + pages * 8, -2))


def placeholder_stock(goodreads_id):
    """PLACEHOLDER: repeatable pseudo-random stock between 3 and 20."""
    return random.Random(goodreads_id).randint(3, 20)


class Command(BaseCommand):
    help = "Import books from ReefAPI (or a saved snapshot) into the Book table."

    def add_arguments(self, parser):
        parser.add_argument("--genre", action="append",
                            help="Genre slug, e.g. fantasy. Repeat for several.")
        parser.add_argument("--per-genre", type=int, default=25,
                            help="Books to import per genre (default 25).")
        parser.add_argument("--delay", type=float, default=1.0,
                            help="Seconds to wait between API calls (default 1).")
        parser.add_argument("--save-snapshot", type=Path,
                            help="Write the fetched records to this JSON file.")
        parser.add_argument("--from-snapshot", type=Path,
                            help="Load records from a JSON file instead of the API.")

    def handle(self, *args, **options):
        if options["from_snapshot"]:
            path = options["from_snapshot"]
            if not path.exists():
                raise CommandError(f"Snapshot not found: {path}")
            records = json.loads(path.read_text(encoding="utf-8"))
        else:
            genres = options["genre"]
            if not genres:
                raise CommandError("Give at least one --genre or use --from-snapshot.")
            records = self.fetch_records(genres, options["per_genre"], options["delay"])
            if options["save_snapshot"]:
                path = options["save_snapshot"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.stdout.write(f"Snapshot saved to {path}")

        created = updated = 0
        for record in records:
            if self.save_record(record):
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created} created, {updated} updated."
        ))

    def fetch_records(self, genres, per_genre, delay):
        seen = set()
        records = []

        for genre in genres:
            self.stdout.write(f"\nGenre: {genre}")
            try:
                listing = fetch_genre(genre)
            except ReefAPIError as error:
                self.stderr.write(f"  Could not fetch genre '{genre}': {error}")
                continue

            picked = 0
            for item in listing:
                if picked >= per_genre:
                    break
                book_id = str(item.get("book_id") or "")
                if not book_id or book_id in seen:
                    continue
                seen.add(book_id)

                time.sleep(delay)
                try:
                    raw = fetch_book_detail(book_id)
                except ReefAPIError as error:
                    self.stderr.write(f"  Skipped {book_id}: {error}")
                    continue

                record = normalise_book(raw)
                if not record["goodreads_id"] or not record["title"]:
                    self.stderr.write(f"  Skipped {book_id}: missing id or title")
                    continue
                if not record["description"]:
                    self.stderr.write(f"  Skipped '{record['title']}': no description")
                    continue

                record["category"] = genre
                records.append(record)
                picked += 1
                self.stdout.write(f"  + {record['title']}")

        return records

    def save_record(self, record):
        """Create or update one book. Returns True if created."""
        fields = dict(record)
        for name in ("title", "author", "series_name", "publisher"):
            if isinstance(fields.get(name), str):
                fields[name] = " ".join(fields[name].split())
        slug = fields.pop("category", None)
        goodreads_id = fields.pop("goodreads_id")

        category = None
        if slug:
            category, _ = Category.objects.get_or_create(
                slug=slug, defaults={"name": slug.replace("-", " ").title()}
            )

        book = Book.objects.filter(goodreads_id=goodreads_id).first()
        if book is None:
            Book.objects.create(
                goodreads_id=goodreads_id,
                category=category,
                price=placeholder_price(fields.get("num_pages")),
                stock=placeholder_stock(goodreads_id),
                **fields,
            )
            return True

        # Existing book: refresh descriptive data only. Price, stock and
        # is_active belong to the shop and are never touched here.
        for name, value in fields.items():
            setattr(book, name, value)
        if book.category_id is None:
            book.category = category
        book.save()
        return False