# apps/matches/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.MatchViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('delete/<str:match_id>/', views.delete_match, name='delete_match'),
]
