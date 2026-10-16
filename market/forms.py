from django.contrib.auth.models import User
from django import forms

from market.services.contact_filter import scrub_public_text

from .models import DealSheet, FleetInquiry, ListingComment, ListingMessage, Motorcycle, PpiRequest, UserRating


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
            "condition_grade",
            "known_flaws",
            "has_reserve",
            "reserve_price",
            "buy_now_price",
            "ends_at",
            "is_dealer",
            "checklist_front",
            "checklist_side",
            "checklist_odometer",
            "checklist_engine",
            "checklist_surat",
            "ppi_available",
            "ppi_notes",
            "seller_phone",
            "seller_wa",
            "image",
        ]
        labels = {
            "title": "Judul",
            "description": "Deskripsi (tanpa nomor / WA / IG)",
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
            "seller_phone": "No. HP (rahasia — tampil setelah pembeli bayar biaya)",
            "seller_wa": "WhatsApp (rahasia — tampil setelah unlock)",
            "image": "Foto",
        }
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Jangan tulis nomor HP / WA / IG di sini — isi di kolom rahasia di bawah.",
                }
            ),
            "plate_number": forms.TextInput(attrs={"placeholder": "B 1234 ABC"}),
            "tax_valid_through": forms.NumberInput(attrs={"placeholder": "2026"}),
            "seller_phone": forms.TextInput(attrs={"placeholder": "08xxxxxxxxxx"}),
            "seller_wa": forms.TextInput(attrs={"placeholder": "08xxxxxxxxxx"}),
        }
        help_texts = {
            "seller_phone": "Tidak ditampilkan di listing publik. Hanya terbuka setelah pembeli bayar biaya platform.",
            "seller_wa": "Sama — tidak publik sampai unlock.",
        }

    def clean_title(self):
        result = scrub_public_text(self.cleaned_data.get("title") or "")
        return result.text

    def clean_description(self):
        result = scrub_public_text(self.cleaned_data.get("description") or "")
        return result.text


class DealSheetForm(forms.ModelForm):
    class Meta:
        model = DealSheet
        fields = [
            "meetup_city",
            "meetup_area",
            "meetup_exact",
            "payment_preference",
            "dp_amount",
            "notes",
        ]
        labels = {
            "meetup_city": "Kota temu",
            "meetup_area": "Area / patokan (publik ke penjual)",
            "meetup_exact": "Alamat / pin exact (terkunci sampai biaya platform dibayar)",
            "payment_preference": "Cara bayar unit",
            "dp_amount": "DP unit (opsional, jika cicilan)",
            "notes": "Catatan",
        }
        widgets = {
            "meetup_city": forms.TextInput(attrs={"placeholder": "Jakarta"}),
            "meetup_area": forms.TextInput(attrs={"placeholder": "Kelapa Gading / mall"}),
            "meetup_exact": forms.TextInput(
                attrs={"placeholder": "Jl. … / patokan exact — terbuka setelah bayar biaya"}
            ),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Jadwal atau syarat nego"}),
            "dp_amount": forms.NumberInput(attrs={"placeholder": "5000000"}),
        }

    def clean_notes(self):
        result = scrub_public_text(self.cleaned_data.get("notes") or "")
        return result.text


class ListingMessageForm(forms.Form):
    body = forms.CharField(
        label="Pesan",
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Chat di NegoMotor saja — jangan kirim nomor / WA / IG",
                "maxlength": 2000,
            }
        ),
        max_length=2000,
    )


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

class CloseDealForm(forms.Form):
    buyer = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Pembeli",
        help_text="Pilih pemenang lelang / pembeli yang sudah deal di NegoMotor.",
    )
    sale_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label="Harga deal (IDR)",
        help_text="Kosongkan untuk memakai bid tertinggi pembeli atau harga ask.",
    )
    notes = forms.CharField(
        max_length=200,
        required=False,
        label="Catatan",
        widget=forms.TextInput(attrs={"placeholder": "Opsional"}),
    )

    def __init__(self, *args, motorcycle: Motorcycle | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if motorcycle is not None:
            bidder_ids = motorcycle.bids.values_list("bidder_id", flat=True).distinct()
            self.fields["buyer"].queryset = User.objects.filter(pk__in=bidder_ids).order_by(
                "username"
            )

class UserRatingForm(forms.ModelForm):
    class Meta:
        model = UserRating
        fields = ["score", "review"]
        labels = {
            "score": "Rating (1–5 bintang)",
            "review": "Ulasan singkat (opsional)",
        }
        widgets = {
            "score": forms.NumberInput(attrs={"min": 1, "max": 5, "step": 1}),
            "review": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 400,
                    "placeholder": "Contoh: Penjual responsif, motor sesuai deskripsi.",
                }
            ),
        }

class ProxyBidForm(forms.Form):
    max_amount = forms.DecimalField(
        min_value=0,
        max_digits=12,
        decimal_places=0,
        label="Tawaran maksimum (proxy)",
        help_text="Sistem menawar otomatis hingga batas ini.",
        widget=forms.NumberInput(attrs={"placeholder": "Contoh: 18500000", "step": "50000"}),
    )

class ListingCommentForm(forms.ModelForm):
    class Meta:
        model = ListingComment
        fields = ["body"]
        labels = {"body": "Tanya penjual / komentar"}
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Tanya soal surat, service, atau kekurangan…"}
            ),
        }

class PpiRequestForm(forms.ModelForm):
    class Meta:
        model = PpiRequest
        fields = ["note"]
        labels = {"note": "Catatan cek unit"}
        widgets = {
            "note": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Kapan dan di mana Anda ingin cek unit?"}
            ),
        }
