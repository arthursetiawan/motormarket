from django import forms

from .models import DealSheet, FleetInquiry, Motorcycle


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
            "fuel_type",
            "stnk_status",
            "bpkb_status",
            "pajak_mati",
            "tax_valid_through",
            "plate_number",
            "image",
        ]
        labels = {
            "title": "Judul",
            "description": "Deskripsi",
            "start_price": "Harga awal (Rp)",
            "make": "Merek",
            "model_name": "Tipe / model",
            "year": "Tahun",
            "mileage_km": "Kilometer",
            "engine_cc": "CC",
            "condition": "Kondisi",
            "city": "Kota",
            "owners_count": "Jumlah pemilik",
            "transmission": "Transmisi",
            "fuel_type": "Bahan bakar",
            "stnk_status": "STNK",
            "bpkb_status": "BPKB",
            "pajak_mati": "Pajak mati",
            "tax_valid_through": "Pajak berlaku sampai (tahun)",
            "plate_number": "Nomor polisi (plat)",
            "image": "Foto",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "plate_number": forms.TextInput(attrs={"placeholder": "B 1234 ABC"}),
            "tax_valid_through": forms.NumberInput(attrs={"placeholder": "2026"}),
        }


class DealSheetForm(forms.ModelForm):
    class Meta:
        model = DealSheet
        fields = [
            "meetup_city",
            "meetup_area",
            "payment_preference",
            "dp_amount",
            "notes",
        ]
        labels = {
            "meetup_city": "Kota temu",
            "meetup_area": "Area / patokan",
            "payment_preference": "Cara bayar",
            "dp_amount": "DP (opsional, jika cicilan)",
            "notes": "Catatan",
        }
        widgets = {
            "meetup_city": forms.TextInput(attrs={"placeholder": "Jakarta"}),
            "meetup_area": forms.TextInput(attrs={"placeholder": "Mall / Indomaret / rumah"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Jadwal atau syarat nego"}),
            "dp_amount": forms.NumberInput(attrs={"placeholder": "5000000"}),
        }


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
            "notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Campuran model, kota, BPKB atas nama PT, atau jadwal"}
            ),
            "company_name": forms.TextInput(attrs={"placeholder": "Surya Courier"}),
            "contact_name": forms.TextInput(attrs={"placeholder": "Nama Anda"}),
            "email": forms.EmailInput(attrs={"placeholder": "anda@perusahaan.com"}),
            "city": forms.TextInput(attrs={"placeholder": "Jakarta"}),
        }
        labels = {
            "company_name": "Perusahaan",
            "contact_name": "Nama Anda",
            "email": "Email kerja",
            "city": "Kota operasi",
            "use_case": "Unit dipakai untuk?",
            "intent": "Beli atau sewa",
            "fleet_size": "Berapa unit?",
            "notes": "Catatan lain",
        }

    def clean_fleet_size(self):
        size = self.cleaned_data["fleet_size"]
        if size < 5 or size > 500:
            raise forms.ValidationError("Ukuran armada harus antara 5 dan 500 unit.")
        return size
