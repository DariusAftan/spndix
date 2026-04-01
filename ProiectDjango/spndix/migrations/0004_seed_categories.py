from django.db import migrations


def seed_categories(apps, schema_editor):
    Categorie = apps.get_model('spndix', 'Categorie')

    categories = [
        ('Food & Groceries', '#2ecc71', 'Esențiale'),
        ('Rent / Mortgage', '#e74c3c', 'Esențiale'),
        ('Utilities (electricity, water, gas)', '#3498db', 'Esențiale'),
        ('Internet & Phone', '#2980b9', 'Esențiale'),
        ('Transportation (fuel, bus, taxi)', '#16a085', 'Esențiale'),
        ('Healthcare & Medicine', '#1abc9c', 'Esențiale'),
        ('Clothing & Accessories', '#8e44ad', 'Personale'),
        ('Personal Care (haircut, cosmetics)', '#9b59b6', 'Personale'),
        ('Gym & Sports', '#27ae60', 'Personale'),
        ('Education & Books', '#f39c12', 'Personale'),
        ('Dining Out & Cafes', '#d35400', 'Timp liber'),
        ('Entertainment (cinema, concerts)', '#9b59b6', 'Timp liber'),
        ('Travel & Vacation', '#f1c40f', 'Timp liber'),
        ('Hobbies', '#7f8c8d', 'Timp liber'),
        ('Subscriptions (Netflix, Spotify)', '#34495e', 'Timp liber'),
        ('Savings', '#f1c40f', 'Financiare'),
        ('Loan Payments', '#c0392b', 'Financiare'),
        ('Insurance', '#7d3c98', 'Financiare'),
        ('Taxes & Fees', '#e67e22', 'Financiare'),
        ('Investments', '#2c3e50', 'Financiare'),
        ('Gifts & Donations', '#e84393', 'Diverse'),
        ('Pet Care', '#6c5ce7', 'Diverse'),
        ('Home & Repairs', '#95a5a6', 'Diverse'),
        ('Electronics & Tech', '#00b894', 'Diverse'),
        ('Other', '#636e72', 'Diverse'),
    ]

    for name, color, group in categories:
        Categorie.objects.get_or_create(
            nume=name,
            defaults={
                'culoare': color,
                'descriere': group,
            },
        )


def unseed_categories(apps, schema_editor):
    Categorie = apps.get_model('spndix', 'Categorie')
    names = [
        'Food & Groceries',
        'Rent / Mortgage',
        'Utilities (electricity, water, gas)',
        'Internet & Phone',
        'Transportation (fuel, bus, taxi)',
        'Healthcare & Medicine',
        'Clothing & Accessories',
        'Personal Care (haircut, cosmetics)',
        'Gym & Sports',
        'Education & Books',
        'Dining Out & Cafes',
        'Entertainment (cinema, concerts)',
        'Travel & Vacation',
        'Hobbies',
        'Subscriptions (Netflix, Spotify)',
        'Savings',
        'Loan Payments',
        'Insurance',
        'Taxes & Fees',
        'Investments',
        'Gifts & Donations',
        'Pet Care',
        'Home & Repairs',
        'Electronics & Tech',
        'Other',
    ]
    Categorie.objects.filter(nume__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('spndix', '0003_budget'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]