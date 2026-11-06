from decimal import Decimal

from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):
    # --- Identity / source -------------------------------------------------
    goodreads_id = models.CharField(max_length=20, unique=True)
    source_url = models.URLField(max_length=500, blank=True)

    # --- Descriptive data (filled by the import, refreshed on re-import) ---
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="books",
    )
    genres = models.JSONField(default=list, blank=True)
    series_name = models.CharField(max_length=200, blank=True)
    series_position = models.CharField(max_length=10, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    isbn13 = models.CharField(max_length=20, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    publish_year = models.PositiveSmallIntegerField(null=True, blank=True)
    num_pages = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, blank=True)
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    ratings_count = models.PositiveIntegerField(default=0)
    cover_url = models.URLField(max_length=500, blank=True)

    # --- Shop-owned data (the import NEVER overwrites these) ---------------
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def in_stock(self):
        return self.stock > 0


class BookEmbedding(models.Model):
    """Vector used by the chatbot to find books close in meaning to a question."""

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="embedding")
    vector = models.JSONField()
    model_name = models.CharField(max_length=100)
    text_hash = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Embedding for {self.book}"