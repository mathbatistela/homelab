from django.urls import path

from . import views

app_name = "gado"

urlpatterns = [
    path("", views.rebanho, name="rebanho"),
    path("saude", views.saude, name="saude"),
    path("animal/<str:brinco>/", views.animal, name="animal"),
    path("cotacao/", views.cotacao, name="cotacao"),
    path("negocios/", views.negocios, name="negocios"),
]
