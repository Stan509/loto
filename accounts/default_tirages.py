from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from accounts.models import Borlette, Tirage, TirageStatus


@dataclass(frozen=True)
class DefaultTirageSpec:
    nom: str
    code: str
    heure_tirage: str
    heure_ouverture: str
    heure_fermeture: str
    pays: str = "USA"
    ville: str = ""


DEFAULT_TIRAGES: list[DefaultTirageSpec] = [
    DefaultTirageSpec(
        nom="New York Midi",
        code="NY_MIDI",
        heure_tirage="14:30",
        heure_ouverture="09:00",
        heure_fermeture="14:25",
        ville="New York",
    ),
    DefaultTirageSpec(
        nom="New York Soir",
        code="NY_SOIR",
        heure_tirage="22:30",
        heure_ouverture="15:00",
        heure_fermeture="22:25",
        ville="New York",
    ),
    DefaultTirageSpec(
        nom="Florida Midi",
        code="FL_MIDI",
        heure_tirage="13:30",
        heure_ouverture="08:00",
        heure_fermeture="13:25",
        ville="Florida",
    ),
    DefaultTirageSpec(
        nom="Florida Soir",
        code="FL_SOIR",
        heure_tirage="21:45",
        heure_ouverture="14:00",
        heure_fermeture="21:40",
        ville="Florida",
    ),
    DefaultTirageSpec(
        nom="Georgia Midi",
        code="GA_MIDI",
        heure_tirage="12:29",
        heure_ouverture="07:00",
        heure_fermeture="12:24",
        ville="Georgia",
    ),
    DefaultTirageSpec(
        nom="Georgia Evening",
        code="GA_EVENING",
        heure_tirage="18:59",
        heure_ouverture="13:00",
        heure_fermeture="18:54",
        ville="Georgia",
    ),
    DefaultTirageSpec(
        nom="Georgia Night",
        code="GA_NIGHT",
        heure_tirage="23:34",
        heure_ouverture="19:30",
        heure_fermeture="23:29",
        ville="Georgia",
    ),
    DefaultTirageSpec(
        nom="Tennessee Morning",
        code="TN_MORNING",
        heure_tirage="10:28",
        heure_ouverture="06:00",
        heure_fermeture="10:23",
        ville="Tennessee",
    ),
    DefaultTirageSpec(
        nom="Tennessee Midi",
        code="TN_MIDI",
        heure_tirage="13:28",
        heure_ouverture="11:00",
        heure_fermeture="13:23",
        ville="Tennessee",
    ),
    DefaultTirageSpec(
        nom="Tennessee Evening",
        code="TN_EVENING",
        heure_tirage="19:28",
        heure_ouverture="14:00",
        heure_fermeture="19:23",
        ville="Tennessee",
    ),
    DefaultTirageSpec(
        nom="Illinois Midi",
        code="IL_MIDI",
        heure_tirage="13:40",
        heure_ouverture="09:00",
        heure_fermeture="13:35",
        ville="Illinois",
    ),
    DefaultTirageSpec(
        nom="Illinois Evening",
        code="IL_EVENING",
        heure_tirage="22:22",
        heure_ouverture="14:00",
        heure_fermeture="22:17",
        ville="Illinois",
    ),
    DefaultTirageSpec(
        nom="Texas Morning",
        code="TX_MORNING",
        heure_tirage="11:00",
        heure_ouverture="07:00",
        heure_fermeture="10:55",
        ville="Texas",
    ),
    DefaultTirageSpec(
        nom="Texas Day",
        code="TX_DAY",
        heure_tirage="13:27",
        heure_ouverture="11:00",
        heure_fermeture="13:22",
        ville="Texas",
    ),
    DefaultTirageSpec(
        nom="Texas Evening",
        code="TX_EVENING",
        heure_tirage="19:00",
        heure_ouverture="14:00",
        heure_fermeture="18:55",
        ville="Texas",
    ),
    DefaultTirageSpec(
        nom="Texas Night",
        code="TX_NIGHT",
        heure_tirage="23:12",
        heure_ouverture="19:30",
        heure_fermeture="23:07",
        ville="Texas",
    ),
]


def _parse_time(v: str):
    return datetime.strptime(v, "%H:%M").time()


def ensure_default_tirages(*, borlette: Borlette) -> None:
    existing = {
        code: True
        for code in Tirage.objects.filter(borlette=borlette)
        .exclude(code="")
        .values_list("code", flat=True)
    }

    for spec in DEFAULT_TIRAGES:
        if existing.get(spec.code):
            continue

        t = Tirage(
            borlette=borlette,
            nom=spec.nom,
            code=spec.code,
            pays=spec.pays,
            ville=spec.ville,
            heure_tirage=_parse_time(spec.heure_tirage),
            heure_ouverture=_parse_time(spec.heure_ouverture),
            heure_fermeture=_parse_time(spec.heure_fermeture),
            is_default=True,
            modifiable=True,
            source_api_locked=True,
            statut=TirageStatus.ACTIF,
            fermeture_auto=True,
            ordre_affichage=0,
            jours_actifs=[0, 1, 2, 3, 4, 5, 6],
        )
        t.full_clean()
        t.save()
