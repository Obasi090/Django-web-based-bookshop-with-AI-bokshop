import json
import logging
import time

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Book, Category
from .services.chatbot import MAX_HISTORY_MESSAGES, ChatbotError, answer

logger = logging.getLogger(__name__)

BOOKS_PER_PAGE = 12
MAX_MESSAGE_LENGTH = 500
MIN_RATINGS = 1000
SORT_OPTIONS = {
    "popular": ("-ratings_count", "title"),
    "rating": ("-avg_rating", "-ratings_count", "title"),
    "newest": ("-created_at", "title"),
    "title": ("title",),
    "price_asc": ("price", "title"),
    "price_desc": ("-price", "title"),
}


def _shelf(queryset, title, url=None):
    return {"title": title, "url": url, "books": queryset[:12]}


def _series_position(book):
    try:
        position = float(book.series_position)
    except (TypeError, ValueError):
        position = float("inf")
    return position, book.title.casefold()


def home(request):
    active = Book.objects.filter(is_active=True).select_related("category")
    base = active.only("id", "title", "author", "cover_url", "avg_rating", "ratings_count", "price", "stock", "category_id", "category__name")
    shelves = []
    if active.count() >= 4:
        shelves = [
            _shelf(base.filter(ratings_count__gte=MIN_RATINGS).order_by("-avg_rating", "-ratings_count", "title"), "Top rated"),
            _shelf(base.order_by("-ratings_count", "title"), "Most popular"),
            _shelf(base.order_by("-created_at", "title"), "New in the shop"),
        ]
        categories = Category.objects.annotate(book_count=Count("books", filter=Q(books__is_active=True))).filter(book_count__gte=4).order_by("-book_count", "name")[:4]
        for category in categories:
            shelves.append(_shelf(base.filter(category=category).order_by("-ratings_count", "title"), f"Popular in {category.name}", reverse("catalog:book_list") + f"?category={category.slug}"))
    hero_books = base.order_by("-ratings_count", "title")[:3]
    return render(request, "catalog/home.html", {"categories": Category.objects.all(), "shelves": shelves, "hero_books": hero_books})


def genres(request):
    categories = Category.objects.annotate(book_count=Count("books", filter=Q(books__is_active=True))).order_by("name")
    return render(request, "catalog/genres.html", {"categories": categories})
CHAT_RATE_LIMIT = 20
CHAT_RATE_WINDOW_SECONDS = 10 * 60


def book_list(request):
    books = Book.objects.filter(is_active=True).select_related("category")

    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    series = request.GET.get("series", "").strip()
    author = request.GET.get("author", "").strip()
    in_stock = request.GET.get("in_stock") == "1"
    sort = request.GET.get("sort", "").strip()

    if query:
        books = books.filter(
            Q(title__icontains=query)
            | Q(author__icontains=query)
            | Q(series_name__icontains=query)
        )
    if category_slug:
        books = books.filter(category__slug=category_slug)
    if series:
        books = books.filter(series_name__iexact=series)
    if author:
        books = books.filter(author__icontains=author)
    if in_stock:
        books = books.filter(stock__gt=0)

    selected_sort = sort if sort in SORT_OPTIONS else ("popular" if not series else "")
    if selected_sort:
        books = books.order_by(*SORT_OPTIONS[selected_sort])
    elif series:
        # Series positions are strings; order by position in Python to handle decimals.
        books = list(books)
        books.sort(key=_series_position)
    else:
        books = books.order_by("title")

    page = Paginator(books, BOOKS_PER_PAGE).get_page(request.GET.get("page"))

    if query:
        heading = f'Search results for “{query}”'
    elif category_slug:
        heading = (Category.objects.filter(slug=category_slug).values_list("name", flat=True).first() or "All books")
    elif series:
        heading = f"Books in {series}"
    elif author:
        heading = f"Books by {author}"
    else:
        heading = "All books"

    return render(request, "catalog/book_list.html", {
        "page": page,
        "categories": Category.objects.annotate(book_count=Count("books", filter=Q(books__is_active=True))),
        "query": query,
        "selected_category": category_slug,
        "selected_sort": selected_sort or "popular",
        "series": series, "author": author, "in_stock": in_stock, "sort_options": SORT_OPTIONS,
        "heading": heading,
        "filter_params": {k: v for k, v in request.GET.items() if k != "page"},
    })


def book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related("category"), pk=pk, is_active=True
    )
    return render(request, "catalog/book_detail.html", {"book": book})


@require_POST
def chat(request):
    """JSON endpoint for the chat widget: {"message": "..."} -> {"reply", "books"}."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    message = str(payload.get("message", "")).strip() if isinstance(payload, dict) else ""
    if not message:
        return JsonResponse({"error": "Please type a question."}, status=400)
    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {"error": f"Please keep your question under {MAX_MESSAGE_LENGTH} characters."},
            status=400,
        )

    # Limit calls per browser session to protect the small Gemini quota.
    now = time.time()
    timestamps = request.session.get("chat_timestamps", [])
    timestamps = [stamp for stamp in timestamps if now - stamp < CHAT_RATE_WINDOW_SECONDS]
    if len(timestamps) >= CHAT_RATE_LIMIT:
        return JsonResponse(
            {"error": "You’ve sent several questions recently. Please wait a few minutes and try again."},
            status=429,
        )
    timestamps.append(now)
    request.session["chat_timestamps"] = timestamps

    history = request.session.get("chat_history", [])
    try:
        reply, books = answer(message, history)
    except ChatbotError as error:
        logger.warning("Chatbot error: %s", error)
        return JsonResponse(
            {"error": "Juo'm is unavailable right now. Please try again in a moment."},
            status=503,
        )

    history = history + [
        {"role": "user", "text": message},
        {"role": "model", "text": reply},
    ]
    request.session["chat_history"] = history[-MAX_HISTORY_MESSAGES:]

    return JsonResponse({
        "reply": reply,
        "books": [
            {
                "id": book.pk,
                "title": book.title,
                "price": f"{book.price:,.0f}",
                "url": reverse("catalog:book_detail", args=[book.pk]),
            }
            for book in books
        ],
    })


@require_POST
def chat_reset(request):
    request.session.pop("chat_history", None)
    return JsonResponse({"ok": True})
