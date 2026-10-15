from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BidViewSet,
    FleetCoverageView,
    FleetPackView,
    ModelMetricsView,
    MotorcycleViewSet,
    PricePredictView,
)

router = DefaultRouter()
router.register(r"motorcycles", MotorcycleViewSet)
router.register(r"bids", BidViewSet)

urlpatterns = [
    path("pricing/predict/", PricePredictView.as_view(), name="price-predict"),
    path("pricing/metrics/", ModelMetricsView.as_view(), name="price-metrics"),
    path("fleets/pack/", FleetPackView.as_view(), name="fleet-pack"),
    path("fleets/coverage/", FleetCoverageView.as_view(), name="fleet-coverage"),
    path("", include(router.urls)),
]
