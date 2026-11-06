# Final acceptance checklist

Status reflects checks performed while preparing this project archive. A source-code review or Python syntax compilation is not the same as running Django or testing in a browser.

| Acceptance item | Status | Evidence / remaining action |
|---|---|---|
| `python manage.py check` is clean | Could not verify | Django is not installed in the preparation environment, and package installation could not reach PyPI. Run from the project's Windows virtual environment. |
| `python manage.py makemigrations --check --dry-run` is clean | Could not verify | A hand-written initial migration was added for the new `orders` app. Run the command locally and resolve any reported model/migration differences. |
| `python manage.py test` passes | Could not verify | Automated tests have been added under `catalog/tests/` and `orders/tests/`; they were not executed because Django and `google-genai` are unavailable here. |
| Complete browser journey works | Could not verify | Browse/search/filter and chat foundation existed previously; accounts/cart/checkout/order workflows are now implemented but need a browser run on the developer's machine. |
| No secrets in Git | Done for tracked files; archive hygiene corrected | `.env` and `db.sqlite3` are ignored and were not listed by `git ls-files`. The delivered ZIP excludes `.env`, the database, and `.git`. Rotate any active keys that were present in the originally uploaded archive. |
| README setup verified on a clean virtual environment | Not done | Setup steps are documented but could not be executed in this network-restricted environment. |
| Real Gemini behaviour after changes | Could not verify | Do not run the live embedding/chat evaluation without checking the key and quota. The prior `chat_eval_results.md` is historical, not a test of these latest changes. |
| Browser behaviour with real Bootstrap assets | Could not verify | Bootstrap CDN download was blocked by unavailable DNS. `base.html` contains a TODO and `README.md` gives the exact paths and download URLs for local assets. |
| ReefAPI import against the live service | Not done here by design | Tests should mock ReefAPI; use the snapshot for a repeatable demo. |
