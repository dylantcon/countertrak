# apps/stats/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'player-match', views.PlayerMatchStatViewSet, basename='player-match-stat')
router.register(r'player-round', views.PlayerRoundStateViewSet, basename='player-round-state')
router.register(r'weapons', views.WeaponViewSet, basename='weapon')
router.register(r'analytics', views.AnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('', include(router.urls)),
]
