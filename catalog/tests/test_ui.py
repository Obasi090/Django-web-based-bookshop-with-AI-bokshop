from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase


class StarsTagTests(SimpleTestCase):
    def render_stars(self, value):
        return Template("{% load shop_ui %}{% stars value %}").render(Context({"value": value}))

    def test_fractional_rating_is_displayed_with_accessible_label(self):
        html = self.render_stars(Decimal("4.36"))
        self.assertIn('aria-label="Rated 4.36 out of 5"', html)
        self.assertIn("87.2%", html)

    def test_none_zero_and_invalid_rating_render_empty_stars(self):
        for value in (None, 0, "not a rating"):
            with self.subTest(value=value):
                self.assertIn('aria-label="Rated 0.00 out of 5"', self.render_stars(value))

    def test_rating_is_clamped_to_five(self):
        self.assertIn('aria-label="Rated 5.00 out of 5"', self.render_stars("6"))
