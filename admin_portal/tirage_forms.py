from django import forms

from accounts.models import Tirage, AdminTiragePreference


DAY_CHOICES = (
    (0, "Lundi"),
    (1, "Mardi"),
    (2, "Mercredi"),
    (3, "Jeudi"),
    (4, "Vendredi"),
    (5, "Samedi"),
    (6, "Dimanche"),
)


class TirageForm(forms.ModelForm):
    jours_actifs = forms.MultipleChoiceField(
        label="Jours actifs",
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Tirage
        fields = (
            "nom",
            "type",
            "jours_actifs",
            "heure_ouverture",
            "heure_fermeture",
            "heure_tirage",
            "fermeture_auto",
            "mariage_automatique",
            "statut",
            "ordre_affichage",
        )

    def clean_jours_actifs(self):
        raw = self.cleaned_data.get("jours_actifs") or []
        return [int(x) for x in raw]

    def clean(self):
        cleaned = super().clean()
        o = cleaned.get("heure_ouverture")
        f = cleaned.get("heure_fermeture")
        t = cleaned.get("heure_tirage")

        # Validation assouplie: on ne vérifie plus l'ordre strict des heures
        # car l'ouverture est maintenant fixée à 00:00 pour tous les tirages
        
        if f and t and not (f < t):
            self.add_error("heure_tirage", "Doit être après l'heure de fermeture.")

        return cleaned


class TirageEditForm(forms.ModelForm):
    """Formulaire d'édition de tirage avec préférence d'activation par admin."""
    jours_actifs = forms.MultipleChoiceField(
        label="Jours actifs",
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    actif_pour_admin = forms.BooleanField(
        label="Actif pour moi",
        required=False,
        initial=True,
        help_text="Si désactivé, ce tirage n'apparaîtra pas pour vos agents",
    )

    class Meta:
        model = Tirage
        fields = (
            "nom",
            "type",
            "jours_actifs",
            "heure_ouverture",
            "heure_fermeture",
            "heure_tirage",
            "fermeture_auto",
            "mariage_automatique",
            "statut",
            "ordre_affichage",
        )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Rendre les champs de temps non requis en édition
        if self.instance and self.instance.pk:
            self.fields['heure_ouverture'].required = False
            self.fields['heure_fermeture'].required = False
            self.fields['heure_tirage'].required = False
        
        if self.instance and self.instance.pk and self.user:
            # Charger la préférence existante
            pref, _ = AdminTiragePreference.objects.get_or_create(
                user=self.user,
                tirage=self.instance,
                defaults={'actif': True}
            )
            self.fields['actif_pour_admin'].initial = pref.actif
        else:
            # Par défaut actif pour nouveau tirage
            self.fields['actif_pour_admin'].initial = True

    def clean_jours_actifs(self):
        raw = self.cleaned_data.get("jours_actifs") or []
        return [int(x) for x in raw]

    def clean(self):
        cleaned = super().clean()
        o = cleaned.get("heure_ouverture")
        f = cleaned.get("heure_fermeture")
        t = cleaned.get("heure_tirage")

        # Validation assouplie: on ne vérifie plus l'ordre strict des heures
        # car l'ouverture est maintenant fixée à 00:00 pour tous les tirages
        
        if f and t and not (f < t):
            self.add_error("heure_tirage", "Doit être après l'heure de fermeture.")

        return cleaned

    def save(self, commit=True):
        tirage = super().save(commit=commit)
        if self.user and tirage.pk:
            # Sauvegarder la préférence d'activation
            # BooleanField envoie True/False (booléen Python)
            actif_value = self.cleaned_data.get('actif_pour_admin', True)
            
            AdminTiragePreference.objects.update_or_create(
                user=self.user,
                tirage=tirage,
                defaults={'actif': actif_value}
            )
        return tirage
