from django.urls import path

from . import views

app_name = "gado"

urlpatterns = [
    path("", views.rebanho, name="rebanho"),
    path("saude", views.saude, name="saude"),
    path("animal/<str:brinco>/", views.animal, name="animal"),
    # Um bicho sem brinco não tem endereço natural; o id serve.
    path("bicho/<int:pk>/", views.animal_por_id, name="animal_por_id"),
    path("cotacao/", views.cotacao, name="cotacao"),
    path("negocios/", views.negocios, name="negocios"),
]
