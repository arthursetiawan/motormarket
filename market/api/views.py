from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from market.models import Motorcycle, Bid
from .serializers import MotorcycleSerializer, BidSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import filters


class MotorcycleViewSet(viewsets.ModelViewSet):
    queryset = Motorcycle.objects.all().order_by('-created_at')
    serializer_class = MotorcycleSerializer
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'make']
    ordering_fields = ['start_price', 'created_at']

    @action(detail=True, methods=['get'])
    def bids(self, request, pk=None):
        motorcycle = self.get_object()
        bids = motorcycle.bids.all().order_by('-amount')
        serializer = BidSerializer(bids, many=True)
        return Response(serializer.data)


class BidViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Bid.objects.all().order_by('-created_at')
    serializer_class = BidSerializer

    def perform_create(self, serializer):
        serializer.save(bidder=self.request.user)
