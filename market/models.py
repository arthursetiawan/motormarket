from django.db import models
from django.contrib.auth.models import User


class Motorcycle(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    make = models.CharField(max_length=100, blank=True, null=True)
    year = models.PositiveSmallIntegerField(blank=True, null=True)
    image = models.ImageField(upload_to='motorcycles/', blank=True, null=True)

    def __str__(self):
        return self.title


class Bid(models.Model):
    motorcycle = models.ForeignKey(Motorcycle, related_name='bids', on_delete=models.CASCADE)
    bidder = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bidder.username} - {self.amount}"
