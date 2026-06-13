from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import Borlette


class PortalAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class BorletteInfoForm(forms.ModelForm):
    class Meta:
        model = Borlette
        fields = [
            "nom_borlette",
            "telephone",
            "adresse",
            "site_web",
            "slogan",
            "logo_borlette",
            "ticket_footer_text",
            "mariage_gratuit_actif",
            "mariage_gratuit_montant",
        ]

        widgets = {
            "nom_borlette": forms.TextInput(attrs={"class": "gaboom-input w-full"}),
            "telephone": forms.TextInput(attrs={"class": "gaboom-input w-full"}),
            "adresse": forms.Textarea(attrs={"class": "gaboom-input w-full", "rows": 4}),
            "site_web": forms.URLInput(attrs={"class": "gaboom-input w-full"}),
            "slogan": forms.TextInput(attrs={"class": "gaboom-input w-full"}),
            "logo_borlette": forms.ClearableFileInput(attrs={"class": "gaboom-input w-full"}),
            "ticket_footer_text": forms.Textarea(attrs={"class": "gaboom-input w-full", "rows": 3}),
            "mariage_gratuit_montant": forms.NumberInput(attrs={"class": "gaboom-input w-full", "step": "0.01"}),
        }

