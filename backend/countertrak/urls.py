"""
URL configuration for countertrak project.
"""

from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    
    # Main app URLs
    path("", views.landing, name="landing"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("setup-guide/", views.setup_guide, name="setup_guide"),
    
    # App-specific URLs
    path("accounts/", include("apps.accounts.urls")),
    path("matches/", include("apps.matches.urls")),
    path("stats/", include("apps.stats.urls")),
]
