"""
URL configuration for countertrak project.
"""

from django.conf import settings
from django.conf.urls.static import static
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

# serve STATIC_ROOT (favicon + collected assets) without nginx, e.g. in the
# docker demo stack; static() is a no-op when DEBUG is off, so in production
# nginx keeps owning /static/. requires runserver --nostatic, otherwise the
# staticfiles debug handler intercepts /static/ before the URLconf.
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
