from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MotorcycleViewSet, BidViewSet

router = DefaultRouter()
router.register(r'motorcycles', MotorcycleViewSet)
router.register(r'bids', BidViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
