import re
from django import forms


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name")
    phone = forms.CharField(max_length=30, label="Phone number")
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Delivery address")
    city = forms.CharField(max_length=100, label="City / State")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Delivery notes (optional)")

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = re.sub(r"\D", "", phone)
        if not re.fullmatch(r"[+\d()\-\s]+", phone) or not 7 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a valid phone number with 7 to 15 digits.")
        return phone
