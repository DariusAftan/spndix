import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spndix', '0002_categorie_cheltuiala_delete_task'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Budget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('suma_limita', models.DecimalField(decimal_places=2, max_digits=10)),
                ('luna', models.PositiveSmallIntegerField(choices=[(1, 'Ianuarie'), (2, 'Februarie'), (3, 'Martie'), (4, 'Aprilie'), (5, 'Mai'), (6, 'Iunie'), (7, 'Iulie'), (8, 'August'), (9, 'Septembrie'), (10, 'Octombrie'), (11, 'Noiembrie'), (12, 'Decembrie')])),
                ('an', models.PositiveSmallIntegerField()),
                ('categorie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bugete', to='spndix.categorie')),
                ('utilizator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Buget',
                'verbose_name_plural': 'Bugete',
                'ordering': ['-an', '-luna', 'categorie__nume'],
                'constraints': [models.UniqueConstraint(fields=('utilizator', 'categorie', 'luna', 'an'), name='unique_budget_per_category_month_year')],
            },
        ),
    ]
