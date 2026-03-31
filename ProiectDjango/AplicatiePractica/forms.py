from django import forms
from .models import Cheltuiala, Categorie


class CheltuialaForm(forms.ModelForm):
    class Meta:
        model = Cheltuiala
        fields = ['titlu', 'suma', 'categorie', 'data', 'descriere']
        widgets = {
            'titlu': forms.TextInput(attrs={'class': 'form-control'}),
            'suma': forms.NumberInput(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'descriere': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['nume', 'descriere', 'culoare']
        widgets = {
            'culoare': forms.TextInput(attrs={'type': 'color'}),
        }