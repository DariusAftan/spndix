from django import forms
from .models import Cheltuiala, Categorie, Budget, LUNA_CHOICES, UserProfile
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


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['categorie', 'suma_limita', 'luna', 'an']
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'suma_limita': forms.NumberInput(attrs={'class': 'form-control'}),
            'luna': forms.Select(choices=LUNA_CHOICES, attrs={'class': 'form-select'}),
            'an': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['tip_gospodarie', 'nr_persoane', 'are_copii', 'venit_lunar', 'obiectiv']
        widgets = {
            'tip_gospodarie': forms.Select(attrs={'class': 'form-select'}),
            'nr_persoane': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'are_copii': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'venit_lunar': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'obiectiv': forms.Select(attrs={'class': 'form-select'}),
        }