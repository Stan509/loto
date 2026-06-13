"""
Formulaires pour les dépenses.
"""
from django import forms
from django.utils import timezone

from accounts.models import Expense, ExpenseCategory


class ExpenseForm(forms.Form):
    """Formulaire de création/édition de dépense."""
    
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        label="Montant (G)",
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
    )
    date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    category = forms.ChoiceField(
        choices=[],
        required=False,
        label="Catégorie",
    )
    new_category = forms.CharField(
        max_length=100,
        required=False,
        label="Nouvelle catégorie",
        help_text="Si rempli, crée une nouvelle catégorie",
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Description",
        help_text="Description obligatoire",
    )

    def __init__(self, *args, borlette=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.borlette = borlette

        # Charger catégories
        if borlette:
            categories = ExpenseCategory.objects.filter(borlette=borlette).order_by("name")
            self.fields["category"].choices = [("", "-- Sélectionner --")] + [
                (c.id, c.name) for c in categories
            ]

        # Date par défaut
        if not self.data.get("date"):
            self.fields["date"].initial = timezone.localdate()

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        new_category = cleaned_data.get("new_category", "").strip()

        if not category and not new_category:
            # Permettre sans catégorie
            pass

        return cleaned_data

    def save(self, created_by=None, instance=None):
        """Sauvegarde la dépense."""
        data = self.cleaned_data
        
        # Gérer catégorie
        category_obj = None
        if data.get("new_category"):
            category_obj, _ = ExpenseCategory.objects.get_or_create(
                borlette=self.borlette,
                name=data["new_category"].strip(),
            )
        elif data.get("category"):
            category_obj = ExpenseCategory.objects.filter(
                id=data["category"], borlette=self.borlette
            ).first()

        if instance:
            # Mise à jour
            instance.amount = data["amount"]
            instance.date = data["date"]
            instance.category = category_obj
            instance.description = data["description"]
            instance.save()
            return instance
        else:
            # Création
            return Expense.objects.create(
                borlette=self.borlette,
                created_by=created_by,
                amount=data["amount"],
                date=data["date"],
                category=category_obj,
                description=data["description"],
            )
