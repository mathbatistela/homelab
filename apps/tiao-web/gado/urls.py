from django.urls import path

from . import views

app_name = "gado"

urlpatterns = [
    path("", views.rebanho, name="rebanho"),
]
