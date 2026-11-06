"""Thin ReefAPI client for the Goodreads endpoints, plus a normaliser.

Design rules:
- No print() or input() here. Failures raise ReefAPIError; callers decide what to do.
- normalise_book() is the ONLY place that knows the raw API field names.
"""
import html
import os
import re

import requests


class ReefAPIError(Exception):
    """Raised when a ReefAPI call fails or returns unusable data."""


def _post(url_env_var, payload):
    api_key = os.getenv("REEFAPI_API_KEY")
    url = os.getenv(url_env_var)
    if not api_key or not url:
        raise ReefAPIError(
            f"Missing REEFAPI_API_KEY or {url_env_var} - check your .env file."
        )

    headers = {"x-api-key": api_key, "content-type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise ReefAPIError("The API response was not valid JSON.") from error
    except requests.Timeout as error:
        raise ReefAPIError("The request timed out.") from error
    except requests.RequestException as error:
        raise ReefAPIError(f"Request failed: {error}") from error

    if not data.get("ok"):
        raise ReefAPIError(f"ReefAPI returned an error: {data.get('error')}")

    return data.get("data") or {}


def fetch_genre(genre):
    """Return the list of {book_id, title, url, cover} for a genre slug."""
    data = _post("REEFAPI_GENRE_URL", {"genre": genre})
    return data.get("books") or []


def fetch_book_detail(book_id):
    """Return the raw 'book' dict for one Goodreads book ID."""
    data = _post(
        "REEFAPI_BOOK_DETAIL_URL",
        {"id": str(book_id), "reviews_limit": 0, "include_pii": False},
    )
    book = data.get("book")
    if not book:
        raise ReefAPIError(f"No book data returned for id {book_id}.")
    return book


def clean_description(text):
    """Strip HTML bits and Windows line breaks from a description."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _squash(value):
    """Collapse runs of whitespace ("John  Green" -> "John Green")."""
    return " ".join(str(value or "").split())


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalise_book(raw):
    """Map a raw book_detail 'book' dict to the fields our Book model uses.

    Reviews, awards, characters, places and buy links are deliberately dropped.
    Output is JSON-safe so it can be saved as a snapshot.
    """
    authors = raw.get("authors") or []
    names = [
        a["name"] for a in authors
        if a.get("name") and a.get("role") in (None, "", "Author")
    ]
    if not names:
        names = [a["name"] for a in authors if a.get("name")]

    series = (raw.get("series") or [{}])[0]
    rating = raw.get("avg_rating")

    return {
        "goodreads_id": str(raw.get("id") or ""),
        "title": _squash(raw.get("title"))[:300],
        "author": _squash(", ".join(names))[:300],
        "description": clean_description(raw.get("description")),
        "genres": list(raw.get("genres") or [])[:10],
        "series_name": _squash(series.get("title"))[:200],
        "series_position": str(series.get("placement") or "")[:10],
        "isbn": raw.get("isbn") or "",
        "isbn13": raw.get("isbn13") or "",
        "publisher": _squash(raw.get("publisher"))[:200],
        "publish_year": _to_int(raw.get("original_publish_year") or raw.get("publish_year")),
        "num_pages": _to_int(raw.get("num_pages")),
        "language": raw.get("language") or "",
        "avg_rating": str(rating) if rating is not None else None,
        "ratings_count": _to_int(raw.get("ratings_count")) or 0,
        "cover_url": raw.get("cover") or "",
        "source_url": raw.get("url") or "",
    }