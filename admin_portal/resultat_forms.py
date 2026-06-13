"""Formulaires pour la saisie des résultats de tirage."""
from django import forms
from django.core.validators import RegexValidator


class ResultatForm(forms.Form):
    """Formulaire de saisie des résultats d'un tirage."""
    
    lot1 = forms.CharField(
        label="1er Lot",
        max_length=2,
        min_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="Format: 00 à 99")],
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "00-99",
            "pattern": r"\d{2}",
            "inputmode": "numeric",
        }),
    )
    
    lot2 = forms.CharField(
        label="2ème Lot",
        max_length=2,
        min_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="Format: 00 à 99")],
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "00-99",
            "pattern": r"\d{2}",
            "inputmode": "numeric",
        }),
    )
    
    lot3 = forms.CharField(
        label="3ème Lot",
        max_length=2,
        min_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="Format: 00 à 99")],
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "00-99",
            "pattern": r"\d{2}",
            "inputmode": "numeric",
        }),
    )
    
    chiffre_loto3 = forms.CharField(
        label="Chiffre Loto3",
        max_length=1,
        min_length=1,
        validators=[RegexValidator(r"^\d$", message="Format: 0 à 9")],
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "0-9",
            "pattern": r"\d",
            "inputmode": "numeric",
        }),
    )
    
    def clean(self):
        cleaned = super().clean()
        lot1 = cleaned.get("lot1")
        lot2 = cleaned.get("lot2")
        lot3 = cleaned.get("lot3")
        
        # Vérifier que les lots sont distincts
        if lot1 and lot2 and lot3:
            lots = [lot1, lot2, lot3]
            if len(set(lots)) != 3:
                raise forms.ValidationError("Les 3 lots doivent être distincts.")
        
        return cleaned


class AgentPayoutForm(forms.Form):
    """Formulaire de paiement agent."""
    
    amount = forms.DecimalField(
        label="Montant",
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01",
            "min": "0.01",
        }),
    )
    
    note = forms.CharField(
        label="Note (optionnel)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Note optionnelle...",
        }),
    )
