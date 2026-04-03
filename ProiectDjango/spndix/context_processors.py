from django.db import DatabaseError, ProgrammingError

from .models import ForecastAlert


def unread_forecast_alerts(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'forecast_alerts_unread_count': 0}

    try:
        count = ForecastAlert.objects.filter(utilizator=request.user, citita=False).count()
    except (ProgrammingError, DatabaseError):
        count = 0

    return {'forecast_alerts_unread_count': count}
