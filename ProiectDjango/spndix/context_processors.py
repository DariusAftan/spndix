from django.db import DatabaseError, ProgrammingError

from .models import ForecastAlert, SmartAction, OnboardingJourney
from .plan_limits import obtine_user_plan


def unread_forecast_alerts(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'forecast_alerts_unread_count': 0,
            'smart_actions_pending_count': 0,
            'current_user_plan': None,
            'current_user_plan_name': 'free',
            'show_onboarding_hint': False,
        }

    try:
        count = ForecastAlert.objects.filter(utilizator=request.user, citita=False).count()
        smart_actions_pending = SmartAction.objects.filter(
            utilizator=request.user,
            status='pending',
        ).count()
        user_plan = obtine_user_plan(request.user)
        plan_name = user_plan.plan or 'free'

        onboarding = OnboardingJourney.objects.filter(utilizator=request.user).first()
        show_onboarding_hint = bool(onboarding and not onboarding.ascuns and not onboarding.first_win_obtinut)
    except (ProgrammingError, DatabaseError):
        count = 0
        smart_actions_pending = 0
        user_plan = None
        plan_name = 'free'
        show_onboarding_hint = False

    return {
        'forecast_alerts_unread_count': count,
        'smart_actions_pending_count': smart_actions_pending,
        'current_user_plan': user_plan,
        'current_user_plan_name': plan_name,
        'show_onboarding_hint': show_onboarding_hint,
    }
