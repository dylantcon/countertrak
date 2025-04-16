# apps/accounts/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'steam', views.SteamAccountViewSet, basename='steam-account')

urlpatterns = [
    path('', include(router.urls)),
]
