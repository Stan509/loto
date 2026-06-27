import itertools
from datetime import time
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import AdminPaymentSettings, Agent, Borlette, Tirage, TirageStatus, UserRole
from core.services.ticket_validation_service import TicketValidationService


@pytest.fixture
def user_model():
    return get_user_model()


@pytest.fixture
def admin_user(db, user_model):
    return user_model.objects.create_user(username="admin_test", password="x", role=UserRole.ADMIN)


@pytest.fixture
def borlette(db, admin_user):
    return Borlette.objects.create(
        user=admin_user,
        nom_borlette="Borlette Test",
        adresse="addr",
        telephone="000",
        slogan="s",
    )


@pytest.fixture
def agent_user(db, user_model):
    return user_model.objects.create_user(username="agent_test", password="x", role=UserRole.AGENT)


@pytest.fixture
def agent(db, agent_user, borlette):
    return Agent.objects.create(
        user=agent_user,
        borlette=borlette,
        nom="Agent",
        telephone="111",
        zone="Z",
        commission=0,
    )


def _make_tirage_open(db, borlette, *, statut=TirageStatus.ACTIF):
    now = timezone.localtime(timezone.now())
    t = now.time()

    # safe window around "now" (keep it inside [open, close) and before draw)
    open_t = time(max(t.hour - 1, 0), t.minute, 0)
    close_t = time(min(t.hour + 1, 23), t.minute, 59)
    draw_t = time(min(t.hour + 2, 23), t.minute, 59)

    return Tirage.objects.create(
        borlette=borlette,
        nom="Tirage",
        type="JOUR",
        jours_actifs=[],
        heure_ouverture=open_t,
        heure_fermeture=close_t,
        heure_tirage=draw_t,
        fermeture_auto=True,
        mariage_automatique=True,
        statut=statut,
        ordre_affichage=0,
    )


@pytest.fixture
def tirage_ouvert(db, borlette):
    return _make_tirage_open(db, borlette, statut=TirageStatus.ACTIF)


@pytest.fixture
def tirage_suspendu(db, borlette):
    return _make_tirage_open(db, borlette, statut=TirageStatus.SUSPENDU)


@pytest.fixture
def settings_allow_all(db, borlette):
    return AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("999"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
        mariage_gratuit_actif=False,
    )


def test_draw_inexistant_invalide(db, borlette, agent, settings_allow_all):
    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "1"}],
        draw_ids=[999999],
    )
    assert res["is_valid"] is False
    assert "Tirage fermé ou invalide" in res["errors"]


def test_draw_autre_admin_invalide(db, user_model, agent, settings_allow_all):
    other_admin = user_model.objects.create_user(username="admin2", password="x", role=UserRole.ADMIN)
    other_borlette = Borlette.objects.create(
        user=other_admin,
        nom_borlette="Borlette 2",
        adresse="addr",
        telephone="000",
        slogan="s",
    )
    other_draw = _make_tirage_open(db, other_borlette, statut=TirageStatus.ACTIF)

    res = TicketValidationService.validate_ticket(
        admin=agent.borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "1"}],
        draw_ids=[other_draw.id],
    )
    assert res["is_valid"] is False
    assert "Tirage fermé ou invalide" in res["errors"]


def test_draw_ferme_invalide(db, borlette, agent, tirage_suspendu, settings_allow_all):
    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "1"}],
        draw_ids=[tirage_suspendu.id],
    )
    assert res["is_valid"] is False
    assert res["free_marriages"] == []
    assert "Tirage fermé ou invalide" in res["errors"]


def test_draw_valide_ticket_valide(db, borlette, agent, tirage_ouvert, settings_allow_all):
    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "1"}],
        draw_ids=[tirage_ouvert.id],
    )
    assert res["is_valid"] is True
    assert res["errors"] == []


@pytest.mark.parametrize(
    "jeu,valeur",
    [
        ("boule", "9"),
        ("boule", "100"),
        ("loto3", "12"),
        ("loto4", "123"),
        ("loto5", "1234"),
        ("mariage", "12-12"),
        ("mariage", "AA-BB"),
    ],
)
def test_formats_invalides(db, borlette, agent, tirage_ouvert, settings_allow_all, jeu, valeur):
    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": jeu, "valeur": valeur, "mise": "1"}],
        draw_ids=[tirage_ouvert.id],
    )
    assert res["is_valid"] is False
    assert f"Format invalide pour {jeu} : {valeur}" in res["errors"]


def test_plafond_0_jeu_interdit(db, borlette, agent, tirage_ouvert):
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("0"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
    )

    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "1"}],
        draw_ids=[tirage_ouvert.id],
    )
    assert res["is_valid"] is False
    assert "Jeu boule interdit par l’admin" in res["errors"]


def test_mise_superieure_plafond_refus(db, borlette, agent, tirage_ouvert):
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("10"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
    )

    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "11"}],
        draw_ids=[tirage_ouvert.id],
    )
    assert res["is_valid"] is False
    assert "Mise supérieure au plafond autorisé pour boule" in res["errors"]


def test_mise_inferieure_ou_egale_plafond_ok(db, borlette, agent, tirage_ouvert):
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("10"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
    )

    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "10"}],
        draw_ids=[tirage_ouvert.id],
    )
    assert res["is_valid"] is True
    assert res["errors"] == []


def test_mariages_gratuits_disabled(db, borlette, agent, tirage_ouvert):
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("999"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
        mariage_gratuit_actif=False,
    )

    lines = [{"jeu": "loto3", "valeur": f"{i:03d}", "mise": "1"} for i in range(10)]
    res = TicketValidationService.validate_ticket(admin=borlette.user, agent=agent, ticket_lines=lines, draw_ids=[tirage_ouvert.id])
    assert res["is_valid"] is True
    assert res["free_marriages"] == []


@pytest.mark.parametrize(
    "total_stake,expected_qty",
    [
        (Decimal("99"), 0),
        (Decimal("100"), 1),
        (Decimal("299"), 1),
        (Decimal("300"), 3),
        (Decimal("500"), 3),
    ],
)
def test_mariages_gratuits_quantite(db, borlette, agent, tirage_ouvert, monkeypatch, total_stake, expected_qty):
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("999"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
        mariage_gratuit_actif=True,
        mariage_gratuit_montant_fixe=Decimal("150"),
    )

    # deterministic random samples: (00-01), (02-03), ...
    pairs = [(i, i + 1) for i in range(0, 98, 2)]
    it = itertools.cycle(pairs)

    def fake_sample(_population, k):
        assert k == 2
        return list(next(it))

    monkeypatch.setattr("core.services.ticket_validation_service.random.sample", fake_sample)

    lines = [{"jeu": "boule", "valeur": "12", "mise": str(total_stake)}]
    # include an existing marriage to ensure no duplicate
    lines.append({"jeu": "mariage", "valeur": "00-01", "mise": "0"})

    res = TicketValidationService.validate_ticket(admin=borlette.user, agent=agent, ticket_lines=lines, draw_ids=[tirage_ouvert.id])
    assert res["is_valid"] is True
    assert len(res["free_marriages"]) == expected_qty

    # stake = 0, no duplicates, and not equal to existing
    seen = set()
    for m in res["free_marriages"]:
        assert m["jeu"] == "mariage"
        assert m["mise"] == Decimal("0")
        assert m["paiement_fixe"] == Decimal("150")
        assert m["valeur"] != "00-01"
        assert m["valeur"] not in seen
        seen.add(m["valeur"])


def test_cas_valide_complet(db, borlette, agent, tirage_ouvert, monkeypatch):
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("999"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
        mariage_gratuit_actif=True,
        mariage_gratuit_montant_fixe=Decimal("200"),
    )

    # deterministic random samples: (10-11), (12-13), ...
    pairs = [(10, 11), (12, 13), (14, 15), (16, 17), (18, 19), (20, 21)]
    it = itertools.cycle(pairs)

    def fake_sample(_population, k):
        assert k == 2
        return list(next(it))

    monkeypatch.setattr("core.services.ticket_validation_service.random.sample", fake_sample)

    lines = [
        {"jeu": "boule", "valeur": "12", "mise": "300"},
        *[{"jeu": "loto3", "valeur": f"{i:03d}", "mise": "1"} for i in range(9)],
    ]

    res = TicketValidationService.validate_ticket(admin=borlette.user, agent=agent, ticket_lines=lines, draw_ids=[tirage_ouvert.id])
    assert res["is_valid"] is True
    assert res["errors"] == []
    assert len(res["free_marriages"]) == 3


def test_no_db_writes_during_service_call(db, borlette, agent, tirage_ouvert, monkeypatch):
    # create settings so the service reads existing row (no creation)
    AdminPaymentSettings.objects.create(
        borlette=borlette,
        max_boule=Decimal("999"),
        max_loto3=Decimal("999"),
        max_loto4=Decimal("999"),
        max_loto5=Decimal("999"),
        max_mariage=Decimal("999"),
        mariage_gratuit_actif=False,
    )

    def boom(*args, **kwargs):
        raise AssertionError("DB write method should not be called by the service")

    # Guardrails: if the service ever regresses to get_or_create/save, fail.
    monkeypatch.setattr("django.db.models.query.QuerySet.get_or_create", boom)
    monkeypatch.setattr("django.db.models.query.QuerySet.update_or_create", boom)
    monkeypatch.setattr("django.db.models.query.QuerySet.bulk_create", boom)
    monkeypatch.setattr("django.db.models.base.Model.save", boom)

    res = TicketValidationService.validate_ticket(
        admin=borlette.user,
        agent=agent,
        ticket_lines=[{"jeu": "boule", "valeur": "12", "mise": "1"}],
        draw_ids=[tirage_ouvert.id],
    )
    assert res["is_valid"] is True
