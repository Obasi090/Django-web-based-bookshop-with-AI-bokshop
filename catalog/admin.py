from django.contrib import admin

from .models import Book, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "price", "stock", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("title", "author", "isbn13")
    list_editable = ("price", "stock", "is_active")