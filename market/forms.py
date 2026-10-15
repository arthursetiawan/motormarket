from django import forms

from .models import Motorcycle


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
