"""Ask the chatbot a question from the terminal (shows what was retrieved).

    python manage.py ask_librarian "something like Fourth Wing"
"""
from django.core.management.base import BaseCommand, CommandError

from catalog.services.chatbot import ChatbotError, generate_reply, retrieve_books


class Command(BaseCommand):
    help = "Ask Juo'm one question and show the retrieved books and the reply."

    def add_arguments(self, parser):
        parser.add_argument("question")

    def handle(self, *args, **options):
        question = options["question"]
        try:
            scored = retrieve_books(question)
            self.stdout.write("Retrieved:")
            for score, book in scored:
                self.stdout.write(f"  {score:.3f}  {book.title}")
            reply = generate_reply(question, [], scored)
        except ChatbotError as error:
            raise CommandError(str(error))

        self.stdout.write("\nReply:\n" + reply)
