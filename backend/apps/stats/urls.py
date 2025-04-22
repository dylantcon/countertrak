from django.urls import path
from . import views, views_query

urlpatterns = [
    path('', views.stats_home, name='stats_home'),
    path('player/<str:steam_id>/', views.player_stats, name='player_stats'),
    path('player/', views.player_stats, name='my_stats'),
    path('match/<str:match_id>/', views.match_detail, name='match_detail'),
    path('weapon-analysis/<str:steam_id>/', views.weapon_analysis, name='weapon_analysis'),
    path('weapon-analysis/', views.weapon_analysis, name='my_weapon_analysis'),
    path('query-explorer/', views_query.query_explorer, name='query_explorer'),
]
