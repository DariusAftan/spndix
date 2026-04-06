from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from .models import AIAnaliza, ExportLog, ScanareLog, UserPlan


def obtine_user_plan(utilizator):
    plan, _ = UserPlan.objects.get_or_create(
        utilizator=utilizator,
        defaults={
            'plan': 'free',
            'activ': True,
        },
    )

    azi = timezone.localdate()
    if plan.plan in ['pro', 'family'] and plan.data_expirare and plan.data_expirare < azi:
        plan.plan = 'free'
        plan.activ = True
        plan.save(update_fields=['plan', 'activ'])

    return plan


def check_limit(tip_actiune):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/accounts/login/')

            plan = obtine_user_plan(request.user)
            luna = timezone.now().month
            an = timezone.now().year
            azi = timezone.localdate()

            # For analysis and receipt scanning, only enforce limits on POST actions.
            if tip_actiune in ['analiza', 'scanare'] and request.method != 'POST':
                return view_func(request, *args, **kwargs)

            if tip_actiune == 'scanare' and request.POST.get('action') != 'analizeaza':
                return view_func(request, *args, **kwargs)

            if plan.plan == 'free':
                if tip_actiune == 'analiza':
                    count = AIAnaliza.objects.filter(
                        utilizator=request.user,
                        creat_la__month=luna,
                        creat_la__year=an,
                    ).count()
                    if count >= 2:
                        messages.warning(
                            request,
                            'Ai atins limita de 2 analize gratuite/lună. Upgrade la Pro pentru analize nelimitate!',
                        )
                        return redirect('upgrade')

                elif tip_actiune == 'export':
                    count = ExportLog.objects.filter(
                        utilizator=request.user,
                        creat_la__month=luna,
                        creat_la__year=an,
                    ).count()
                    if count >= 1:
                        messages.warning(
                            request,
                            'Ai atins limita de 1 export gratuit/lună.',
                        )
                        return redirect('upgrade')

                elif tip_actiune == 'scanare':
                    count = ScanareLog.objects.filter(
                        utilizator=request.user,
                        creat_la__month=luna,
                        creat_la__year=an,
                    ).count()
                    if count >= 3:
                        messages.warning(
                            request,
                            'Ai atins limita de 3 scanări gratuite/lună. Upgrade la Pro pentru scanări nelimitate!',
                        )
                        return redirect('upgrade')

            elif plan.plan in ['pro', 'family']:
                if tip_actiune == 'analiza':
                    count = AIAnaliza.objects.filter(
                        utilizator=request.user,
                        creat_la__date=azi,
                    ).count()
                    if count >= 10:
                        messages.warning(
                            request,
                            'Ai atins limita de 10 analize AI/zi pentru planul curent.',
                        )
                        return redirect('upgrade')

                elif tip_actiune == 'scanare':
                    count = ScanareLog.objects.filter(
                        utilizator=request.user,
                        creat_la__date=azi,
                    ).count()
                    if count >= 5:
                        messages.warning(
                            request,
                            'Ai atins limita de 5 scanări/zi pentru planul curent.',
                        )
                        return redirect('upgrade')

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
