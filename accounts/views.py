from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("catalog:book_list")

    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("catalog:book_list")
    return render(request, "accounts/signup.html", {"form": form})
