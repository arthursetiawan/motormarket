from django import forms
from .models import Motorcycle


class MotorcycleForm(forms.ModelForm):
    class Meta:
        model = Motorcycle
        fields = ['title', 'description', 'start_price', 'make', 'year', 'image']
