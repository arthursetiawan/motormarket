from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_listing, name='create_listing'),
    path('profile/', views.profile, name='profile'),
    path('motorcycle/<int:pk>/', views.motorcycle_detail, name='motorcycle_detail'),
    path('motorcycle/<int:pk>/bid/', views.place_bid, name='place_bid'),
]
