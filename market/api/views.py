import json

import pandas as pd
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from market.models import Bid, Motorcycle
from market.services.fleet_intel import market_coverage, recommend_pack
from market.services.pricing import listing_to_record
from market.services.trust import listing_trust
from ml.catalog import CATALOG
from ml.paths import METRICS_PATH
from ml.score import ModelNotTrainedError, deal_label, deal_score, predict_prices

from .serializers import BidSerializer, MotorcycleSerializer, PriceQuoteSerializer


class MotorcycleViewSet(viewsets.ModelViewSet):
    queryset = Motorcycle.objects.select_related("prediction", "seller").order_by("-created_at")
    serializer_class = MotorcycleSerializer
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "make", "model_name", "city"]
    ordering_fields = ["start_price", "created_at", "year", "mileage_km"]

    @action(detail=True, methods=["get"])
    def bids(self, request, pk=None):
        motorcycle = self.get_object()
        bids = motorcycle.bids.all().order_by("-amount")
        serializer = BidSerializer(bids, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def fair_value(self, request, pk=None):
        bike = self.get_object()
        try:
            pred = float(predict_prices(pd.DataFrame([listing_to_record(bike)]))[0])
        except ModelNotTrainedError:
            return Response({"detail": "model not trained"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        asking = float(bike.start_price)
        score = deal_score(asking, pred)
        return Response(
            {
                "motorcycle_id": bike.pk,
                "asking_price": asking,
                "predicted_price": round(pred, 0),
                "deal_score": round(score, 2),
                "deal_label": deal_label(score),
            }
        )

    @action(detail=True, methods=["get"])
    def trust(self, request, pk=None):
        bike = self.get_object()
        report = listing_trust(bike)
        return Response({"motorcycle_id": bike.pk, **report.to_dict()})


class BidViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Bid.objects.all().order_by("-created_at")
    serializer_class = BidSerializer

    def perform_create(self, serializer):
        serializer.save(bidder=self.request.user)


class PricePredictView(APIView):
    def post(self, request):
        ser = PriceQuoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = dict(ser.validated_data)
        if payload.get("segment") in (None, "scooter"):
            match = next(
                (
                    row
                    for row in CATALOG
                    if row["make"].lower() == payload["make"].lower()
                    and row["model_name"].lower() == payload["model_name"].lower()
                ),
                None,
            )
            if match:
                payload["segment"] = match["segment"]
                payload["engine_cc"] = payload.get("engine_cc") or match["engine_cc"]
                payload["fuel_type"] = match["fuel_type"]
                payload["transmission"] = match["transmission"]
        try:
            pred = float(predict_prices(pd.DataFrame([payload]))[0])
        except ModelNotTrainedError:
            return Response({"detail": "model not trained"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        asking = float(payload["asking_price"])
        score = deal_score(asking, pred)
        return Response(
            {
                "predicted_price": round(pred, 0),
                "asking_price": asking,
                "deal_score": round(score, 2),
                "deal_label": deal_label(score),
                "currency": "IDR",
            }
        )


class ModelMetricsView(APIView):
    def get(self, request):
        if not METRICS_PATH.exists():
            return Response({"detail": "no metrics yet"}, status=status.HTTP_404_NOT_FOUND)
        return Response(json.loads(METRICS_PATH.read_text(encoding="utf-8")))


class FleetPackView(APIView):
    """Recommend a buy/rent pack for a fleet program from the live book."""

    def get(self, request):
        program = request.query_params.get("program", "delivery")
        size = request.query_params.get("size", "10")
        city = request.query_params.get("city") or None
        try:
            size_i = int(size)
        except (TypeError, ValueError):
            return Response({"detail": "size must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        pack = recommend_pack(program, size=size_i, preferred_city=city)
        if pack is None:
            return Response({"detail": "unknown program"}, status=status.HTTP_404_NOT_FOUND)
        # JSON-safe: drop nested program image path noise already present
        payload = dict(pack)
        payload["program"] = {
            "slug": pack["program"]["slug"],
            "name": pack["program"]["name"],
            "models": pack["program"]["models"],
            "cities": pack["program"]["cities"],
        }
        return Response(payload)


class FleetCoverageView(APIView):
    def get(self, request):
        return Response(market_coverage())
