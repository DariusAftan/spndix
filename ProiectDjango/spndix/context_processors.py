from django.db import DatabaseError, ProgrammingError

from .models import ForecastAlert
from .plan_limits import obtine_user_plan


def unread_forecast_alerts(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'forecast_alerts_unread_count': 0,
            'current_user_plan': None,
            'current_user_plan_name': 'free',
        }

    try:
        count = ForecastAlert.objects.filter(utilizator=request.user, citita=False).count()
        user_plan = obtine_user_plan(request.user)
        plan_name = user_plan.plan or 'free'
    except (ProgrammingError, DatabaseError):
        count = 0
        user_plan = None
        plan_name = 'free'

    return {
        'forecast_alerts_unread_count': count,
        'current_user_plan': user_plan,
        'current_user_plan_name': plan_name,
    }
