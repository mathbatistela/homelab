"""URL map.

Two audiences, two front doors:

    /        Jader's pages -- read-only, big type, built for a phone
    /admin/  the management side, for Matheus

Jader's pages sit at the ROOT on purpose. He types the bare domain and nothing
else; the previous viewer answered that with a 404 for weeks.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("gado.urls")),
]
