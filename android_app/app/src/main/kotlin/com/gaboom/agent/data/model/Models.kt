package com.gaboom.agent.data.model

import com.google.gson.annotations.SerializedName

/**
 * Modèles de données pour l'API Agent
 */

// ═══════════════════════════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════════════════════════

data class LoginRequest(
    val username: String,
    val password: String,
    @SerializedName("device_signature") val deviceSignature: String
)

data class LoginResponse(
    val success: Boolean,
    val agent: AgentInfo?,
    val borlette: BorletteInfo?,
    val tokens: TokenPair?,
    val error: String?
)

data class AgentInfo(
    val id: Int,
    val nom: String,
    val telephone: String,
    val zone: String,
    val commission: Double
)

data class BorletteInfo(
    val id: Int,
    val nom: String,
    val telephone: String,
    val slogan: String,
    val adresse: String = "",
    @SerializedName("logo_url") val logoUrl: String = "",
    @SerializedName("ticket_footer_text") val ticketFooterText: String = "",
    @SerializedName("mariage_gratuit_actif") val mariageGratuitActif: Boolean = false,
    @SerializedName("mariage_gratuit_montant") val mariageGratuitMontant: String = "0"
)

data class TokenPair(
    val access: String,
    val refresh: String
)

// ═══════════════════════════════════════════════════════════════════════════
// TIRAGES
// ═══════════════════════════════════════════════════════════════════════════

data class TiragesResponse(
    val success: Boolean,
    val tirages: List<Tirage>?,
    @SerializedName("server_time") val serverTime: String?,
    val error: String?
)

data class Tirage(
    val id: Int,
    val nom: String,
    val type: String,
    @SerializedName("heure_ouverture") val heureOuverture: String,
    @SerializedName("heure_fermeture") val heureFermeture: String,
    @SerializedName("heure_tirage") val heureTirage: String,
    val etat: String,
    val jours: String?,
    @SerializedName("session_key") val sessionKey: String? = null
)

data class DisponiblesResponse(
    val success: Boolean,
    @SerializedName("tirage_id") val tirageId: Int?,
    @SerializedName("tirage_nom") val tirageNom: String?,
    val etat: String?,
    val numeros: List<Int>?,
    val combis: CombisDisponibles?,
    val error: String?
)

data class CombisDisponibles(
    val mariage: List<String>?,
    val loto3: List<String>?,
    val loto4: List<String>?,
    val loto5: List<String>?
)

// ═══════════════════════════════════════════════════════════════════════════
// TICKETS
// ═══════════════════════════════════════════════════════════════════════════

data class TicketLine(
    val jeu: String,
    val valeur: String,
    val mise: Double,
    @SerializedName("potentiel_gain") val potentielGain: Double = 0.0,
    val gratuit: Boolean = false,
    val option: Int = 1  // Option LOTO (1, 2, 3) - envoyé au backend
)

/**
 * Extended TicketLine with options support for Loto4/Loto5.
 * Options 1/2/3 are treated as separate bets.
 */
data class TicketLineWithOptions(
    val jeu: String,
    val valeur: String,
    val miseBase: Double,  // Mise de base (before multiplying by options)
    val options: Set<Int> = emptySet(),  // Selected options (1, 2, 3)
    val useGlobalOptions: Boolean = true,  // Whether this line follows global options
    @SerializedName("potentiel_gain") val potentielGain: Double = 0.0,
    val gratuit: Boolean = false
) {
    /**
     * Effective mise = miseBase * number of options for Loto4/5, otherwise miseBase
     */
    val effectiveMise: Double
        get() = if (jeu.lowercase() in listOf("loto4", "loto5")) {
            if (options.isEmpty()) 0.0 else miseBase * options.size
        } else {
            miseBase
        }
    
    /**
     * Convert to API TicketLine(s) - one per option for Loto4/5
     */
    fun toApiLines(): List<TicketLine> {
        return if (jeu.lowercase() in listOf("loto4", "loto5")) {
            if (options.isEmpty()) emptyList()
            else options.map { opt ->
                TicketLine(
                    jeu = jeu, // Sending "loto4" etc as per backend validation mapping
                    valeur = valeur,
                    mise = miseBase,
                    potentielGain = potentielGain,
                    gratuit = gratuit,
                    option = opt
                )
            }
        } else {
            listOf(
                TicketLine(
                    jeu = jeu,
                    valeur = valeur,
                    mise = miseBase,
                    potentielGain = potentielGain,
                    gratuit = gratuit
                )
            )
        }
    }
    
    /**
     * For display: shows options as string (e.g., "Opt1+2" or "Opt1+2+3")
     */
    fun optionsDisplay(): String {
        if (options.isEmpty()) return ""
        return "Opt" + options.sorted().joinToString("+")
    }
}

data class TicketCreateRequest(
    @SerializedName("draw_ids") val drawIds: List<Int>,
    val lines: List<TicketLine>
)

// Multi-tirage
data class MultiTicketEntry(
    val game: String,
    val number: String,
    val stake: Double,
    val gratuit: Boolean = false,
    val option: Int? = null  // Option spécifique pour Loto4/Loto5 (1, 2, ou 3)
)

data class MultiTicketCreateRequest(
    @SerializedName("tirage_ids") val tirageIds: List<Int>,
    val entries: List<MultiTicketEntry>,
    val overrides: Map<String, MultiTicketOverride>? = null,
    @SerializedName("session_key") val sessionKey: String? = null  // Required for offline sync HMAC
)

data class MultiTicketOverride(
    val entries: List<MultiTicketEntry>
)

data class MultiTicketCreateResponse(
    val success: Boolean,
    @SerializedName("group_id") val groupId: String?,
    val tickets: List<MultiTicketInfo>?,
    val failed: List<FailedTirageInfo>?,
    val error: String?
)

data class FailedTirageInfo(
    @SerializedName("tirage_id") val tirageId: Int,
    val error: String
)

data class MultiTicketInfo(
    @SerializedName("tirage_id") val tirageId: Int,
    @SerializedName("tirage_nom") val tirageNom: String,
    @SerializedName("ticket_uuid") val ticketId: String,
    @SerializedName("ticket_no") val ticketNo: String,
    @SerializedName("group_id") val groupId: String? = null,
    @SerializedName("total_mise") val totalMise: Double,
    val lines: List<MultiTicketLineInfo>?
)

data class CreatedTicketInfo(
    val ticketId: String,
    val ticketNo: String,
    val tirageId: Int,
    val tirageNom: String,
    val totalMise: Double,
    val printed: Boolean = false,
    val isOffline: Boolean = false
)

data class MultiTicketLineInfo(
    val jeu: String,
    val valeur: String,
    val mise: Double
)

data class TicketPreviewResponse(
    val success: Boolean,
    @SerializedName("is_valid") val isValid: Boolean?,
    val errors: List<String>?,
    @SerializedName("ticket_number") val ticketNumber: String?,
    val date: String?,
    val time: String?,
    @SerializedName("borlette_name") val borletteName: String?,
    @SerializedName("borlette_slogan") val borletteSlogan: String?,
    @SerializedName("borlette_tel") val borletteTel: String?,
    @SerializedName("agent_name") val agentName: String?,
    @SerializedName("draw_names") val drawNames: List<String>?,
    val lines: List<TicketLine>?,
    @SerializedName("lines_print") val linesPrint: List<String>?,
    @SerializedName("free_marriages") val freeMarriages: List<Map<String, Any>>?,
    @SerializedName("free_marriages_print") val freeMarriagesPrint: List<String>?,
    val error: String?
)

data class TicketCreateResponse(
    val success: Boolean,
    val ticket: TicketInfo?,
    val error: String?
)

data class TicketInfo(
    val id: String,
    val numero: String,
    @SerializedName("group_id") val groupId: String? = null,
    @SerializedName("total_mise") val totalMise: Double,
    @SerializedName("total_gain") val totalGain: Double?,
    val statut: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("closed_at") val closedAt: String?,
    val tirages: List<String>,
    val lines: List<TicketLine>?
)

data class TicketPrintResponse(
    val success: Boolean,
    @SerializedName("print_data") val printData: PrintData?,
    val error: String?
)

data class PrintData(
    @SerializedName("borlette_name") val borletteName: String,
    @SerializedName("borlette_slogan") val borletteSlogan: String,
    @SerializedName("borlette_tel") val borletteTel: String,
    @SerializedName("borlette_adresse") val borletteAdresse: String = "",
    @SerializedName("borlette_site_web") val borletteSiteWeb: String = "",
    @SerializedName("borlette_logo_url") val borletteLogoUrl: String = "",
    @SerializedName("agent_name") val agentName: String,
    @SerializedName("ticket_number") val ticketNumber: String,
    @SerializedName("group_id") val groupId: String? = null,
    val date: String,
    val time: String,
    val tirages: List<String>,
    val lines: List<String>,
    @SerializedName("total_mise") val totalMise: Double,
    val isOffline: Boolean = false,
    @SerializedName("ticket_footer_text") val ticketFooterText: String = "La fiche est payable une seule fois au porteur. Le montant gagné devra être réclamé avant 90 jours",
    @SerializedName("mariage_gratuit_actif") val mariageGratuitActif: Boolean = false,
    @SerializedName("mariage_gratuit_montant") val mariageGratuitMontant: String = "0",
    @SerializedName("qr_code_url") val qrCodeUrl: String = ""
)

// ═══════════════════════════════════════════════════════════════════════════
// HISTORIQUE & RESULTATS
// ═══════════════════════════════════════════════════════════════════════════

data class HistoriqueResponse(
    val success: Boolean,
    val tickets: List<TicketInfo>?,
    val error: String?
)

data class ResultatsResponse(
    val success: Boolean,
    val resultats: List<ResultatTirage>?,
    val error: String?
)

data class ResultatTirage(
    val id: Int,
    @SerializedName("tirage_id") val tirageId: Int,
    @SerializedName("tirage_nom") val tirageNom: String,
    @SerializedName("tirage_type") val tirageType: String,
    val date: String,
    @SerializedName("heure_tirage") val heureTirage: String,
    // Les 3 lots de base
    val lot1: String,
    val lot2: String,
    val lot3: String,
    // Loto3
    val loto3: String,
    // Loto4 (3 options)
    @SerializedName("loto4_opt1") val loto4Opt1: String,
    @SerializedName("loto4_opt2") val loto4Opt2: String,
    @SerializedName("loto4_opt3") val loto4Opt3: String,
    // Loto5 (3 options)
    @SerializedName("loto5_opt1") val loto5Opt1: String,
    @SerializedName("loto5_opt2") val loto5Opt2: String,
    @SerializedName("loto5_opt3") val loto5Opt3: String
)

// ═══════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════

data class DashboardResponse(
    val success: Boolean,
    val agent: AgentDashboardInfo?,
    val today: TodayStatsInfo?,
    val period: PeriodStatsInfo?,
    val global: GlobalStatsInfo?,
    val error: String?
)

data class AgentDashboardInfo(
    val nom: String,
    val zone: String,
    @SerializedName("commission_pct") val commissionPct: Double
)

data class TodayStatsInfo(
    val tickets: Int,
    val mises: Double,
    @SerializedName("gains_du") val gainsDu: Double,
    @SerializedName("gains_paye") val gainsPaye: Double,
    @SerializedName("gain_agent") val gainAgent: Double,
    val commission: Double
)

data class PeriodStatsInfo(
    val days: Int,
    @SerializedName("start_date") val startDate: String,
    val tickets: Int,
    val mises: Double,
    @SerializedName("gains_du") val gainsDu: Double,
    @SerializedName("gains_paye") val gainsPaye: Double,
    @SerializedName("gain_agent") val gainAgent: Double,
    val commission: Double
)

data class GlobalStatsInfo(
    val mises: Double,
    @SerializedName("gains_du") val gainsDu: Double,
    @SerializedName("gains_paye") val gainsPaye: Double,
    @SerializedName("gains_totaux") val gainsTotaux: Double,
    @SerializedName("solde_caisse") val soldeCaisse: Double = 0.0,
    @SerializedName("commission_balance") val commissionBalance: Double,
    @SerializedName("commission_earned") val commissionEarned: Double,
    @SerializedName("commission_withdrawn") val commissionWithdrawn: Double
)

data class WithdrawCommissionResponse(
    val success: Boolean,
    @SerializedName("amount_withdrawn") val amountWithdrawn: Double?,
    @SerializedName("new_balance") val newBalance: Double?,
    @SerializedName("entry_id") val entryId: String?,
    val error: String?
)

data class CommissionHistoryResponse(
    val success: Boolean,
    @SerializedName("period_days") val periodDays: Int?,
    @SerializedName("start_date") val startDate: String?,
    val entries: List<CommissionEntry>?,
    val totals: CommissionTotals?,
    val error: String?
)

data class CommissionEntry(
    val id: String,
    val type: String,
    @SerializedName("type_display") val typeDisplay: String,
    val amount: Double,
    val description: String,
    val date: String
)

data class CommissionTotals(
    val earned: Double,
    val withdrawn: Double,
    val net: Double
)

// ═══════════════════════════════════════════════════════════════════════════
// TICKET LIST (Gestion Tickets)
// ═══════════════════════════════════════════════════════════════════════════

data class TicketListResponse(
    val success: Boolean,
    val tickets: List<TicketListItem>?,
    val total: Int?,
    val limit: Int?,
    val offset: Int?,
    val error: String?
)

data class TicketListItem(
    val id: String,
    val numero: String,
    @SerializedName("group_id") val groupId: String? = null,
    @SerializedName("tirage_id") val tirageId: Int?,
    @SerializedName("tirage_nom") val tirageNom: String,
    @SerializedName("tirage_open") val tirageOpen: Boolean,
    val status: String,  // pending, won, lost, paid, cancelled
    @SerializedName("num_bets") val numBets: Int,
    @SerializedName("total_mise") val totalMise: Double,
    @SerializedName("total_gain_du") val totalGainDu: Double,
    @SerializedName("total_gain_paye") val totalGainPaye: Double,
    @SerializedName("is_winner") val isWinner: Boolean,
    @SerializedName("is_paid") val isPaid: Boolean,
    @SerializedName("can_pay") val canPay: Boolean,
    @SerializedName("can_void") val canVoid: Boolean,
    @SerializedName("can_reprint") val canReprint: Boolean,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("age_minutes") val ageMinutes: Double
) {
    fun getStatusDisplay(): String = when (status) {
        "pending" -> "En cours"
        "won" -> "Gagné"
        "lost" -> "Perdu"
        "paid" -> "Déjà payé"
        "cancelled" -> "Annulé"
        else -> status
    }
    
    fun getStatusColor(): Long = when (status) {
        "pending" -> 0xFFFFA500  // Orange
        "won" -> 0xFF10B981      // Green
        "lost" -> 0xFFEF4444     // Red
        "paid" -> 0xFF3B82F6     // Blue
        "cancelled" -> 0xFF6B7280 // Gray
        else -> 0xFF6B7280
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// TICKET SEARCH / PAY / VOID
// ═══════════════════════════════════════════════════════════════════════════

data class TicketSearchResponse(
    val success: Boolean,
    val tickets: List<TicketSearchResult>?,
    val error: String?
)

data class TicketGroupResponse(
    val success: Boolean,
    @SerializedName("group_id") val groupId: String?,
    val tickets: List<TicketGroupItem>?,
    val total: Int?,
    val error: String?
)

data class TicketGroupItem(
    val id: String,
    val numero: String,
    @SerializedName("tirage_id") val tirageId: Int?,
    @SerializedName("tirage_nom") val tirageNom: String,
    val status: String,
    @SerializedName("total_mise") val totalMise: Double,
    @SerializedName("total_gain_du") val totalGainDu: Double,
    @SerializedName("total_gain_paye") val totalGainPaye: Double,
    @SerializedName("is_winner") val isWinner: Boolean,
    @SerializedName("is_paid") val isPaid: Boolean,
    @SerializedName("can_pay") val canPay: Boolean,
    @SerializedName("can_void") val canVoid: Boolean,
    @SerializedName("created_at") val createdAt: String,
    val lines: List<TicketLineDetail>?
) {
    fun getStatusDisplay(): String = when (status) {
        "pending" -> "En cours"
        "won" -> "Gagné"
        "lost" -> "Perdu"
        "paid" -> "Déjà payé"
        "cancelled" -> "Annulé"
        else -> status
    }
    
    fun getStatusColor(): Long = when (status) {
        "pending" -> 0xFFFFA500
        "won" -> 0xFF10B981
        "lost" -> 0xFFEF4444
        "paid" -> 0xFF3B82F6
        "cancelled" -> 0xFF6B7280
        else -> 0xFF6B7280
    }
}

data class TicketSearchResult(
    val id: String,
    @SerializedName("ticket_no") val ticketNo: String,
    @SerializedName("tirage_nom") val tirageNom: String,
    @SerializedName("tirage_id") val tirageId: Int,
    @SerializedName("total_mise") val totalMise: Double,
    @SerializedName("total_gain_du") val totalGainDu: Double,
    @SerializedName("is_winner") val isWinner: Boolean,
    @SerializedName("is_paid") val isPaid: Boolean,
    val statut: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("can_void") val canVoid: Boolean,
    @SerializedName("void_deadline") val voidDeadline: String?,
    val lines: List<TicketLineDetail>?
)

data class TicketLineDetail(
    val jeu: String,
    val valeur: String,
    val mise: Double,
    @SerializedName("gain_du") val gainDu: Double,
    @SerializedName("is_winner") val isWinner: Boolean,
    @SerializedName("win_context") val winContext: String?
)

data class TicketPayResponse(
    val success: Boolean,
    val message: String?,
    @SerializedName("amount_paid") val amountPaid: Double?,
    val error: String?
)

data class TicketVoidResponse(
    val success: Boolean,
    val message: String?,
    val error: String?
)

// ═══════════════════════════════════════════════════════════════════════════
// TICKET BLUEPRINT (Refaire fiche)
// ═══════════════════════════════════════════════════════════════════════════

data class TicketBlueprintResponse(
    val success: Boolean,
    @SerializedName("ticket_id") val ticketId: String?,
    @SerializedName("tirage_id") val tirageId: Int?,
    @SerializedName("tirage_nom") val tirageNom: String?,
    @SerializedName("session_key") val sessionKey: String?,
    val lines: List<BlueprintLine>?,
    @SerializedName("total_mise") val totalMise: Double?,
    val error: String?
)

data class BlueprintLine(
    val jeu: String,
    val valeur: String,
    val mise: Double,
    val option: Int? = null
)

// ═══════════════════════════════════════════════════════════════════════════
// HEARTBEAT
// ═══════════════════════════════════════════════════════════════════════════

data class HeartbeatRequest(
    val latitude: Double? = null,
    val longitude: Double? = null
)

data class HeartbeatResponse(
    val success: Boolean = true,
    val status: String?,
    val timestamp: String?
)

// ═══════════════════════════════════════════════════════════════════════════
// HEALTH CHECK (no auth required)
// ═══════════════════════════════════════════════════════════════════════════

data class HealthResponse(
    val status: String,
    @SerializedName("server_time") val serverTime: String?,
    val version: String?
)

// ═══════════════════════════════════════════════════════════════════════════
// DEVICE REGISTRATION & CONFIG (Phase I-A)
// ═══════════════════════════════════════════════════════════════════════════

data class DeviceRegisterRequest(
    @SerializedName("device_name") val deviceName: String = ""
)

data class DeviceRegisterResponse(
    val success: Boolean = false,
    val error: String? = null,
    @SerializedName("device_id") val deviceId: String?,
    @SerializedName("device_secret") val deviceSecret: String?,
    @SerializedName("device_name") val deviceName: String?
)

data class AgentConfigResponse(
    val success: Boolean = false,
    val error: String? = null,
    @SerializedName("allow_offline_print") val allowOfflinePrint: Boolean = false,
    @SerializedName("server_time") val serverTime: String?,
    val version: String?,
    val borlette: BorletteInfo? = null
)

// ═══════════════════════════════════════════════════════════════════════════
// WEBSOCKET
// ═══════════════════════════════════════════════════════════════════════════

data class WebSocketMessage(
    val type: String,
    val data: Map<String, Any>? = null
)
