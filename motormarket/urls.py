from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from market import views as market_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', market_views.home, name='home'),
    path('market/', include('market.urls')),
    path('accounts/', include('allauth.urls')),
    path('api/', include('market.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
