from rest_framework import serializers
from market.models import Motorcycle, Bid
from sorl.thumbnail import get_thumbnail


class MotorcycleSerializer(serializers.ModelSerializer):
    seller = serializers.StringRelatedField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Motorcycle
        fields = ['id', 'title', 'description', 'make', 'year', 'start_price', 'image', 'thumbnail', 'created_at', 'seller']

    def get_thumbnail(self, obj):
        if obj.image:
            try:
                t = get_thumbnail(obj.image, '600x400', crop='center', quality=85)
                return t.url
            except Exception:
                return obj.image.url
        return None


class BidSerializer(serializers.ModelSerializer):
    bidder = serializers.StringRelatedField()

    class Meta:
        model = Bid
        fields = ['id', 'motorcycle', 'bidder', 'amount', 'created_at']
