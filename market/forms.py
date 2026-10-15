from django import forms

from .models import FleetInquiry, Motorcycle


class MotorcycleForm(forms.ModelForm):
    class Meta:
        model = Motorcycle
        fields = [
            "title",
            "description",
            "start_price",
            "make",
            "model_name",
            "year",
            "mileage_km",
            "engine_cc",
            "condition",
            "city",
            "owners_count",
            "transmission",
            "image",
        ]


class FleetInquiryForm(forms.ModelForm):
    class Meta:
        model = FleetInquiry
        fields = [
            "company_name",
            "contact_name",
            "email",
            "city",
            "use_case",
            "intent",
            "fleet_size",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Model mix, cities, or when you need them"}),
            "company_name": forms.TextInput(attrs={"placeholder": "Surya Courier"}),
            "contact_name": forms.TextInput(attrs={"placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@company.com"}),
            "city": forms.TextInput(attrs={"placeholder": "Jakarta"}),
        }
        labels = {
            "company_name": "Company",
            "contact_name": "Your name",
            "email": "Work email",
            "city": "City you operate in",
            "use_case": "What will the bikes do?",
            "intent": "Buy or rent",
            "fleet_size": "How many bikes?",
            "notes": "Anything else",
        }

    def clean_fleet_size(self):
        size = self.cleaned_data["fleet_size"]
        if size < 5 or size > 500:
            raise forms.ValidationError("Fleet size should be between 5 and 500 bikes.")
        return size
