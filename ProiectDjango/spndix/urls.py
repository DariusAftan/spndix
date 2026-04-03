from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('cheltuieli/', views.lista_cheltuieli, name='lista_cheltuieli'),
    path('cheltuieli/export/excel/', views.export_cheltuieli_excel, name='export_cheltuieli_excel'),
    path('cheltuieli/export/pdf/', views.export_cheltuieli_pdf, name='export_cheltuieli_pdf'),
    path('analiza/', views.analiza_ai, name='analiza_ai'),
    path('alerte/citita/<int:pk>/', views.marca_citita, name='marca_citita'),
    path('scaneaza-bon/', views.scaneaza_bon, name='scaneaza_bon'),
    path('goals/', views.lista_goals, name='lista_goals'),
    path('goals/adauga/', views.adauga_goal, name='adauga_goal'),
    path('goals/editeaza/<int:pk>/', views.editeaza_goal, name='editeaza_goal'),
    path('goals/sterge/<int:pk>/', views.sterge_goal, name='sterge_goal'),
    path('goals/contributie/<int:pk>/', views.adauga_contributie, name='adauga_contributie'),
    path('adauga/', views.adauga_cheltuiala, name='adauga_cheltuiala'),
    path('editeaza/<int:pk>/', views.editeaza_cheltuiala, name='editeaza_cheltuiala'),
    path('sterge/<int:pk>/', views.sterge_cheltuiala, name='sterge_cheltuiala'),
    path('bugete/', views.lista_bugete, name='lista_bugete'),
    path('bugete/adauga/', views.adauga_buget, name='adauga_buget'),
    path('bugete/editeaza/<int:pk>/', views.editeaza_buget, name='editeaza_buget'),
    path('bugete/sterge/<int:pk>/', views.sterge_buget, name='sterge_buget'),
    path('profil/', views.profil, name='profil'),
    path('register/', views.register, name='register'), 
]