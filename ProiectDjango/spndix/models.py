from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta


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


TIP_GOSPODARIE_CHOICES = [
    ('single', 'Single'),
    ('cuplu', 'Cuplu'),
    ('familie_copii', 'Familie cu copii'),
    ('colegi_casa', 'Colegi de casă'),
]


OBIECTIV_CHOICES = [
    ('economisire', 'Economisire'),
    ('stabilitate', 'Stabilitate'),
    ('investitii', 'Investiții'),
    ('iesire_datorii', 'Ieșire din datorii'),
]


PLAN_CHOICES = [
    ('free', 'Free'),
    ('pro', 'Pro'),
    ('family', 'Family'),
]


TIP_ALERTA_CHOICES = [
    ('depasire_iminenta', 'Depășire iminentă'),
    ('ritm_alert', 'Ritm alert'),
    ('economie_posibila', 'Economie posibilă'),
    ('recurenta_detectata', 'Recurență detectată'),
    ('abonament_iminent', 'Abonament iminent'),
    ('abonament_scumpit', 'Abonament scumpit'),
    ('sugestie_anulare', 'Sugestie anulare'),
]


FRECVENTA_SUBSCRIPTION_CHOICES = [
    ('lunar', 'Lunar'),
    ('anual', 'Anual'),
    ('saptamanal', 'Săptămânal'),
]


ROL_MEMBRU_GOSPODARIE_CHOICES = [
    ('owner', 'Owner'),
    ('adult', 'Adult'),
    ('copil', 'Copil'),
]


TIP_SMART_ACTION_CHOICES = [
    ('buget', 'Buget'),
    ('abonament', 'Abonament'),
    ('economii', 'Economii'),
    ('onboarding', 'Onboarding'),
]


STATUS_SMART_ACTION_CHOICES = [
    ('pending', 'În așteptare'),
    ('done', 'Finalizat'),
    ('dismissed', 'Ignorat'),
]


class UserProfile(models.Model):
    utilizator = models.OneToOneField(User, on_delete=models.CASCADE)
    tip_gospodarie = models.CharField(max_length=20, choices=TIP_GOSPODARIE_CHOICES, default='single')
    nr_persoane = models.IntegerField(default=1)
    are_copii = models.BooleanField(default=False)
    venit_lunar = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    obiectiv = models.CharField(max_length=20, choices=OBIECTIV_CHOICES, default='stabilitate')
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profil {self.utilizator.username}"

    class Meta:
        verbose_name = 'Profil utilizator'
        verbose_name_plural = 'Profiluri utilizatori'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(utilizator=instance)


class UserPlan(models.Model):
    utilizator = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userplan')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    activ = models.BooleanField(default=True)
    data_expirare = models.DateField(null=True, blank=True)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilizator.username} - {self.get_plan_display()}"

    class Meta:
        verbose_name = 'Plan utilizator'
        verbose_name_plural = 'Planuri utilizatori'


@receiver(post_save, sender=User)
def create_user_plan(sender, instance, created, **kwargs):
    if created:
        UserPlan.objects.create(utilizator=instance, plan='free')


class Categorie(models.Model):
    nume = models.CharField(max_length=100)
    descriere = models.TextField(blank=True, null=True)
    culoare = models.CharField(max_length=7, default='#3498db')

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


class ForecastAlert(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forecast_alerts')
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, blank=True)
    tip = models.CharField(max_length=30, choices=TIP_ALERTA_CHOICES)
    mesaj = models.TextField()
    suma_implicata = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    zile_ramase = models.IntegerField(null=True, blank=True)
    actiune_recomandata = models.TextField()
    citita = models.BooleanField(default=False)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilizator.username} - {self.get_tip_display()}"

    class Meta:
        verbose_name = 'Alertă forecast'
        verbose_name_plural = 'Alerte forecast'
        ordering = ['citita', '-creat_la']


class SavingsGoal(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    titlu = models.CharField(max_length=200)
    suma_tinta = models.DecimalField(max_digits=12, decimal_places=2)
    suma_curenta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data_tinta = models.DateField(null=True, blank=True)
    culoare = models.CharField(max_length=7, default='#6366f1')
    icon = models.CharField(max_length=50, default='bi-piggy-bank')
    activ = models.BooleanField(default=True)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titlu} - {self.utilizator.username}"

    class Meta:
        verbose_name = 'Savings goal'
        verbose_name_plural = 'Savings goals'
        ordering = ['-activ', 'data_tinta', '-creat_la']


class GoalContribution(models.Model):
    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name='contributii')
    suma = models.DecimalField(max_digits=12, decimal_places=2)
    nota = models.CharField(max_length=200, blank=True)
    data = models.DateField()
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.goal.titlu} +{self.suma}"

    class Meta:
        verbose_name = 'Contribuție goal'
        verbose_name_plural = 'Contribuții goals'
        ordering = ['-data', '-creat_la']


class ExportLog(models.Model):
    TIP_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    ]

    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_logs')
    tip = models.CharField(max_length=20, choices=TIP_CHOICES)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilizator.username} - {self.tip}"

    class Meta:
        verbose_name = 'Log export'
        verbose_name_plural = 'Loguri export'
        ordering = ['-creat_la']


class ScanareLog(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scanare_logs')
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilizator.username} - scanare"

    class Meta:
        verbose_name = 'Log scanare'
        verbose_name_plural = 'Loguri scanare'
        ordering = ['-creat_la']


class Subscription(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    nume = models.CharField(max_length=200)
    suma_estimata = models.DecimalField(max_digits=12, decimal_places=2)
    frecventa = models.CharField(max_length=20, choices=FRECVENTA_SUBSCRIPTION_CHOICES, default='lunar')
    ziua_lunii = models.IntegerField(null=True, blank=True)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, blank=True)
    activ = models.BooleanField(default=True)
    detectat_automat = models.BooleanField(default=False)
    ultima_plata = models.DateField(null=True, blank=True)
    urmatoarea_plata = models.DateField(null=True, blank=True)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nume} - {self.utilizator.username}"

    class Meta:
        verbose_name = 'Abonament'
        verbose_name_plural = 'Abonamente'
        ordering = ['-activ', 'urmatoarea_plata', 'nume']


class Household(models.Model):
    nume = models.CharField(max_length=120)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='households_owned')
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nume} ({self.owner.username})"

    class Meta:
        verbose_name = 'Gospodărie'
        verbose_name_plural = 'Gospodării'
        ordering = ['-creat_la']


class HouseholdMember(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='membri')
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='household_memberships')
    rol = models.CharField(max_length=20, choices=ROL_MEMBRU_GOSPODARIE_CHOICES, default='adult')
    responsabilitate = models.CharField(max_length=200, blank=True)
    activ = models.BooleanField(default=True)
    adaugat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.household.nume} - {self.utilizator.username} ({self.get_rol_display()})"

    class Meta:
        verbose_name = 'Membru gospodărie'
        verbose_name_plural = 'Membri gospodărie'
        ordering = ['household__nume', 'utilizator__username']
        constraints = [
            models.UniqueConstraint(
                fields=['household', 'utilizator'],
                name='unique_household_member',
            )
        ]


class OnboardingJourney(models.Model):
    utilizator = models.OneToOneField(User, on_delete=models.CASCADE, related_name='onboarding_journey')
    data_start = models.DateField(default=timezone.localdate)
    data_tinta = models.DateField(null=True, blank=True)
    first_win_obtinut = models.BooleanField(default=False)
    first_win_la = models.DateTimeField(null=True, blank=True)
    ascuns = models.BooleanField(default=False)
    creat_la = models.DateTimeField(auto_now_add=True)
    actualizat_la = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.data_tinta:
            self.data_tinta = self.data_start + timedelta(days=7)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Onboarding {self.utilizator.username}"

    class Meta:
        verbose_name = 'Onboarding'
        verbose_name_plural = 'Onboarding'


@receiver(post_save, sender=User)
def create_onboarding_journey(sender, instance, created, **kwargs):
    if created:
        OnboardingJourney.objects.create(utilizator=instance)


class SmartAction(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='smart_actions')
    alerta = models.OneToOneField(
        ForecastAlert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='smart_action',
    )
    titlu = models.CharField(max_length=220)
    descriere = models.TextField(blank=True)
    tip = models.CharField(max_length=20, choices=TIP_SMART_ACTION_CHOICES, default='buget')
    status = models.CharField(max_length=20, choices=STATUS_SMART_ACTION_CHOICES, default='pending')
    impact_estimat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data_scadenta = models.DateField(null=True, blank=True)
    completata_la = models.DateTimeField(null=True, blank=True)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilizator.username} - {self.titlu}"

    class Meta:
        verbose_name = 'Smart action'
        verbose_name_plural = 'Smart actions'
        ordering = ['status', 'data_scadenta', '-creat_la']


class ReceiptInsight(models.Model):
    utilizator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receipt_insights')
    magazin = models.CharField(max_length=160)
    data_bon = models.DateField()
    total = models.DecimalField(max_digits=12, decimal_places=2)
    nr_produse = models.PositiveIntegerField(default=0)
    pret_mediu_produs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    produse_json = models.JSONField(default=list, blank=True)
    creat_la = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilizator.username} - {self.magazin} - {self.total}"

    class Meta:
        verbose_name = 'Receipt insight'
        verbose_name_plural = 'Receipt insights'
        ordering = ['-data_bon', '-creat_la']
        indexes = [
            models.Index(fields=['utilizator', 'data_bon']),
        ]
