from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("books/", views.book_list, name="book_list"),
    path("genres/", views.genres, name="genres"),
    path("books/<int:pk>/", views.book_detail, name="book_detail"),
    path("chat/", views.chat, name="chat"),
    path("chat/reset/", views.chat_reset, name="chat_reset"),
]
