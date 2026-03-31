from django.contrib import admin
from .models import Categorie, Cheltuiala


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