from django import forms
from django.contrib.auth import get_user_model

from .models import Borlette


User = get_user_model()


class BorletteAdminForm(forms.ModelForm):
    mot_de_passe = forms.CharField(
        label="Mot de passe (création de l'Admin)",
        widget=forms.PasswordInput,
        required=False,
        help_text="Ce mot de passe sert uniquement à créer/mettre à jour le compte Admin associé.",
    )

    class Meta:
        model = Borlette
        fields = (
            "nom_borlette",
            "adresse",
            "telephone",
            "agents_eligible_share",
            "mot_de_passe",
            "logo_borlette",
            "slogan",
            "site_web",
            "ticket_footer_text",
            "mariage_gratuit_actif",
            "mariage_gratuit_montant",
        )

    def clean_agents_eligible_share(self):
        val = self.cleaned_data.get("agents_eligible_share")
        if val is None:
            return val

        if self.instance.pk:
            total_agents = self.instance.agents.count()
            if val > total_agents:
                raise forms.ValidationError(f"Doit être <= total_agents ({total_agents}).")

        return val

    def clean_nom_borlette(self):
        nom_borlette = self.cleaned_data["nom_borlette"].strip()

        existing_user_qs = User.objects.filter(username=nom_borlette)
        if self.instance.pk and self.instance.user_id:
            existing_user_qs = existing_user_qs.exclude(pk=self.instance.user_id)

        if existing_user_qs.exists():
            raise forms.ValidationError("Ce nom de borlette est déjà utilisé par un utilisateur.")

        return nom_borlette

    def clean(self):
        cleaned = super().clean()

        if not self.instance.pk:
            if not cleaned.get("mot_de_passe"):
                self.add_error("mot_de_passe", "Ce champ est obligatoire à la création.")

        return cleaned
