from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_cheltuieli, name='lista_cheltuieli'),
    path('adauga/', views.adauga_cheltuiala, name='adauga_cheltuiala'),
    path('editeaza/<int:pk>/', views.editeaza_cheltuiala, name='editeaza_cheltuiala'),
    path('sterge/<int:pk>/', views.sterge_cheltuiala, name='sterge_cheltuiala'),
    path('register/', views.register, name='register'), 
]