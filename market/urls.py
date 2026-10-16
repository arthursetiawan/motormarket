from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('insights/', views.insights, name='insights'),
    path('fleets/', views.fleets, name='fleets'),
    path('terms/', views.terms, name='terms'),
    path('create/', views.create_listing, name='create_listing'),
    path('suggest-ask/', views.suggest_ask, name='suggest_ask'),
    path('profile/', views.profile, name='profile'),
    path('motorcycle/<int:pk>/', views.motorcycle_detail, name='motorcycle_detail'),
    path('motorcycle/<int:pk>/bid/', views.place_bid, name='place_bid'),
    path('motorcycle/<int:pk>/deal/', views.submit_deal_sheet, name='submit_deal_sheet'),
    path('motorcycle/<int:pk>/message/', views.send_listing_message, name='send_listing_message'),
    path('motorcycle/<int:pk>/pay-fee/', views.pay_platform_fee, name='pay_platform_fee'),
    path('motorcycle/<int:pk>/close-deal/', views.mark_deal_closed, name='mark_deal_closed'),
    path('motorcycle/<int:pk>/close-sold/', views.close_listing_deal, name='close_listing_deal'),
    path('deals/<int:deal_id>/rate/', views.rate_deal, name='rate_deal'),
    path('u/<str:username>/', views.public_profile, name='public_profile'),
    path('motorcycle/<int:pk>/report-bypass/', views.report_bypass, name='report_bypass'),
]
