# UI map

## Pages

- `/` is the home page with catalogue shelves and the Juo'm entry point.
- `/books/` is the searchable and filterable catalogue.
- `/books/<id>/` is a book detail and purchase page.
- `/genres/` lists the shop's categories.
- `/cart/`, `/checkout/`, and `/orders/` keep the existing cart and pay-on-delivery flow.

## Design tokens

The paper, surface, espresso, teal, green, and amber colours are CSS custom properties in `catalog/static/catalog/css/theme.css`. Headings use Georgia and body copy uses system fonts so no web font download is needed.

## Shared components

`_header.html`, `_footer.html`, and `_messages.html` form the shared frame. `_book_cover.html`, `_stars.html`, `_book_card.html`, `_shelf.html`, and `_pagination.html` keep catalogue pages consistent. The stars tag clamps ratings to 0–5 and exposes the rating as an accessible label.

## Deliberate omissions

The shop has no customer reviews, user ratings, author biographies, friends, or followers, so the interface does not invent those features. Book metadata and public ratings are attributed to Goodreads via the third-party import service. Chat recommendations add books to the cart; order placement remains in checkout.
