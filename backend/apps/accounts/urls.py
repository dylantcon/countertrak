from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import logout_view as logout

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('link-steam/', views.link_steam, name='link_steam'),
    path('generate-config/<str:steam_id>/', views.generate_config, name='generate_config'),
]
