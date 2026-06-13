from django import forms
from django.contrib.auth import get_user_model

from accounts.models import Agent


User = get_user_model()


class AgentCreateForm(forms.Form):
    nom = forms.CharField(label="Nom", max_length=150)
    telephone = forms.CharField(label="Téléphone", max_length=50)
    zone = forms.CharField(label="Zone", max_length=120)
    mot_de_passe = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    commission = forms.DecimalField(label="Commission (%)", max_digits=5, decimal_places=2)


class AgentEditForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = (
            "nom",
            "telephone",
            "zone",
            "statut",
            "commission",
        )


class AgentResetPasswordForm(forms.Form):
    mot_de_passe = forms.CharField(label="Nouveau mot de passe", widget=forms.PasswordInput)
