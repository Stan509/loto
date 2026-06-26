import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.validators import RegexValidator

from datetime import datetime
from decimal import Decimal


class UserRole(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    ADMIN = "ADMIN", "Admin"
    AGENT = "AGENT", "Agent"
    AFFILIATE = "AFFILIATE", "Affiliate"
    PARTNER = "PARTNER", "Partenaire"


class User(AbstractUser):
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.ADMIN,
    )

    must_change_password = models.BooleanField(
        default=False,
        help_text="Force l'utilisateur à changer son mot de passe à la prochaine connexion"
    )

    active_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Identifiant de la session active de l'agent pour restreindre à un seul appareil"
    )

    device_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Signature de l'appareil de l'agent"
    )

    email_verification_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Jeton de vérification de l'email"
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Indique si l'email a été vérifié"
    )
    password_reset_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Jeton de récupération de mot de passe"
    )
    password_reset_token_expires = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date d'expiration du jeton de récupération"
    )




class Borlette(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="borlette")

    nom_borlette = models.CharField(max_length=150, unique=True)
    adresse = models.TextField()
    telephone = models.CharField(max_length=50)
    logo_borlette = models.ImageField(upload_to="borlettes/logos/", blank=True, null=True)
    slogan = models.CharField(max_length=255)
    site_web = models.URLField(blank=True, null=True)

    agents_eligible_share = models.PositiveIntegerField(
        default=0,
        verbose_name="Agents comptabilisés pour partage",
        help_text="Nombre d'agents pris en compte dans la répartition des revenus.",
    )

    # Offline mode settings
    allow_offline_print = models.BooleanField(default=False, help_text="Allow agents to print offline tickets (HL-XXXXXXXX)")

    # Ticket settings
    ticket_footer_text = models.TextField(
        default="La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours",
        blank=True,
        help_text="Texte de pied de page modifiable pour les tickets"
    )
    mariage_gratuit_actif = models.BooleanField(
        default=False,
        help_text="Activer le mariage gratuit pour cette borlette"
    )
    mariage_gratuit_montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Montant fixe du mariage gratuit en Gourdes"
    )

    def __str__(self) -> str:
        return self.nom_borlette

    def clean(self):
        super().clean()

        if self.pk and self.agents_eligible_share is not None:
            total_agents = self.agents.count()
            if self.agents_eligible_share > total_agents:
                raise ValidationError({
                    "agents_eligible_share": f"agents_eligible_share doit être <= total_agents ({total_agents})."
                })


class StaffUserRole(models.TextChoices):
    MANAGER = "manager", "Manager"
    FINANCE = "finance", "Finance"
    OPERATOR = "operator", "Opérateur"


class StaffUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staffuser")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="staff_users")

    role = models.CharField(max_length=20, choices=StaffUserRole.choices)
    is_active = models.BooleanField(default=True)

    can_view_dashboard = models.BooleanField(default=True)
    can_manage_agents = models.BooleanField(default=False)
    can_manage_results = models.BooleanField(default=False)
    can_view_finance = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.borlette.nom_borlette})"


class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    commission_percent = models.IntegerField(default=10)

    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class Referral(models.Model):
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE)
    new_user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.promo.code} -> {self.new_user.username}"


class FinancialTransactionType(models.TextChoices):
    ACTIVATION = "activation", "Activation"
    SUBSCRIPTION = "subscription", "Abonnement"


class FinancialTransaction(models.Model):
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="financial_transactions")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True)

    type = models.CharField(max_length=32, choices=FinancialTransactionType.choices)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    months_active = models.PositiveIntegerField(default=0)
    agents_count = models.PositiveIntegerField(default=0)
    eligible_agents = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["borlette", "created_at"], name="idx_ftx_borlette_ca"),
            models.Index(fields=["borlette", "type", "created_at"], name="idx_ftx_borlette_ty"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.borlette.nom_borlette} {self.type} {self.total_amount}"


class FinancialSplitRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ASSOCIATE_1 = "associate_1", "Associé 1"
    ASSOCIATE_2 = "associate_2", "Associé 2"
    AFFILIATE = "affiliate", "Affilié"
    CASH = "cash", "Caisse"


class FinancialSplit(models.Model):
    transaction = models.ForeignKey(FinancialTransaction, on_delete=models.CASCADE, related_name="splits")

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=32, choices=FinancialSplitRole.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction", "role"], name="idx_fsplit_tx_role"),
            models.Index(fields=["user", "created_at"], name="idx_fsplit_user_ca"),
        ]
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.transaction_id} {self.role} {self.amount}"


class WithdrawalStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    APPROVED = "approved", "Approuvé"
    REJECTED = "rejected", "Refusé"
    PAID = "paid", "Payé"


class WithdrawalRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="withdrawal_requests")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=WithdrawalStatus.choices, default=WithdrawalStatus.PENDING)
    payment_method = models.CharField(max_length=20, choices=[
        ("moncash", "MonCash"),
        ("natcash", "NatCash"),
        ("western_union", "Western Union"),
    ], blank=True, null=True)
    
    # Informations de paiement de l'affilié au moment du retrait
    payment_phone = models.CharField(max_length=20, blank=True, null=True)
    payment_full_name = models.CharField(max_length=100, blank=True, null=True)
    payment_location = models.CharField(max_length=100, blank=True, null=True)
    
    # Preuve de paiement (screenshot uploadé par l'admin)
    proof_screenshot = models.ImageField(upload_to="withdrawal_proofs/%Y/%m/", blank=True, null=True, help_text="Screenshot de preuve de paiement")
    
    # Notes de l'admin
    admin_notes = models.TextField(blank=True, default="", help_text="Notes de l'administrateur")
    
    # Traité par (superuser)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_withdrawals")

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Date limite de traitement (48h)
    expected_by = models.DateTimeField(null=True, blank=True, help_text="Date limite de traitement (48h)")

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_withdraw_user_ca"),
            models.Index(fields=["status", "created_at"], name="idx_withdraw_status"),
            models.Index(fields=["expected_by"], name="idx_withdraw_expected"),
        ]
        ordering = ["-created_at"]
    
    def save(self, *args, **kwargs):
        if self.status == WithdrawalStatus.PENDING and not self.expected_by:
            from django.utils import timezone
            self.expected_by = timezone.now() + timezone.timedelta(hours=48)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} {self.amount} {self.status}"


class AgentStatus(models.TextChoices):
    ACTIF = "ACTIF", "Actif"
    SUSPENDU = "SUSPENDU", "Suspendu"


class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agent")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="agents")

    nom = models.CharField(max_length=150)
    telephone = models.CharField(max_length=50)
    zone = models.CharField(max_length=120)
    statut = models.CharField(max_length=16, choices=AgentStatus.choices, default=AgentStatus.ACTIF)

    commission = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    solde_actuel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_ventes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_benefice = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    date_creation = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)

    # GPS coordinates tracking
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_location_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.nom

    @property
    def is_online(self) -> bool:
        """Agent is online if heartbeat within last 2 minutes."""
        if not self.last_seen_at:
            return False
        return timezone.now() - self.last_seen_at <= timezone.timedelta(minutes=2)

    @property
    def etat_connexion(self) -> str:
        if self.is_online:
            return "CONNECTE"
        return "HORS_LIGNE"

    @property
    def solde_caisse_calculé(self) -> Decimal:
        """
        Solde de caisse physique de l'agent.
        Formule : Somme directe de toutes les transactions de caisse.
        """
        from agent_portal.models import AgentCashboxEntry
        return AgentCashboxEntry.get_agent_cashbox_balance(self).get("balance")



class TirageType(models.TextChoices):
    JOUR = "JOUR", "Jour"
    SOIR = "SOIR", "Soir"
    SPECIAL = "SPECIAL", "Spécial"


class TirageStatus(models.TextChoices):
    ACTIF = "ACTIF", "Actif"
    SUSPENDU = "SUSPENDU", "Suspendu"


class Tirage(models.Model):
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="tirages")

    nom = models.CharField(max_length=120)
    code = models.CharField(max_length=50, blank=True)
    pays = models.CharField(max_length=50, default="USA")
    ville = models.CharField(max_length=50, blank=True)
    type = models.CharField(max_length=16, choices=TirageType.choices, default=TirageType.JOUR)
    jours_actifs = models.JSONField(default=list)

    heure_ouverture = models.TimeField(blank=True, null=True)
    heure_fermeture = models.TimeField(blank=True, null=True)
    heure_tirage = models.TimeField(blank=True, null=True)

    is_default = models.BooleanField(default=False)
    modifiable = models.BooleanField(default=True)
    source_api_locked = models.BooleanField(default=True)

    logo = models.ImageField(upload_to="tirages_logos/", null=True, blank=True)

    fermeture_auto = models.BooleanField(default=True)
    mariage_automatique = models.BooleanField(
        default=False,
        help_text="Activer les mariages automatiques pour ce tirage"
    )
    statut = models.CharField(max_length=16, choices=TirageStatus.choices, default=TirageStatus.ACTIF)
    ordre_affichage = models.PositiveIntegerField(default=0)

    # Session key: change à chaque réouverture du tirage
    session_key = models.UUIDField(default=uuid.uuid4, db_index=True)
    session_started_at = models.DateTimeField(default=timezone.now)
    
    # Tracking fermeture/ouverture automatique
    last_opened_at = models.DateTimeField(null=True, blank=True)
    last_closed_at = models.DateTimeField(null=True, blank=True)
    # Cache du dernier état connu (pour détecter les transitions)
    cached_state = models.CharField(max_length=10, default="", blank=True)

    # Legacy fields (kept for backward compatibility)
    resultat = models.TextField(blank=True, null=True)
    date_resultat = models.DateField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["borlette", "code"], name="uniq_tirage_code_per_borlette"),
        ]

    def __str__(self) -> str:
        return self.nom

    def save(self, *args, **kwargs):
        if not (self.code or "").strip():
            self.code = f"CUSTOM_{uuid.uuid4().hex[:10].upper()}"
        return super().save(*args, **kwargs)

    def is_closed(self) -> bool:
        now_t = timezone.localtime(timezone.now()).time()
        return bool(self.heure_fermeture and now_t > self.heure_fermeture)

    def minutes_to_close(self) -> int:
        now_dt = timezone.localtime(timezone.now())
        now_t = now_dt.time()
        fermeture = self.heure_fermeture
        if not fermeture:
            return 0

        close_dt = datetime.combine(now_dt.date(), fermeture)
        now_cmp = datetime.combine(now_dt.date(), now_t)
        if close_dt < now_cmp:
            close_dt = datetime.combine(now_dt.date() + timezone.timedelta(days=1), fermeture)
        delta = close_dt - now_cmp
        minutes = int(delta.total_seconds() / 60)
        return max(0, minutes)

    def clean(self):
        super().clean()

        if self.source_api_locked and self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("heure_tirage", flat=True).first()
            if old and self.heure_tirage and self.heure_tirage != old:
                raise ValidationError("L'heure de tirage est verrouillée (source API).")

        if self.pk:
            old = type(self).objects.get(pk=self.pk)

            if old.is_closed():
                raise ValidationError("Impossible de modifier un tirage déjà fermé")

            if Resultat.objects.filter(tirage_id=self.pk, session_key=old.session_key).exists():
                raise ValidationError("Modification interdite: résultat déjà publié")

        if self.heure_ouverture and self.heure_fermeture and not (self.heure_ouverture < self.heure_fermeture):
            raise ValidationError("heure_ouverture doit être < heure_fermeture")

        if self.heure_fermeture and self.heure_tirage and not (self.heure_fermeture < self.heure_tirage):
            raise ValidationError("heure_fermeture doit être < heure_tirage")

        if self.heure_ouverture and self.heure_tirage and not (self.heure_ouverture < self.heure_tirage):
            raise ValidationError("heure_ouverture doit être < heure_tirage")

    def get_icon_name(self):
        code = (self.code or "").upper()

        if code.startswith("NY"):
            return "ny.png"
        elif code.startswith("FL"):
            return "fl.png"
        elif code.startswith("GA"):
            return "ga.png"
        elif code.startswith("TN"):
            return "tn.png"
        elif code.startswith("CHI"):
            return "chi.png"

        return "default.png"

    def get_icon_emoji(self):
        code = (self.code or "").upper()

        if code.startswith("NY"):
            return "🗽"
        elif code.startswith("FL"):
            return "🌴"
        elif code.startswith("GA"):
            return "🍑"
        elif code.startswith("TN"):
            return "🎸"
        elif code.startswith("CHI"):
            return "🏙️"

        return "🎯"

    @property
    def jours_actifs_display(self) -> str:
        labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        days = self.jours_actifs or []
        if not days:
            return "Tous"
        try:
            return ", ".join([labels[int(d)] for d in days])
        except Exception:
            return "—"

    @property
    def est_suspendu(self) -> bool:
        return self.statut == TirageStatus.SUSPENDU

    @property
    def etat_ouverture(self) -> str:
        if self.est_suspendu:
            return "FERME"

        now = timezone.localtime(timezone.now())
        weekday = now.weekday()
        active_days = self.jours_actifs or []
        if active_days and weekday not in active_days:
            return "FERME"

        t = now.time()
        
        # Si l'heure de tirage n'est pas définie, le tirage est ouvert par défaut
        if not self.heure_tirage:
            return "OUVERT"
        
        from datetime import timedelta, datetime, time
        
        # Calculer l'heure de fermeture (tirage - 5 minutes)
        fermeture_time = (datetime.combine(datetime.min, self.heure_tirage) - timedelta(minutes=5)).time()
        
        t_10_00 = time(10, 0)
        t_14_30 = time(14, 30)
        t_18_00 = time(18, 0)
        t_23_34 = time(23, 34)
        t_02_00 = time(2, 0)
        t_10_00_am = time(10, 0)
        
        # Draws with results scheduled between 10:00 and 14:30 open at 02:00 AM
        if t_10_00 <= self.heure_tirage <= t_14_30:
            if t_02_00 <= t < fermeture_time:
                return "OUVERT"
            return "FERME"
            
        # Draws with results scheduled between 18:00 and 23:34 open at 10:00 AM
        elif t_18_00 <= self.heure_tirage <= t_23_34:
            if t_10_00_am <= t < fermeture_time:
                return "OUVERT"
            return "FERME"
            
        # Default behavior: closed between closure and re-opening (+30 min)
        else:
            reouverture_time = (datetime.combine(datetime.min, self.heure_tirage) + timedelta(minutes=30)).time()
            if fermeture_time <= t < reouverture_time:
                return "FERME"
            return "OUVERT"

    def rotate_session(self) -> None:
        """Génère une nouvelle session_key (appelé à la réouverture du tirage)."""
        self.session_key = uuid.uuid4()
        self.session_started_at = timezone.now()
        self.save(update_fields=["session_key", "session_started_at"])

    def needs_session_rotation(self) -> bool:
        """Vérifie si le tirage a besoin d'une nouvelle session.
        
        Retourne True si:
        - Le tirage est OUVERT
        - ET session_started_at est d'un jour précédent OU avant l'heure d'ouverture d'aujourd'hui
        """
        if self.etat_ouverture != "OUVERT":
            return False

        now = timezone.localtime(timezone.now())
        session_start = timezone.localtime(self.session_started_at)

        # Si la session a commencé un jour différent
        if session_start.date() < now.date():
            return True

        # Si la session a commencé avant l'heure d'ouverture aujourd'hui
        # (cas où le serveur tourne depuis avant l'ouverture)
        if session_start.date() == now.date() and self.heure_ouverture and session_start.time() < self.heure_ouverture:
            return True

        return False

    def ensure_current_session(self) -> None:
        """S'assure que la session est à jour, rotate si nécessaire."""
        if self.needs_session_rotation():
            self.rotate_session()


class AdminPaymentSettings(models.Model):
    borlette = models.OneToOneField(Borlette, on_delete=models.CASCADE, related_name="payment_settings")

    boule_1er_lot_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    boule_2eme_lot_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    boule_3eme_lot_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    loto3_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loto4_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loto5_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    mariage_normal_coeff = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    mariage_gratuit_actif = models.BooleanField(default=False)

    mariage_gratuit_seuil1 = models.PositiveIntegerField(default=4)
    mariage_gratuit_qty1 = models.PositiveIntegerField(default=3)

    mariage_gratuit_seuil2 = models.PositiveIntegerField(default=10)
    mariage_gratuit_qty2 = models.PositiveIntegerField(default=6)

    mariage_gratuit_montant_fixe = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    max_boule = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("50000"), validators=[MinValueValidator(0)])
    max_loto3 = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("50000"), validators=[MinValueValidator(0)])
    max_loto4 = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("50000"), validators=[MinValueValidator(0)])
    max_loto5 = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("50000"), validators=[MinValueValidator(0)])
    max_mariage = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("50000"), validators=[MinValueValidator(0)])

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Paiements: {self.borlette.nom_borlette}"


class TirageCombiType(models.TextChoices):
    MARIAGE = "mariage", "Mariage"
    LOTO3 = "loto3", "Loto 3"
    LOTO4 = "loto4", "Loto 4"
    LOTO5 = "loto5", "Loto 5"


class TirageNumeroStats(models.Model):
    tirage = models.ForeignKey(Tirage, on_delete=models.CASCADE, related_name="numero_stats")
    numero = models.CharField(
        max_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="numero doit être au format 00 à 99")],
    )

    mises_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    plafond_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    bloque_auto = models.BooleanField(default=False)
    bloque_admin = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tirage", "numero"], name="uniq_tirage_numero"),
        ]
        indexes = [
            models.Index(fields=["tirage", "numero"], name="idx_tirage_numero"),
            models.Index(fields=["tirage", "bloque_auto"], name="idx_tirage_num_ba"),
            models.Index(fields=["tirage", "bloque_admin"], name="idx_tirage_num_bm"),
        ]

    def __str__(self) -> str:
        return f"{self.tirage.nom} · {self.numero}"


class TirageCombiStats(models.Model):
    tirage = models.ForeignKey(Tirage, on_delete=models.CASCADE, related_name="combi_stats")
    jeu_type = models.CharField(max_length=20, choices=TirageCombiType.choices)
    valeur = models.CharField(max_length=10)

    mises_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    plafond_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    bloque_auto = models.BooleanField(default=False)
    bloque_admin = models.BooleanField(default=False)
    bloque_derived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tirage", "jeu_type", "valeur"], name="uniq_tirage_combi"),
        ]
        indexes = [
            models.Index(fields=["tirage", "jeu_type"], name="idx_tirage_combi_j"),
            models.Index(fields=["tirage", "jeu_type", "valeur"], name="idx_tirage_combi_v"),
            models.Index(fields=["tirage", "bloque_auto"], name="idx_tirage_com_ba"),
            models.Index(fields=["tirage", "bloque_admin"], name="idx_tirage_com_bm"),
        ]

    def __str__(self) -> str:
        return f"{self.tirage.nom} · {self.jeu_type}:{self.valeur}"


class Resultat(models.Model):
    """Résultat d'un tirage avec les 3 lots et calculs automatiques des combinaisons.
    
    Lié à session_key pour isolation par session de tirage.
    Un seul résultat par (tirage, session_key).
    """
    tirage = models.ForeignKey(Tirage, on_delete=models.CASCADE, related_name="resultats")
    session_key = models.UUIDField(db_index=True, default=uuid.uuid4)
    date = models.DateField()
    
    # Les 3 lots de base (00-99)
    lot1 = models.CharField(
        max_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="lot doit être au format 00 à 99")],
    )
    lot2 = models.CharField(
        max_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="lot doit être au format 00 à 99")],
    )
    lot3 = models.CharField(
        max_length=2,
        validators=[RegexValidator(r"^\d{2}$", message="lot doit être au format 00 à 99")],
    )
    
    # Chiffre ajouté pour loto3 (0-9)
    chiffre_loto3 = models.CharField(
        max_length=1,
        validators=[RegexValidator(r"^\d$", message="chiffre doit être 0 à 9")],
    )

    # Loto4 - 3 options (1er, 2ème, 3ème)
    loto4_option1 = models.CharField(
        max_length=4,
        blank=True,
        default="",
        validators=[RegexValidator(r"^\d{4}$", message="Loto4 doit être 4 chiffres")],
        help_text="1ère option Loto4",
    )
    loto4_option2 = models.CharField(
        max_length=4,
        blank=True,
        default="",
        validators=[RegexValidator(r"^\d{4}$", message="Loto4 doit être 4 chiffres")],
        help_text="2ème option Loto4",
    )
    loto4_option3 = models.CharField(
        max_length=4,
        blank=True,
        default="",
        validators=[RegexValidator(r"^\d{4}$", message="Loto4 doit être 4 chiffres")],
        help_text="3ème option Loto4",
    )

    # Loto5 - 2 options (1er et 2ème)
    loto5_option1 = models.CharField(
        max_length=5,
        blank=True,
        default="",
        validators=[RegexValidator(r"^\d{5}$", message="Loto5 doit être 5 chiffres")],
        help_text="1ère option Loto5",
    )
    loto5_option2 = models.CharField(
        max_length=5,
        blank=True,
        default="",
        validators=[RegexValidator(r"^\d{5}$", message="Loto5 doit être 5 chiffres")],
        help_text="2ème option Loto5",
    )

    complementaire = models.CharField(
        max_length=1,
        blank=True,
        default="",
        validators=[RegexValidator(r"^\d$", message="chiffre doit être 0 à 9")],
    )
    
    # Verrouillage après calcul des gains
    locked = models.BooleanField(default=False)
    computed_at = models.DateTimeField(null=True, blank=True)

    source = models.CharField(max_length=50, default="API")
    statut = models.CharField(
        max_length=20,
        choices=[
            ("pending", "En attente"),
            ("validated", "Validé"),
            ("rejected", "Rejeté"),
        ],
        default="pending",
    )
    is_suspicious = models.BooleanField(default=False)

    validated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_resultats",
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    rejected_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_resultats",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tirage", "session_key"], name="uniq_tirage_session_resultat"),
        ]
        indexes = [
            models.Index(fields=["tirage", "session_key"], name="idx_resultat_tirage_sess"),
            models.Index(fields=["tirage", "date"], name="idx_resultat_tirage_date"),
        ]
        ordering = ["-date", "-created_at"]
    
    def save(self, *args, **kwargs):
        # Nettoyer complementaire et chiffre_loto3
        c = (self.complementaire or "").strip() or (self.chiffre_loto3 or "").strip()
        if c:
            self.complementaire = c
            self.chiffre_loto3 = c
        
        # Calculer automatiquement les combinaisons loto
        if self.lot1 and self.lot2 and self.lot3:
            self.loto4_option1 = f"{self.lot1}{self.lot2}"
            self.loto4_option2 = f"{self.lot1}{self.lot3}"
            self.loto4_option3 = f"{self.lot2}{self.lot3}"
            
            l3 = f"{c}{self.lot1}" if c else ""
            if l3:
                self.loto5_option1 = f"{l3}{self.lot2}"
                self.loto5_option2 = f"{l3}{self.lot3}"
                
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.tirage.nom} {self.date} - {self.lot1}/{self.lot2}/{self.lot3}"
    
    @property
    def loto3(self) -> str:
        """Loto3 = chiffre + lot1 (ex: 9 + 23 = 923)"""
        c = (self.complementaire or "").strip() or (self.chiffre_loto3 or "").strip()
        return f"{c}{self.lot1}" if c and self.lot1 else ""
    
    @property
    def loto4_opt1(self) -> str:
        """Loto4 option 1 = 1er lot + 2eme lot"""
        return f"{self.lot1}{self.lot2}" if self.lot1 and self.lot2 else ""
    
    @property
    def loto4_opt2(self) -> str:
        """Loto4 option 2 = 1er lot + 3eme lot"""
        return f"{self.lot1}{self.lot3}" if self.lot1 and self.lot3 else ""
    
    @property
    def loto4_opt3(self) -> str:
        """Loto4 option 3 = 2eme lot + 3eme lot"""
        return f"{self.lot2}{self.lot3}" if self.lot2 and self.lot3 else ""
    
    @property
    def loto5_opt1(self) -> str:
        """Loto5 option 1 = loto3 + 2eme lot"""
        return f"{self.loto3}{self.lot2}" if self.loto3 and self.lot2 else ""
    
    @property
    def loto5_opt2(self) -> str:
        """Loto5 option 2 = loto3 + 3eme lot"""
        return f"{self.loto3}{self.lot3}" if self.loto3 and self.lot3 else ""

    @property
    def loto5_opt3(self) -> str:
        """Loto5 option 3 = dernier chiffre du premier lot + 2eme lot + 3eme lot"""
        if self.lot1 and self.lot2 and self.lot3:
            return f"{self.lot1[-1]}{self.lot2}{self.lot3}"
        return ""



class LotteryAPIConfig(models.Model):
    api_url = models.URLField()
    api_key = models.CharField(max_length=255)

    is_active = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)


class AuditAction(models.TextChoices):
    TICKET_CREATE = "TICKET_CREATE", "Ticket Create"
    TICKET_VOID = "TICKET_VOID", "Ticket Void"
    TICKET_PAYOUT = "TICKET_PAYOUT", "Ticket Payout"
    RESULTS_SET = "RESULTS_SET", "Results Set"
    RESULTS_RESET = "RESULTS_RESET", "Results Reset"
    RESULTS_VALIDATE = "RESULTS_VALIDATE", "Results Validate"
    RESULTS_REJECT = "RESULTS_REJECT", "Results Reject"
    RESULTS_PENDING = "RESULTS_PENDING", "Results Pending"
    RESULTS_FLAG = "RESULTS_FLAG", "Results Flag"

    STAFF_CREATE = "STAFF_CREATE", "Staff Create"
    STAFF_UPDATE = "STAFF_UPDATE", "Staff Update"
    STAFF_TOGGLE_ACTIVE = "STAFF_TOGGLE_ACTIVE", "Staff Toggle Active"
    RESULTS_EDIT = "RESULTS_EDIT", "Results Edit"
    RISK_BLOCK_ADD = "RISK_BLOCK_ADD", "Risk Block Add"
    RISK_BLOCK_REMOVE = "RISK_BLOCK_REMOVE", "Risk Block Remove"
    AGENT_COMMISSION_PAYOUT = "AGENT_COMMISSION_PAYOUT", "Agent Commission Payout"
    AGENT_CASHBOX_WITHDRAWAL = "AGENT_CASHBOX_WITHDRAWAL", "Agent Cashbox Withdrawal"
    AGENT_CASHBOX_REPLENISH = "AGENT_CASHBOX_REPLENISH", "Agent Cashbox Replenish"
    EXPENSE_CREATE = "EXPENSE_CREATE", "Expense Create"
    EXPENSE_UPDATE = "EXPENSE_UPDATE", "Expense Update"
    EXPENSE_DELETE = "EXPENSE_DELETE", "Expense Delete"
    LOGIN_ADMIN = "LOGIN_ADMIN", "Login Admin"
    LOGIN_AGENT = "LOGIN_AGENT", "Login Agent"
    BORLETTE_UPDATE = "BORLETTE_UPDATE", "Borlette Update"
    FINANCIAL_DISTRIBUTION_CALC = "FINANCIAL_DISTRIBUTION_CALC", "Financial Distribution Calc"
    WITHDRAWAL_CREATE = "WITHDRAWAL_CREATE", "Withdrawal Create"
    WITHDRAWAL_APPROVE = "WITHDRAWAL_APPROVE", "Withdrawal Approve"
    WITHDRAWAL_REJECT = "WITHDRAWAL_REJECT", "Withdrawal Reject"
    WITHDRAWAL_MARK_PAID = "WITHDRAWAL_MARK_PAID", "Withdrawal Mark Paid"
    # Offline mode audit actions
    DEVICE_REGISTER = "DEVICE_REGISTER", "Device Register"
    OFFLINE_TICKET_QUEUED = "OFFLINE_TICKET_QUEUED", "Offline Ticket Queued"
    OFFLINE_SYNC_SUCCESS = "OFFLINE_SYNC_SUCCESS", "Offline Sync Success"
    OFFLINE_SYNC_FAILED = "OFFLINE_SYNC_FAILED", "Offline Sync Failed"
    OFFLINE_TAMPER_BLOCKED = "OFFLINE_TAMPER_BLOCKED", "Offline Tamper Blocked"
    OFFLINE_BATCH_PARTIAL = "OFFLINE_BATCH_PARTIAL", "Offline Batch Partial"


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    borlette = models.ForeignKey(Borlette, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    actor_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    actor_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")

    action = models.CharField(max_length=64, choices=AuditAction.choices)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=128)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["borlette", "created_at"], name="idx_audit_borlette_ca"),
            models.Index(fields=["action", "created_at"], name="idx_audit_action_ca"),
            models.Index(fields=["entity_type", "entity_id"], name="idx_audit_entity"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at} {self.action} {self.entity_type}:{self.entity_id}"


class AgentPayout(models.Model):
    """Paiement effectué à un agent (solde = commissions - payouts)."""
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="payouts")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="agent_payouts", null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_payouts_created"
    )
    note = models.TextField(blank=True, default="")
    
    # Snapshot période pour audit
    snapshot_period_start = models.DateField(null=True, blank=True)
    snapshot_period_end = models.DateField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["agent", "created_at"], name="idx_payout_agent_dt"),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"{self.agent.nom} - {self.amount} - {self.created_at}"


class AgentDevice(models.Model):
    """Device registration for offline ticket HMAC signing."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=64, unique=True, db_index=True)
    device_secret = models.CharField(max_length=128)  # HMAC secret
    device_name = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["agent", "is_active"], name="idx_device_agent_active"),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"{self.agent.nom} - {self.device_name or self.device_id[:8]}"
    
    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])


class ExpenseCategory(models.Model):
    """Catégorie de dépense pour une borlette."""
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="expense_categories")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("borlette", "name")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Expense(models.Model):
    """Dépense enregistrée pour une borlette.
    
    Bénéfice Net = Mises - Gains Dus - Commissions - Dépenses
    """
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="expenses")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses_created"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses"
    )
    description = models.TextField()


class AffiliateProfile(models.Model):
    """Profil pour les utilisateurs avec le rôle AFFILIATE.
    
    Stocke les informations spécifiques aux partenaires affiliés:
    - Code promo unique pour le parrainage
    - Gains et commissions
    - Filleuls (référés)
    - Permissions pour donner les résultats des tirages
    - Informations de paiement pour les retraits
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="affiliate_profile")
    
    # Code promo unique pour le parrainage
    promo_code = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Gains et commissions
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Commission par défaut (peut être personnalisée)
    commission_percent = models.IntegerField(default=20, help_text="Commission en pourcentage")
    
    # Statistiques
    total_referrals = models.PositiveIntegerField(default=0)
    active_referrals = models.PositiveIntegerField(default=0)
    
    # Informations de paiement pour les retraits
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ("moncash", "MonCash"),
            ("natcash", "NatCash"),
            ("western_union", "Western Union"),
        ],
        blank=True,
        null=True,
        help_text="Méthode de paiement préférée"
    )
    # Numéro de téléphone pour MonCash/NatCash
    payment_phone = models.CharField(max_length=20, blank=True, null=True, help_text="Numéro pour MonCash/NatCash")
    # Nom complet pour Western Union
    payment_full_name = models.CharField(max_length=100, blank=True, null=True, help_text="Nom complet pour Western Union")
    # Ville/Localisation pour Western Union
    payment_location = models.CharField(max_length=100, blank=True, null=True, help_text="Ville/Localisation pour Western Union")
    
    # Permissions
    can_submit_results = models.BooleanField(
        default=False,
        help_text="Permet à l'affilié de soumettre les résultats des tirages par défaut"
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["promo_code"], name="idx_aff_promo"),
            models.Index(fields=["user"], name="idx_aff_user"),
            models.Index(fields=["is_active"], name="idx_aff_active"),
        ]
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"Affiliate: {self.user.username} ({self.promo_code})"
    
    def save(self, *args, **kwargs):
        # Générer un code promo unique si non fourni
        if not self.promo_code:
            import random
            import string
            prefix = "GAB"
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.promo_code = f"{prefix}{suffix}"
        super().save(*args, **kwargs)
    
    @property
    def referrals(self):
        """Retourne tous les filleuls (référés) de cet affilié."""
        return Referral.objects.filter(promo__owner=self.user).select_related('new_user')
    
    @property
    def active_referrals_count(self):
        """Retourne le nombre de filleuls actifs (avec une borlette)."""
        return self.referrals.filter(new_user__borlette__isnull=False).count()


class MariageBlock(models.Model):
    """Blocage manuel d'une combinaison mariage pour un tirage.
    
    Phase J: Blocage manuel des mariages par tirage.
    Les blocs auto sont calculés à partir des boules bloquées (TirageNumeroStats),
    pas persistés ici.
    """
    tirage = models.ForeignKey(Tirage, on_delete=models.CASCADE, related_name="mariage_blocks")
    
    # Deux boules format 00-99 (stockées comme int pour faciliter les comparaisons)
    # Toujours stocké avec a < b pour normalisation
    boule_a = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(99)])
    boule_b = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(99)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="mariage_blocks_created"
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tirage", "boule_a", "boule_b"], 
                name="uniq_tirage_mariage_block"
            ),
        ]
        indexes = [
            models.Index(fields=["tirage", "boule_a", "boule_b"], name="idx_mariage_block_lookup"),
        ]
        ordering = ["boule_a", "boule_b"]
    
    def __str__(self):
        return f"{self.tirage.nom} · {self.boule_a:02d}x{self.boule_b:02d}"
    
    @property
    def combo_display(self) -> str:
        """Format d'affichage: 44x30"""
        return f"{self.boule_a:02d}x{self.boule_b:02d}"
    
    @property
    def combo_reverse_display(self) -> str:
        """Format inverse: 30x44"""
        return f"{self.boule_b:02d}x{self.boule_a:02d}"
    
    @classmethod
    def is_blocked(cls, tirage_id: int, a: str, b: str) -> bool:
        """Vérifie si la combinaison mariage (a, b) est bloquée pour un tirage.
        Normalise a < b avant la recherche.
        """
        try:
            ia, ib = int(a), int(b)
        except (ValueError, TypeError):
            return False
        if ia > ib:
            ia, ib = ib, ia
        return cls.objects.filter(tirage_id=tirage_id, boule_a=ia, boule_b=ib).exists()

    @classmethod
    def get_blocked_combos(cls, tirage_id: int) -> set[tuple[str, str]]:
        """Retourne l'ensemble des combinaisons mariage bloquées manuellement sous forme de tuples (a, b) de chaînes formatées (00-99)."""
        blocks = cls.objects.filter(tirage_id=tirage_id)
        return {(f"{b.boule_a:02d}", f"{b.boule_b:02d}") for b in blocks}

    def clean(self):
        """Normalise pour que boule_a < boule_b"""
        if self.boule_a > self.boule_b:
            self.boule_a, self.boule_b = self.boule_b, self.boule_a


class PartnerProfile(models.Model):
    """Profil pour les partenaires avec accès limités.
    
    Les partenaires peuvent:
    - Donner les résultats des tirages
    - Confirmer les paiements des affiliés
    - Renouveler les abonnements des directeurs
    
    Les partenaires NE peuvent PAS:
    - Voir les montants d'argent accumulés
    - Voir le nombre d'agents par borlette
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="partner_profile")
    
    # Permissions spécifiques
    can_submit_results = models.BooleanField(default=True, help_text="Peut soumettre les résultats des tirages")
    can_confirm_affiliate_payments = models.BooleanField(default=True, help_text="Peut confirmer les paiements des affiliés")
    can_renew_subscriptions = models.BooleanField(default=True, help_text="Peut renouveler les abonnements des directeurs")
    
    # Accès aux borlettes spécifiques (si vide = accès à toutes)
    allowed_borlettes = models.ManyToManyField(Borlette, blank=True, related_name="partners", help_text="Borlettes accessibles (vide = toutes)")
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"Partner: {self.user.username}"


class SubscriptionType(models.TextChoices):
    """Types d'abonnement disponibles."""
    TRIAL = "trial", "Essai Gratuit"
    STANDARD = "standard", "Standard"
    PREMIUM = "premium", "Premium"
    MONTHLY = "mensuel", "Mensuel"

class Subscription(models.Model):
    """Abonnement d'un directeur à une borlette."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    borlette = models.ForeignKey(
        Borlette,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    subscription_type = models.CharField(
        max_length=50,
        choices=SubscriptionType.choices,
        default=SubscriptionType.STANDARD,
        help_text="Type d'abonnement",
    )
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Preuve de paiement pour le renouvellement
    payment_proof = models.FileField(
        upload_to='payment_proofs/%Y/%m/',
        null=True,
        blank=True,
        help_text="Preuve de paiement (capture d'écran, reçu, etc.)",
        verbose_name="Preuve de paiement"
    )
    payment_proof_uploaded_at = models.DateTimeField(null=True, blank=True)
    
    def is_trial_active(self):
        """Vérifie si l'essai gratuit est encore actif."""
        from django.utils import timezone
        if self.subscription_type == SubscriptionType.TRIAL:
            return timezone.now().date() <= self.end_date
        return False
    
    def is_trial_expired(self):
        """Vérifie si l'essai gratuit a expiré."""
        from django.utils import timezone
        if self.subscription_type == SubscriptionType.TRIAL:
            return timezone.now().date() > self.end_date
        return False
    
    def get_subscription_status(self):
        """Retourne le statut de l'abonnement."""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Si essai gratuit et a dépassé 30 jours, on passe à mensuel
        if self.subscription_type == SubscriptionType.TRIAL:
            if (today - self.start_date).days >= 30:
                self.subscription_type = SubscriptionType.MONTHLY
                self.save(update_fields=["subscription_type"])
                
        if not self.is_active:
            return "inactive"
        if self.subscription_type == SubscriptionType.TRIAL:
            if self.is_trial_expired():
                return "trial_expired"
            return "trial_active"
        if timezone.now().date() > self.end_date:
            return "expired"
        return "active"
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"

    def __str__(self) -> str:
        return f"{self.user.username} - {self.borlette.nom_borlette} ({self.start_date} à {self.end_date})"


class DocumentationVideo(models.Model):
    """Modèle pour stocker les vidéos YouTube de la documentation."""
    title = models.CharField(max_length=255, verbose_name="Titre de la vidéo")
    youtube_url = models.URLField(verbose_name="URL YouTube")
    youtube_video_id = models.CharField(max_length=50, verbose_name="ID de la vidéo YouTube")
    description = models.TextField(blank=True, verbose_name="Description")
    category = models.CharField(max_length=100, blank=True, verbose_name="Catégorie")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Vidéo de documentation"
        verbose_name_plural = "Vidéos de documentation"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        """Extrait l'ID vidéo YouTube de l'URL automatiquement."""
        if self.youtube_url and not self.youtube_video_id:
            self.youtube_video_id = self.extract_video_id(self.youtube_url)
        super().save(*args, **kwargs)

    @staticmethod
    def extract_video_id(url):
        """Extrait l'ID de la vidéo YouTube depuis l'URL."""
        import re
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\?\/]+)',
            r'youtube\.com\/watch\?v=([^&]+)',
            r'youtu\.be\/([^?]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None


class AdminTiragePreference(models.Model):
    """Préférences d'activation des tirages par admin.
    
    Chaque admin peut activer/désactiver des tirages indépendamment.
    Si désactivé, le tirage n'apparaît pas pour les agents de cet admin.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tirage_preferences")
    tirage = models.ForeignKey(Tirage, on_delete=models.CASCADE, related_name="admin_preferences")
    actif = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "tirage"], name="uniq_admin_tirage_pref"),
        ]
        indexes = [
            models.Index(fields=["user", "tirage"], name="idx_admin_tirage"),
            models.Index(fields=["user", "actif"], name="idx_admin_actif"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} · {self.tirage.nom} · {'Actif' if self.actif else 'Inactif'}"


class RecoveryStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    RESOLVED = "RESOLVED", "Résolu"
    REJECTED = "REJECTED", "Rejeté"


class AccountRecoveryRequest(models.Model):
    """Demande de récupération de compte (Admin de Borlette)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_requests")
    borlette = models.ForeignKey(Borlette, on_delete=models.CASCADE, related_name="recovery_requests", null=True, blank=True)

    status = models.CharField(max_length=16, choices=RecoveryStatus.choices, default=RecoveryStatus.PENDING)
    phone_number = models.CharField(max_length=50, blank=True, help_text="Numéro de téléphone de vérification")
    message = models.TextField(blank=True, help_text="Message du client")

    temp_password = models.CharField(max_length=128, blank=True, null=True, help_text="Mot de passe temporaire généré par le superadmin")
    temp_password_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_recoveries")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_recovery_status_ca"),
            models.Index(fields=["user"], name="idx_recovery_user"),
        ]

    def __str__(self) -> str:
        return f"Récupération {self.user.username} - {self.status}"


class GlobalPaymentSettings(models.Model):
    """Configuration globale pour Stripe et MonCash (SuperAdmin)."""
    stripe_public_key = models.CharField(max_length=255, blank=True, default="")
    stripe_secret_key = models.CharField(max_length=255, blank=True, default="")
    
    moncash_client_id = models.CharField(max_length=255, blank=True, default="")
    moncash_secret_key = models.CharField(max_length=255, blank=True, default="")
    moncash_sandbox = models.BooleanField(default=True)
    
    automatic_payments_active = models.BooleanField(default=False)
    
    stripe_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.5"))
    stripe_fee_fixed = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.30"))
    moncash_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.0"))
    moncash_fee_fixed = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.0"))

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration Globale Paiement"
        verbose_name_plural = "Configurations Globales Paiement"

    def __str__(self) -> str:
        return "Configuration Globale Paiement"


class SMTPSettings(models.Model):
    """Configuration SMTP dynamique pour Namecheap/serveur d'envoi d'emails."""
    smtp_host = models.CharField(max_length=255, default="mail.privateemail.com")
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    from_email = models.CharField(max_length=255, blank=True, null=True, help_text="Ex: Gaboom <no-reply@gaboom509.com>")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration SMTP"
        verbose_name_plural = "Configurations SMTP"

    def __str__(self) -> str:
        return f"SMTP {self.smtp_host} ({self.smtp_username})"

