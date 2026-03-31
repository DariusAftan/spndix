from django.db import models
from django.contrib.auth.models import User


class Categorie(models.Model):
    nume = models.CharField(max_length=100)
    descriere = models.TextField(blank=True, null=True)
    culoare = models.CharField(max_length=7, default='#3498db')  # hex color

    def __str__(self):
        return self.nume

    class Meta:
        verbose_name_plural = "Categorii"


class Cheltuiala(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True)
    titlu = models.CharField(max_length=200)
    suma = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    descriere = models.TextField(blank=True, null=True)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titlu} - {self.suma} RON"

    class Meta:
        verbose_name_plural = "Cheltuieli"
        ordering = ['-data']