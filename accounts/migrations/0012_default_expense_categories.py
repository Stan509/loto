"""
Migration pour créer les catégories de dépenses par défaut pour chaque borlette existante.
"""
from django.db import migrations


DEFAULT_CATEGORIES = [
    "Location",
    "Transport",
    "Achat de matériel",
    "Impôts",
    "Internet",
    "Électricité",
    "Téléphone",
    "Salaires",
    "Fournitures de bureau",
    "Entretien",
    "Publicité",
    "Frais bancaires",
    "Autres",
]


def create_default_categories(apps, schema_editor):
    """Crée les catégories par défaut pour chaque borlette."""
    Borlette = apps.get_model("accounts", "Borlette")
    ExpenseCategory = apps.get_model("accounts", "ExpenseCategory")

    for borlette in Borlette.objects.all():
        for cat_name in DEFAULT_CATEGORIES:
            ExpenseCategory.objects.get_or_create(
                borlette=borlette,
                name=cat_name,
            )


def reverse_default_categories(apps, schema_editor):
    """Supprime les catégories par défaut (réversible)."""
    ExpenseCategory = apps.get_model("accounts", "ExpenseCategory")
    ExpenseCategory.objects.filter(name__in=DEFAULT_CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_expenses"),
    ]

    operations = [
        migrations.RunPython(create_default_categories, reverse_default_categories),
    ]
