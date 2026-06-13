from django import forms

from accounts.models import AdminPaymentSettings


class AdminPaymentSettingsForm(forms.ModelForm):
    class Meta:
        model = AdminPaymentSettings
        fields = (
            "boule_1er_lot_coeff",
            "boule_2eme_lot_coeff",
            "boule_3eme_lot_coeff",
            "loto3_coeff",
            "loto4_coeff",
            "loto5_coeff",
            "mariage_normal_coeff",
            "mariage_gratuit_actif",
            "mariage_gratuit_seuil1",
            "mariage_gratuit_qty1",
            "mariage_gratuit_seuil2",
            "mariage_gratuit_qty2",
            "mariage_gratuit_montant_fixe",
            "max_boule",
            "max_loto3",
            "max_loto4",
            "max_loto5",
            "max_mariage",
        )
        widgets = {
            "mariage_gratuit_actif": forms.CheckboxInput(),
        }
        labels = {
            "max_boule": "Boules (tous lots confondus)",
            "max_loto3": "Loto 3",
            "max_loto4": "Loto 4",
            "max_loto5": "Loto 5",
            "max_mariage": "Mariage normal",
        }
        help_texts = {
            "max_boule": "0 = interdit",
            "max_loto3": "0 = interdit",
            "max_loto4": "0 = interdit",
            "max_loto5": "0 = interdit",
            "max_mariage": "0 = interdit",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name in ("max_boule", "max_loto3", "max_loto4", "max_loto5", "max_mariage"):
            if name in self.fields:
                self.fields[name].min_value = 0

    def clean(self):
        cleaned = super().clean()

        s1 = cleaned.get("mariage_gratuit_seuil1")
        q1 = cleaned.get("mariage_gratuit_qty1")
        s2 = cleaned.get("mariage_gratuit_seuil2")
        q2 = cleaned.get("mariage_gratuit_qty2")

        if s1 is not None and s2 is not None and s2 <= s1:
            self.add_error("mariage_gratuit_seuil2", "Doit être strictement supérieur au seuil 1.")

        if q1 is not None and q1 == 0:
            self.add_error("mariage_gratuit_qty1", "Doit être supérieur à 0.")

        if q2 is not None and q2 == 0:
            self.add_error("mariage_gratuit_qty2", "Doit être supérieur à 0.")

        return cleaned
