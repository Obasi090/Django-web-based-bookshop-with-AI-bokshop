from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, Client
from django.urls import reverse

from catalog.models import Book, BookEmbedding, Category
from catalog.services import chatbot


class CleanReplyTests(SimpleTestCase):
    def test_fixes_plain_text_and_currency(self):
        self.assertEqual(chatbot.clean_reply("**Try this**: ₦₦ 6,400", {"6,400"}), "Try this: ₦6,400")
        self.assertEqual(chatbot.clean_reply("It has 800 pages and costs 6,400", {"6,400"}), "It has 800 pages and costs ₦6,400")


class ChatbotServiceTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Fantasy", slug="fantasy")
        self.book = Book.objects.create(goodreads_id="1", title="The Test Book", author="A Writer",
            description="A test description", category=category, price=Decimal("6400.00"), stock=3,
            avg_rating=Decimal("4.50"), ratings_count=100)

    def test_format_catalogue_uses_live_price_and_stock(self):
        result = chatbot.format_catalogue([(0.9, self.book)])
        self.assertIn("₦6,400", result)
        self.assertIn("in stock (3 left)", result)
        self.book.stock = 0
        self.assertIn("OUT OF STOCK", chatbot.format_catalogue([(0.9, self.book)]))

    @patch("catalog.services.chatbot.embed_texts", return_value=[[1.0, 0.0]])
    def test_retrieval_ranks_closest_book(self, _embed):
        BookEmbedding.objects.create(book=self.book, vector=[1.0, 0.0], model_name=chatbot.embedding_model(), text_hash="abc")
        other = Book.objects.create(goodreads_id="2", title="Other Book", price=Decimal("1000.00"), stock=1)
        BookEmbedding.objects.create(book=other, vector=[0.0, 1.0], model_name=chatbot.embedding_model(), text_hash="def")
        self.assertEqual(chatbot.retrieve_books("a question")[0][1], self.book)

    @patch("catalog.services.chatbot.time.sleep")
    def test_embedding_command_skips_unchanged_and_force_refreshes(self, _sleep):
        with patch("catalog.services.chatbot.embed_texts", return_value=[[1.0, 0.0]]) as fake_embed:
            embedded, skipped = chatbot.embed_books(batch_size=1, delay=0, per_minute=100)
            self.assertEqual((embedded, skipped), (1, 0))
            fake_embed.assert_called_once()
        with patch("catalog.services.chatbot.embed_texts") as fake_embed:
            embedded, skipped = chatbot.embed_books(batch_size=1, delay=0, per_minute=100)
            self.assertEqual((embedded, skipped), (0, 1))
            fake_embed.assert_not_called()
        with patch("catalog.services.chatbot.embed_texts", return_value=[[0.0, 1.0]]) as fake_embed:
            embedded, skipped = chatbot.embed_books(force=True, batch_size=1, delay=0, per_minute=100)
            self.assertEqual((embedded, skipped), (1, 0))
            fake_embed.assert_called_once()

    @patch("catalog.services.chatbot.time.sleep")
    @patch("catalog.services.chatbot.embed_texts", return_value=[[1.0, 0.0]])
    def test_embedding_command_paces_between_batches(self, _embed, sleep):
        Book.objects.create(goodreads_id="pace-2", title="Second Test Book", description="Another description", stock=1)
        embedded, skipped = chatbot.embed_books(batch_size=1, delay=0, per_minute=100)
        self.assertEqual((embedded, skipped), (2, 0))
        sleep.assert_called_once_with(0.6)

    def test_retry_waits_for_rate_limit_but_not_bad_request(self):
        class FakeAPIError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code

        with patch.object(chatbot.errors, "APIError", FakeAPIError), patch("catalog.services.chatbot.time.sleep") as sleep:
            calls = {"count": 0}
            def flaky():
                calls["count"] += 1
                if calls["count"] == 1:
                    raise FakeAPIError(429, "Please retry in 1s")
                return "ok"
            self.assertEqual(chatbot._with_retry(flaky, attempts=2, max_wait=8), "ok")
            sleep.assert_called_once_with(2.0)
            with self.assertRaises(chatbot.ChatbotError):
                chatbot._with_retry(lambda: (_ for _ in ()).throw(FakeAPIError(400, "bad request")), attempts=3, max_wait=8)
            self.assertEqual(sleep.call_count, 1)
            with self.assertRaises(chatbot.ChatbotError):
                chatbot._with_retry(lambda: (_ for _ in ()).throw(FakeAPIError(429, "Please retry in 60s")), attempts=3, max_wait=8)
            self.assertEqual(sleep.call_count, 1)


class ChatEndpointTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_invalid_messages_are_rejected(self):
        self.client.get(reverse("catalog:book_list"))
        token = self.client.cookies["csrftoken"].value
        url = reverse("catalog:chat")
        self.assertEqual(self.client.post(url, data="{bad", content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 400)
        self.assertEqual(self.client.post(url, data='{"message":""}', content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 400)
        self.assertEqual(self.client.post(url, data='{"message":"' + ('x' * 501) + '"}', content_type="application/json", HTTP_X_CSRFTOKEN=token).status_code, 400)
        self.assertEqual(self.client.post(url, data='{"message":"x"}', content_type="application/json").status_code, 403)

    @patch("catalog.views.answer", return_value=("Hello", []))
    def test_history_capped_and_rate_limited(self, _answer):
        self.client.get(reverse("catalog:book_list"))
        token = self.client.cookies["csrftoken"].value
        url = reverse("catalog:chat")
        for _ in range(4):
            response = self.client.post(url, data='{"message":"hi"}', content_type="application/json", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 200)
        session = self.client.session
        self.assertEqual(len(session["chat_history"]), 8)
        session["chat_timestamps"] = [__import__("time").time()] * 20
        session.save()
        response = self.client.post(url, data='{"message":"hi"}', content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 429)

    @patch("catalog.views.answer", side_effect=chatbot.ChatbotError("upstream"))
    def test_model_error_returns_503(self, _answer):
        self.client.get(reverse("catalog:book_list"))
        token = self.client.cookies["csrftoken"].value
        response = self.client.post(reverse("catalog:chat"), data='{"message":"hi"}', content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 503)

    def test_reset_clears_history(self):
        session = self.client.session
        session["chat_history"] = [{"role": "user", "text": "hi"}]
        session.save()
        self.client.get(reverse("catalog:book_list"))
        token = self.client.cookies["csrftoken"].value
        response = self.client.post(reverse("catalog:chat_reset"), data="", content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("chat_history", self.client.session)
