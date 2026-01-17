# api/urls.py
from django.urls import path, include

urlpatterns = [
    path('accounts/', include('apps.accounts.urls')),
    path('matches/', include('apps.matches.urls')),
    path('stats/', include('apps.stats.urls')),
]
