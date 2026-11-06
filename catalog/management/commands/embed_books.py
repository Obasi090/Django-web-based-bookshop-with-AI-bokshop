"""Create or refresh the Gemini embeddings the chatbot searches.

    python manage.py embed_books            # only new or changed books
    python manage.py embed_books --force    # re-embed everything
"""
from django.core.management.base import BaseCommand, CommandError

from catalog.services.chatbot import ChatbotError, embed_books


class Command(BaseCommand):
    help = "Create or refresh embeddings for the catalogue (needed by the chatbot)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-embed every book.")
        parser.add_argument("--batch-size", type=int, default=20,
                            help="Books per API request (default 20).")
        parser.add_argument("--delay", type=float, default=1.0,
                            help="Minimum seconds between requests (default 1).")
        parser.add_argument("--per-minute", type=int, default=80,
                            help="Max books to embed per minute (default 80; "
                                 "the free tier allows 100).")

    def handle(self, *args, **options):
        try:
            embedded, skipped = embed_books(
                force=options["force"],
                batch_size=options["batch_size"],
                delay=options["delay"],
                per_minute=options["per_minute"],
                log=self.stdout.write,
            )
        except ChatbotError as error:
            raise CommandError(str(error))

        self.stdout.write(self.style.SUCCESS(
            f"Embedded {embedded} book(s); {skipped} already up to date."
        ))