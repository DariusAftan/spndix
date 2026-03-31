from django import forms
from .models import Cheltuiala, Categorie
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'

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