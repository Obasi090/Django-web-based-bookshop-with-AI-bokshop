from django.urls import path
from django.contrib.auth import urls as auth_urls
from . import views

app_name = "accounts"
urlpatterns = [
    path("signup/", views.signup, name="signup"),
] + auth_urls.urlpatterns
