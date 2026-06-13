from django.contrib import admin

from .models import (
    AgentLedgerEntry, AgentCashboxEntry, Ticket, TicketLine, TicketPayout
)


@admin.register(AgentLedgerEntry)
class AgentLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("agent", "borlette", "entry_type", "amount", "created_at", "created_by")
    list_filter = ("borlette", "entry_type", "created_at")
    search_fields = ("agent__user__username", "agent__nom", "description")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    
    def has_change_permission(self, request, obj=None):
        return False  # Ledger entries are immutable
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete


@admin.register(AgentCashboxEntry)
class AgentCashboxEntryAdmin(admin.ModelAdmin):
    list_display = ("agent", "borlette", "entry_type", "amount", "created_at", "related_ticket")
    list_filter = ("borlette", "entry_type", "created_at")
    search_fields = ("agent__nom", "description", "related_ticket__numero_ticket")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(TicketPayout)
class TicketPayoutAdmin(admin.ModelAdmin):
    list_display = ("ticket", "agent", "amount", "created_at", "created_by")
    list_filter = ("borlette", "created_at")
    search_fields = ("ticket__numero_ticket", "agent__nom")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("numero_ticket", "borlette", "agent", "total_mise", "total_gain", "statut", "created_at")
    list_filter = ("borlette", "statut")
    search_fields = ("numero_ticket", "agent__nom", "agent__telephone")


@admin.register(TicketLine)
class TicketLineAdmin(admin.ModelAdmin):
    list_display = ("ticket", "jeu", "valeur", "mise")
    list_filter = ("jeu",)
    search_fields = ("ticket__numero_ticket", "valeur")
