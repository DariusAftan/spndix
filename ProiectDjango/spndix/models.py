from django.db import models
from django.contrib.auth.models import User


LUNA_CHOICES = [
    (1, 'Ianuarie'),
    (2, 'Februarie'),
    (3, 'Martie'),
    (4, 'Aprilie'),
    (5, 'Mai'),
    (6, 'Iunie'),
    (7, 'Iulie'),
    (8, 'August'),
    (9, 'Septembrie'),
    (10, 'Octombrie'),
    (11, 'Noiembrie'),
    (12, 'Decembrie'),
]


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


class Budget(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE)
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name='bugete')
    suma_limita = models.DecimalField(max_digits=10, decimal_places=2)
    luna = models.PositiveSmallIntegerField(choices=LUNA_CHOICES)
    an = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.categorie} - {self.get_luna_display()} {self.an} - {self.suma_limita} RON"

    class Meta:
        verbose_name = "Buget"
        verbose_name_plural = "Bugete"
        ordering = ['-an', '-luna', 'categorie__nume']
        constraints = [
            models.UniqueConstraint(
                fields=['utilizator', 'categorie', 'luna', 'an'],
                name='unique_budget_per_category_month_year',
            )
        ]


class AIAnaliza(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE)
    luna = models.PositiveSmallIntegerField(choices=LUNA_CHOICES)
    an = models.PositiveSmallIntegerField()
    continut_analiza = models.TextField()
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analiză AI - {self.utilizator.username} - {self.get_luna_display()} {self.an}"

    class Meta:
        verbose_name = "Analiză AI"
        verbose_name_plural = "Analize AI"
        ordering = ['-an', '-luna', '-creat_la']
        constraints = [
            models.UniqueConstraint(
                fields=['utilizator', 'luna', 'an'],
                name='unique_ai_analysis_per_month_year',
            )
        ]