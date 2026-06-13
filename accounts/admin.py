from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.db import transaction

from .forms import BorletteAdminForm
from .models import Borlette, UserRole, FinancialTransaction, FinancialSplit, DocumentationVideo
from accounts.audit import log_audit

User = get_user_model()


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Rôle",
            {
                "fields": ("role",),
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Rôle",
            {
                "fields": ("role",),
            },
        ),
    )

    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "is_superuser")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Borlette)
class BorletteAdmin(admin.ModelAdmin):
    form = BorletteAdminForm
    list_display = ("nom_borlette", "telephone", "agents_eligible_share", "site_web")
    search_fields = ("nom_borlette", "telephone")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        mot_de_passe = form.cleaned_data.get("mot_de_passe")

        old = None
        if change and obj.pk:
            old = Borlette.objects.filter(pk=obj.pk).first()

        if not change:
            user = User(
                username=obj.nom_borlette,
                role=UserRole.ADMIN,
                is_staff=False,
                is_superuser=False,
                is_active=True,
            )
            if mot_de_passe:
                user.set_password(mot_de_passe)
            user.save()
            obj.user = user
            obj.save()
            return

        old_db = Borlette.objects.select_related("user").get(pk=obj.pk)
        obj.save()

        if old_db.user_id:
            user = old_db.user
            if user.username != obj.nom_borlette:
                user.username = obj.nom_borlette
            user.role = UserRole.ADMIN
            user.is_staff = False
            user.is_superuser = False
            if mot_de_passe:
                user.set_password(mot_de_passe)
            user.save()

        if change and old is not None:
            changed: dict[str, object] = {}
            for f in [
                "nom_borlette",
                "adresse",
                "telephone",
                "slogan",
                "site_web",
                "agents_eligible_share",
                "allow_offline_print",
            ]:
                if getattr(old, f, None) != getattr(obj, f, None):
                    changed[f] = {"old": getattr(old, f, None), "new": getattr(obj, f, None)}

            if changed:
                log_audit(
                    action="BORLETTE_UPDATE",
                    entity_type="Borlette",
                    entity_id=str(obj.pk),
                    borlette=obj,
                    actor_user=request.user,
                    meta={"changed": changed},
                    request=request,
                )


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "borlette", "type", "total_amount", "agents_count", "eligible_agents", "months_active", "created_at")
    list_filter = ("type", "created_at")
    search_fields = ("id", "borlette__nom_borlette")
    readonly_fields = ("borlette", "promo_code", "type", "total_amount", "agents_count", "eligible_agents", "months_active", "created_at")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinancialSplit)
class FinancialSplitAdmin(admin.ModelAdmin):
    list_display = ("id", "transaction", "role", "amount", "user", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("transaction__id", "user__username")
    readonly_fields = ("transaction", "role", "amount", "user", "created_at")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentationVideo)
class DocumentationVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "order", "is_active", "created_at")
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("title", "youtube_url", "category")
    list_editable = ("order", "is_active")
    readonly_fields = ("youtube_video_id",)

    fieldsets = (
        (None, {
            "fields": ("title", "youtube_url", "youtube_video_id", "description", "category", "order", "is_active")
        }),
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
