# The Bravemind's Hub

**Project title:** Design and Implementation of a Web-Based Bookshop Platform with Integrated AI Chatbot.

A final-year Computer Science project: a Django-based web bookshop with an integrated AI librarian chatbot. Customers can browse a local book catalogue, ask natural-language questions about books, register, manage a session cart, place a simulated pay-on-delivery order, and view their own orders. The shop owner manages books, prices, stock and orders in Django admin.

## Technology

- Python and Django 6.1.2
- SQLite
- Django templates, Bootstrap 5.3.3 and vanilla JavaScript
- ReefAPI/Goodreads metadata import (optional after a snapshot is available)
- Gemini embeddings and generation for retrieval-augmented generation (RAG)
- `requests`, `python-dotenv`, `google-genai`

## Setup on Windows (PowerShell)

Run these commands from the folder containing `manage.py` (`PythonProject`). Use your own virtual environment and never share `.env`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace `DJANGO_SECRET_KEY` with a long random secret. Add API keys only if you will use those services. Keep `.env` private.

```powershell
python manage.py check
python manage.py migrate
python manage.py createsuperuser
```

### Load books

**Offline/demo route (preferred for a repeatable defence):**

```powershell
python manage.py import_books --from-snapshot catalog/fixtures/books_snapshot.json
```

This uses the saved JSON snapshot and does not call ReefAPI. The import command creates placeholder prices and stock for new books. These are demo values, not real shop prices or inventory. Re-importing book metadata does not overwrite the shop's prices, stock or active flag.

**Optional live import:** only when you have configured valid ReefAPI credentials and have checked your remaining credits:

```powershell
python manage.py import_books --genre fantasy --genre mystery --genre romance --genre science-fiction --genre young-adult --per-genre 25 --save-snapshot catalog/fixtures/books_snapshot.json
```

Embedding requires Gemini quota. Do not run it repeatedly if the API returns 429; wait at least a minute, then rerun the command. It skips books whose source text has not changed.

```powershell
python manage.py embed_books
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Sign in to `/admin/` with the superuser account to manage catalogue records and orders.

## Environment variables

| Variable | Required for | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django startup | Private Django signing key. Never commit it. |
| `DJANGO_DEBUG` | Optional | Set to `True` only for local development. Defaults to `False`. |
| `REEFAPI_API_KEY` | Live import only | ReefAPI key. |
| `REEFAPI_GENRE_URL` | Live import only | ReefAPI genre endpoint URL. |
| `REEFAPI_BOOK_DETAIL_URL` | Live import only | ReefAPI book-detail endpoint URL. |
| `GEMINI_API_KEY` | Embeddings/chat | Gemini API key. |
| `GEMINI_CHAT_MODEL` | Optional | Chat model override; otherwise the model configured in `catalog/services/chatbot.py` is used. |
| `GEMINI_EMBEDDING_MODEL` | Optional | Embedding model override; use the model that matches stored vectors. The current design expects `gemini-embedding-001` and 768 dimensions. |

## Useful commands

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py import_books --from-snapshot catalog/fixtures/books_snapshot.json
python manage.py embed_books
python manage.py ask_librarian "Recommend a fantasy book"
python manage.py chat_eval --delay 6 --out chat_eval_results.md
```

`ask_librarian`, `embed_books`, and `chat_eval` call Gemini and can consume quota. They are deliberately not part of the automated test suite. The automated tests use fakes/mocks and should not call external services.

## Bootstrap offline note

The environment used to prepare this repository could not reach jsDelivr, so the existing Bootstrap CDN references remain in `catalog/templates/catalog/base.html`. To make the interface work without internet, download these two files when online and save them at the exact paths shown:

1. `https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css` → `catalog/static/catalog/vendor/bootstrap.min.css`
2. `https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js` → `catalog/static/catalog/vendor/bootstrap.bundle.min.js`

Then replace the CDN `<link>` and `<script>` references in `base.html` with `{% load static %}`, `{% static 'catalog/vendor/bootstrap.min.css' %}`, and `{% static 'catalog/vendor/bootstrap.bundle.min.js' %}` respectively. Do not create empty files as substitutes. Goodreads cover images are still remote; a fallback message is shown when a cover fails to load.

## Troubleshooting

- **`KeyError: 'DJANGO_SECRET_KEY'`:** make sure `.env` exists beside `manage.py`, contains `DJANGO_SECRET_KEY=...`, and you launched the command from the project root.
- **`Unknown command`:** check that command folders are Python packages and contain `__init__.py`, especially `catalog/management/` and `catalog/management/commands/`.
- **Gemini 429 / `RESOURCE_EXHAUSTED`:** quota was exceeded. Wait at least one minute before retrying. Do not repeatedly restart a full embedding run; the command skips unchanged embeddings already saved.
- **No embeddings found:** run `python manage.py embed_books` with valid Gemini credentials/quota before testing live chat.
- **Chatbot says it is unavailable:** check the Gemini key, configured model, quota, network and server logs. Do not print API keys in logs or screenshots.
- **No cover appears:** remote Goodreads cover hosts may be unavailable; the book remains usable and a fallback placeholder is shown.

## Design summary

Book metadata is imported into SQLite once; catalogue pages do not call ReefAPI. The shop owns price and stock. For a chatbot message, the app embeds the question, retrieves up to five semantically similar active books, adds their current database price and stock to the model context, and displays the answer plus matching book links. The chatbot is advisory only and cannot place orders or accept payment.

See [`docs/architecture.md`](docs/architecture.md), [`docs/limitations.md`](docs/limitations.md), and [`docs/chatbot_test_cases.md`](docs/chatbot_test_cases.md).
