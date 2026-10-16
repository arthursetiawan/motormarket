from rest_framework import serializers
from sorl.thumbnail import get_thumbnail

from market.models import Bid, ListingPrediction, Motorcycle


class ListingPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingPrediction
        fields = [
            "predicted_price",
            "deal_score",
            "deal_label",
            "model_version",
            "scored_at",
            "trust_score",
            "trust_label",
            "trust_flags",
            "trust_completeness",
            "anomaly_score",
            "anomaly_label",
            "anomaly_flags",
            "anomaly_confidence",
            "anomaly_peer_n",
            "anomaly_peer_source",
        ]


class MotorcycleSerializer(serializers.ModelSerializer):
    seller = serializers.StringRelatedField()
    thumbnail = serializers.SerializerMethodField()
    prediction = ListingPredictionSerializer(read_only=True)

    class Meta:
        model = Motorcycle
        fields = [
            "id",
            "title",
            "description",
            "make",
            "model_name",
            "year",
            "mileage_km",
            "engine_cc",
            "condition",
            "city",
            "owners_count",
            "start_price",
            "image",
            "thumbnail",
            "created_at",
            "seller",
            "prediction",
        ]

    def get_thumbnail(self, obj):
        if obj.image:
            try:
                t = get_thumbnail(obj.image, "600x400", crop="center", quality=85)
                return t.url
            except Exception:
                return obj.image.url
        return None


class BidSerializer(serializers.ModelSerializer):
    bidder = serializers.StringRelatedField()

    class Meta:
        model = Bid
        fields = ["id", "motorcycle", "bidder", "amount", "created_at"]


class PriceQuoteSerializer(serializers.Serializer):
    make = serializers.CharField()
    model_name = serializers.CharField()
    year = serializers.IntegerField(min_value=2008, max_value=2026)
    mileage_km = serializers.IntegerField(min_value=0)
    engine_cc = serializers.IntegerField(min_value=50)
    condition = serializers.ChoiceField(choices=["excellent", "good", "fair", "poor"])
    city = serializers.CharField()
    owners_count = serializers.IntegerField(min_value=1, max_value=8)
    asking_price = serializers.FloatField(min_value=1)
    fuel_type = serializers.CharField(required=False, default="petrol")
    transmission = serializers.CharField(required=False, default="automatic")
    segment = serializers.CharField(required=False, default="scooter")
