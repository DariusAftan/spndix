from django.contrib import admin
from .models import (
    Categorie,
    Cheltuiala,
    Budget,
    AIAnaliza,
    ForecastAlert,
    SavingsGoal,
    GoalContribution,
    ExportLog,
    ScanareLog,
    Subscription,
    UserPlan,
    Household,
    HouseholdMember,
    OnboardingJourney,
    SmartAction,
    ReceiptInsight,
)


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


@admin.register(ForecastAlert)
class ForecastAlertAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'tip', 'categorie', 'suma_implicata', 'zile_ramase', 'citita', 'creat_la')
    list_filter = ('tip', 'citita', 'creat_la', 'utilizator')
    search_fields = ('utilizator__username', 'mesaj', 'actiune_recomandata', 'categorie__nume')


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('titlu', 'utilizator', 'suma_curenta', 'suma_tinta', 'data_tinta', 'activ')
    list_filter = ('activ', 'data_tinta', 'utilizator')
    search_fields = ('titlu', 'utilizator__username')


@admin.register(GoalContribution)
class GoalContributionAdmin(admin.ModelAdmin):
    list_display = ('goal', 'suma', 'data', 'creat_la')
    list_filter = ('data', 'creat_la')
    search_fields = ('goal__titlu', 'nota')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'nume',
        'utilizator',
        'suma_estimata',
        'frecventa',
        'urmatoarea_plata',
        'activ',
        'detectat_automat',
    )
    list_filter = ('frecventa', 'activ', 'detectat_automat', 'utilizator')
    search_fields = ('nume', 'utilizator__username', 'categorie__nume')


@admin.register(UserPlan)
class UserPlanAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'plan', 'activ', 'data_expirare', 'creat_la')
    list_filter = ('plan', 'activ', 'creat_la')
    search_fields = ('utilizator__username', 'stripe_customer_id', 'stripe_subscription_id')


@admin.register(ExportLog)
class ExportLogAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'tip', 'creat_la')
    list_filter = ('tip', 'creat_la')
    search_fields = ('utilizator__username',)


@admin.register(ScanareLog)
class ScanareLogAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'creat_la')
    list_filter = ('creat_la',)
    search_fields = ('utilizator__username',)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('nume', 'owner', 'creat_la')
    list_filter = ('creat_la',)
    search_fields = ('nume', 'owner__username')


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ('household', 'utilizator', 'rol', 'activ', 'responsabilitate')
    list_filter = ('rol', 'activ', 'household')
    search_fields = ('household__nume', 'utilizator__username', 'responsabilitate')


@admin.register(OnboardingJourney)
class OnboardingJourneyAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'data_start', 'data_tinta', 'first_win_obtinut', 'ascuns')
    list_filter = ('first_win_obtinut', 'ascuns')
    search_fields = ('utilizator__username',)


@admin.register(SmartAction)
class SmartActionAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'titlu', 'tip', 'status', 'impact_estimat', 'data_scadenta')
    list_filter = ('tip', 'status', 'data_scadenta')
    search_fields = ('utilizator__username', 'titlu', 'descriere')


@admin.register(ReceiptInsight)
class ReceiptInsightAdmin(admin.ModelAdmin):
    list_display = ('utilizator', 'magazin', 'data_bon', 'total', 'nr_produse', 'pret_mediu_produs')
    list_filter = ('magazin', 'data_bon')
    search_fields = ('utilizator__username', 'magazin')
