from django.contrib import admin
from .models import Categorie, Cheltuiala, Budget, AIAnaliza


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nume', 'descriere', 'culoare')
    search_fields = ('nume',)


@admin.register(Cheltuiala)
class CheltuialaAdmin(admin.ModelAdmin):
    list_display = ('titlu', 'suma', 'categorie', 'utilizator', 'data')
    list_filter = ('categorie', 'data', 'utilizator')
    search_fields = ('titlu', 'descriere')
    date_hierarchy = 'data'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('categorie', 'utilizator', 'suma_limita', 'luna', 'an')
    list_filter = ('categorie', 'luna', 'an', 'utilizator')
    search_fields = ('categorie__nume', 'utilizator__username')


@admin.register(AIAnaliza)
class AIAnalizaAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'luna', 'an', 'creat_la')
    list_filter = ('luna', 'an', 'utilizator')
    search_fields = ('utilizator__username', 'continut_analiza')