import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spndix', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Categorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nume', models.CharField(max_length=100)),
                ('descriere', models.TextField(blank=True, null=True)),
                ('culoare', models.CharField(default='#3498db', max_length=7)),
            ],
            options={
                'verbose_name_plural': 'Categorii',
            },
        ),
        migrations.CreateModel(
            name='Cheltuiala',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titlu', models.CharField(max_length=200)),
                ('suma', models.DecimalField(decimal_places=2, max_digits=10)),
                ('data', models.DateField()),
                ('descriere', models.TextField(blank=True, null=True)),
                ('creat_la', models.DateTimeField(auto_now_add=True)),
                ('categorie', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='spndix.categorie')),
                ('utilizator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Cheltuieli',
                'ordering': ['-data'],
            },
        ),
        migrations.DeleteModel(
            name='Task',
        ),
    ]
