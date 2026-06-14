package com.gaboom.agent.ui.screens.vente

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.TicketCreateRequest
import com.gaboom.agent.data.model.TicketLine
import com.gaboom.agent.data.model.TicketLineWithOptions
import com.gaboom.agent.data.model.Tirage
import com.gaboom.agent.data.model.MultiTicketCreateRequest
import com.gaboom.agent.data.model.MultiTicketEntry
import com.gaboom.agent.data.model.MultiTicketCreateResponse
import com.gaboom.agent.data.model.PrintData
import com.gaboom.agent.data.config.AgentConfigDataStore
import com.gaboom.agent.data.repository.AuthRepository
import com.gaboom.agent.data.local.PendingTicketDao
import com.gaboom.agent.data.local.PendingTicketEntity
import com.gaboom.agent.data.local.SyncStatus
import com.gaboom.agent.data.network.NetworkMonitor
import com.gaboom.agent.data.model.*
import com.gaboom.agent.print.BluetoothPrinter
import com.gaboom.agent.util.GameGenerators
import com.gaboom.agent.util.HmacUtil
import com.gaboom.agent.util.LotoOptionsHelper
import com.google.gson.Gson
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

data class TicketShareInfo(
    val ticketNo: String,
    val tirageNom: String,
    val date: String,
    val time: String,
    val lines: List<Pair<String, Double>>, // jeu:valeur -> mise
    val totalMise: Double,
    val groupId: String?,
    val ticketId: String = "",
    val borletteName: String = "",
    val borletteSlogan: String = "",
    val borletteTel: String = "",
    val borletteAdresse: String = "",
    val borletteLogoUrl: String = "",
    val agentName: String = "",
    val ticketFooterText: String = "",
    val mariageGratuitActif: Boolean = false,
    val mariageGratuitMontant: String = "0"
)

data class VenteUiState(
    val isLoading: Boolean = false,
    val lines: List<TicketLineWithOptions> = emptyList(),
    val ticketCreated: Boolean = false,
    val error: String? = null,
    val autoMariageEnabled: Boolean = false,
    val autoLoto4Enabled: Boolean = false,
    val autoLoto5Enabled: Boolean = false,
    // Global options - apply to all new Loto4/Loto5 lines
    val globalLoto4Options: Set<Int> = setOf(1),  // Default: Option 1 checked
    val globalLoto5Options: Set<Int> = setOf(1),  // Default: Option 1 checked
    val useGlobalOptions: Boolean = true,  // Whether to apply global options to new lines
    val applyGlobalToAllLoto4: Boolean = true,  // Apply global options to all Loto4
    val applyGlobalToAllLoto5: Boolean = true,  // Apply global options to all Loto5
    // Multi-tirage mode - ENABLED BY DEFAULT
    val multiTirageMode: Boolean = true,
    val availableTirages: List<Tirage> = emptyList(),
    val selectedTirageIds: Set<Int> = emptySet(),
    val isLoadingTirages: Boolean = false,
    // Multi-tirage creation results
    val createdTickets: List<CreatedTicketInfo> = emptyList(),
    val currentPrintIndex: Int = 0,
    val printError: String? = null,
    val creationProgress: String? = null,
    // Free marriage option (from admin settings)
    val freeMariageEnabled: Boolean = false,
    val freeMariageChecked: Boolean = false,
    // Ticket data for sharing after creation
    val ticketToShare: TicketShareInfo? = null,
    // Borlette info for print preview
    val borletteName: String = "",
    val borletteSlogan: String = "",
    val borletteTel: String = "",
    val borletteAdresse: String = "",
    val borletteLogoUrl: String = "",
    val agentName: String = "",
    val ticketFooterText: String = "",
    val mariageGratuitActif: Boolean = false,
    val mariageGratuitMontant: String = "0"
)

@HiltViewModel
class VenteViewModel @Inject constructor(
    private val apiService: AgentApiService,
    private val printer: BluetoothPrinter,
    private val agentConfigDataStore: AgentConfigDataStore,
    private val authRepository: AuthRepository,
    private val pendingTicketDao: PendingTicketDao,
    private val networkMonitor: NetworkMonitor,
    private val gson: Gson
) : ViewModel() {

    private val _uiState = MutableStateFlow(VenteUiState())
    val uiState: StateFlow<VenteUiState> = _uiState.asStateFlow()

    init {
        // Load free marriage setting from config and load tirages automatically
        viewModelScope.launch {
            val enabled = agentConfigDataStore.getFreeMariageEnabled()
            // Load borlette and agent info for print preview
            val borletteName = authRepository.getBorletteNom() ?: "GABOOM BORLETTE"
            val borletteSlogan = authRepository.getBorletteSlogan() ?: ""
            val borletteTel = authRepository.getBorletteTel() ?: ""
            val borletteAdresse = authRepository.getBorletteAdresse() ?: ""
            val borletteLogoUrl = authRepository.getBorletteLogoUrl() ?: ""
            val agentName = authRepository.getAgentNom() ?: ""
            val ticketFooterText = authRepository.getTicketFooterText() ?: ""
            val mariageGratuitActif = authRepository.getMariageGratuitActif()
            val mariageGratuitMontant = authRepository.getMariageGratuitMontant()
            _uiState.value = _uiState.value.copy(
                freeMariageEnabled = enabled,
                borletteName = borletteName,
                borletteSlogan = borletteSlogan,
                borletteTel = borletteTel,
                borletteAdresse = borletteAdresse,
                borletteLogoUrl = borletteLogoUrl,
                agentName = agentName,
                ticketFooterText = ticketFooterText,
                mariageGratuitActif = mariageGratuitActif,
                mariageGratuitMontant = mariageGratuitMontant
            )
            // Auto-load tirages since multi-tirage is default
            loadAvailableTiragesOnInit()
        }
    }
    
    private suspend fun loadAvailableTiragesOnInit() {
        _uiState.value = _uiState.value.copy(isLoadingTirages = true)
        try {
            val response = apiService.getTiragesActifs()
            if (response.isSuccessful) {
                val allTirages = response.body()?.tirages ?: emptyList()
                // Separate open and closed tirages
                val openTirages = allTirages.filter { it.etat == "OUVERT" }
                _uiState.value = _uiState.value.copy(
                    availableTirages = allTirages,  // Include all for display (closed ones grayed out)
                    isLoadingTirages = false
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isLoadingTirages = false,
                    error = "Erreur chargement tirages"
                )
            }
        } catch (e: Exception) {
            _uiState.value = _uiState.value.copy(
                isLoadingTirages = false,
                error = "Erreur: ${e.message}"
            )
        }
    }

    /**
     * Add a new line with proper options handling.
     * For Loto4/Loto5: creates a SEPARATE LINE for each option so user can edit each price individually.
     * 
     * @return Error message if validation fails, null if success
     */
    fun addLine(jeu: String, valeur: String, mise: Double): String? {
        if (valeur.isBlank()) return "Numéro requis"
        if (mise <= 0) return "Mise invalide"

        val isLoto = jeu.lowercase() in listOf("loto4", "loto5")
        
        if (isLoto) {
            // Get selected options
            val options = when (jeu.lowercase()) {
                "loto4" -> _uiState.value.globalLoto4Options.ifEmpty { setOf(1) }
                "loto5" -> _uiState.value.globalLoto5Options.ifEmpty { setOf(1) }
                else -> emptySet()
            }
            
            // Validate options
            val (isValid, errorMsg) = LotoOptionsHelper.validateLotoOptions(jeu, options)
            if (!isValid) {
                return errorMsg
            }
            
            // Create a SEPARATE LINE for each option
            val newLines = options.sorted().map { opt ->
                TicketLineWithOptions(
                    jeu = jeu,
                    valeur = valeur,
                    miseBase = mise,
                    options = setOf(opt),  // Single option per line
                    useGlobalOptions = false
                )
            }
            
            _uiState.value = _uiState.value.copy(
                lines = _uiState.value.lines + newLines,
                error = null
            )
        } else {
            // Non-Loto: single line as before
            val newLine = TicketLineWithOptions(
                jeu = jeu,
                valeur = valeur,
                miseBase = mise,
                options = emptySet(),
                useGlobalOptions = false
            )
            _uiState.value = _uiState.value.copy(
                lines = _uiState.value.lines + newLine,
                error = null
            )
        }
        return null  // Success
    }

    fun removeLine(index: Int) {
        val newLines = _uiState.value.lines.toMutableList()
        if (index in newLines.indices) {
            newLines.removeAt(index)
            _uiState.value = _uiState.value.copy(lines = newLines)
        }
    }

    /**
     * Update base mise for a line.
     * Total effective mise will be recalculated (miseBase * options.size)
     */
    fun updateLineMise(index: Int, newMise: Double) {
        val newLines = _uiState.value.lines.toMutableList()
        if (index in newLines.indices) {
            newLines[index] = newLines[index].copy(miseBase = newMise)
            _uiState.value = _uiState.value.copy(lines = newLines)
        }
    }

    /**
     * Add a new line with a specific option for the same Loto number.
     * Used to add additional options to an existing number.
     */
    fun addOptionLine(jeu: String, valeur: String, mise: Double, option: Int) {
        val newLine = TicketLineWithOptions(
            jeu = jeu,
            valeur = valeur,
            miseBase = mise,
            options = setOf(option),
            useGlobalOptions = false
        )
        _uiState.value = _uiState.value.copy(
            lines = _uiState.value.lines + newLine,
            error = null
        )
    }

    /**
     * Update options for a specific line (override global options)
     */
    fun updateLineOptions(index: Int, options: Set<Int>) {
        val newLines = _uiState.value.lines.toMutableList()
        if (index in newLines.indices) {
            newLines[index] = newLines[index].copy(
                options = options,
                useGlobalOptions = false
            )
            _uiState.value = _uiState.value.copy(lines = newLines)
        }
    }

    /**
     * Toggle a line to use/not use global options
     */
    fun toggleLineUseGlobalOptions(index: Int) {
        val newLines = _uiState.value.lines.toMutableList()
        if (index in newLines.indices) {
            val line = newLines[index]
            val newUseGlobal = !line.useGlobalOptions
            val newOptions = if (newUseGlobal) {
                // Apply current global options (use exact set, don't force opt1)
                when (line.jeu.lowercase()) {
                    "loto4" -> _uiState.value.globalLoto4Options
                    "loto5" -> _uiState.value.globalLoto5Options
                    else -> emptySet()
                }
            } else {
                line.options  // Keep current options when switching to custom
            }
            newLines[index] = line.copy(
                useGlobalOptions = newUseGlobal,
                options = newOptions
            )
            _uiState.value = _uiState.value.copy(lines = newLines)
        }
    }

    // ─── Global Options Management ───────────────────────────────────────────

    fun toggleGlobalLoto4Option(option: Int) {
        val current = _uiState.value.globalLoto4Options.toMutableSet()
        if (current.contains(option)) {
            current.remove(option)
        } else {
            current.add(option)
        }
        _uiState.value = _uiState.value.copy(globalLoto4Options = current)
        // Propager aux lignes existantes si "Appliquer à tous" est coché
        if (_uiState.value.applyGlobalToAllLoto4) {
            applyGlobalOptionsToAllLoto4()
        }
    }

    fun toggleGlobalLoto5Option(option: Int) {
        val current = _uiState.value.globalLoto5Options.toMutableSet()
        if (current.contains(option)) {
            current.remove(option)
        } else {
            current.add(option)
        }
        _uiState.value = _uiState.value.copy(globalLoto5Options = current)
        // Propager aux lignes existantes si "Appliquer à tous" est coché
        if (_uiState.value.applyGlobalToAllLoto5) {
            applyGlobalOptionsToAllLoto5()
        }
    }

    fun setUseGlobalOptions(useGlobal: Boolean) {
        _uiState.value = _uiState.value.copy(useGlobalOptions = useGlobal)
    }

    /**
     * Set FULL option (1+2+3) for Loto4
     * When enabling FULL: set {1,2,3} and auto-apply to existing lines
     * When disabling FULL: keep current selection (don't reset to {1})
     */
    fun setLoto4Full(isFull: Boolean) {
        if (isFull) {
            _uiState.value = _uiState.value.copy(
                globalLoto4Options = setOf(1, 2, 3),
                applyGlobalToAllLoto4 = true  // Auto-enable apply to all
            )
            applyGlobalOptionsToAllLoto4()
        }
    }

    /**
     * Set FULL option (1+2+3) for Loto5
     * When enabling FULL: set {1,2,3} and auto-apply to existing lines
     * When disabling FULL: keep current selection (don't reset to {1})
     */
    fun setLoto5Full(isFull: Boolean) {
        if (isFull) {
            _uiState.value = _uiState.value.copy(
                globalLoto5Options = setOf(1, 2, 3),
                applyGlobalToAllLoto5 = true  // Auto-enable apply to all
            )
            applyGlobalOptionsToAllLoto5()
        }
    }

    /**
     * Toggle "Apply to all" for Loto4
     */
    fun toggleApplyGlobalToAllLoto4(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(applyGlobalToAllLoto4 = enabled)
        if (enabled) {
            applyGlobalOptionsToAllLoto4()
        }
    }

    /**
     * Toggle "Apply to all" for Loto5
     */
    fun toggleApplyGlobalToAllLoto5(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(applyGlobalToAllLoto5 = enabled)
        if (enabled) {
            applyGlobalOptionsToAllLoto5()
        }
    }

    /**
     * Apply global Loto4 options to all existing Loto4 lines.
     * FULL option: Expande chaque ligne en plusieurs lignes séparées (une par option).
     * Ex: loto4 = 1234 avec FULL → 3 lignes: opt1, opt2, opt3
     */
    private fun applyGlobalOptionsToAllLoto4() {
        val globalOpts = _uiState.value.globalLoto4Options
        if (globalOpts.isEmpty()) return
        
        val newLines = mutableListOf<TicketLineWithOptions>()
        val processedNumbers = mutableSetOf<String>()  // Track processed loto4 numbers
        
        for (line in _uiState.value.lines) {
            if (line.jeu.lowercase() == "loto4") {
                // Skip if we already processed this number (avoid duplicates)
                if (line.valeur in processedNumbers) continue
                processedNumbers.add(line.valeur)
                
                // Create separate line for each global option
                globalOpts.sorted().forEach { opt ->
                    newLines.add(
                        TicketLineWithOptions(
                            jeu = line.jeu,
                            valeur = line.valeur,
                            miseBase = line.miseBase,
                            options = setOf(opt),
                            useGlobalOptions = true
                        )
                    )
                }
            } else {
                newLines.add(line)
            }
        }
        _uiState.value = _uiState.value.copy(lines = newLines)
    }

    /**
     * Apply global Loto5 options to all existing Loto5 lines.
     * FULL option: Expande chaque ligne en plusieurs lignes séparées (une par option).
     */
    private fun applyGlobalOptionsToAllLoto5() {
        val globalOpts = _uiState.value.globalLoto5Options
        if (globalOpts.isEmpty()) return
        
        val newLines = mutableListOf<TicketLineWithOptions>()
        val processedNumbers = mutableSetOf<String>()  // Track processed loto5 numbers
        
        for (line in _uiState.value.lines) {
            if (line.jeu.lowercase() == "loto5") {
                // Skip if we already processed this number (avoid duplicates)
                if (line.valeur in processedNumbers) continue
                processedNumbers.add(line.valeur)
                
                // Create separate line for each global option
                globalOpts.sorted().forEach { opt ->
                    newLines.add(
                        TicketLineWithOptions(
                            jeu = line.jeu,
                            valeur = line.valeur,
                            miseBase = line.miseBase,
                            options = setOf(opt),
                            useGlobalOptions = true
                        )
                    )
                }
            } else {
                newLines.add(line)
            }
        }
        _uiState.value = _uiState.value.copy(lines = newLines)
    }

    // ─── Automations ─────────────────────────────────────────────────────────

    fun toggleAutoMariage(enabled: Boolean, defaultMise: Double) {
        _uiState.value = _uiState.value.copy(autoMariageEnabled = enabled)
        if (enabled) {
            generateAutoMariages(defaultMise)
        }
    }

    fun toggleAutoLoto4(enabled: Boolean, defaultMise: Double) {
        _uiState.value = _uiState.value.copy(autoLoto4Enabled = enabled)
        if (enabled) {
            generateAutoLoto4(defaultMise)
        }
    }

    fun toggleLoto4Option(option: Int) {
        toggleGlobalLoto4Option(option)
    }

    fun toggleLoto5Option(option: Int) {
        toggleGlobalLoto5Option(option)
    }

    private fun generateAutoMariages(defaultMise: Double) {
        val existingLines = _uiState.value.lines.map { Pair(it.jeu, it.valeur) }
        val autoMariages = GameGenerators.generateAutoMariages(existingLines, defaultMise)
        
        val newLines = autoMariages.map { (jeu, valeur, mise) ->
            TicketLineWithOptions(jeu = jeu, valeur = valeur, miseBase = mise, options = emptySet())
        }
        
        if (newLines.isNotEmpty()) {
            _uiState.value = _uiState.value.copy(
                lines = _uiState.value.lines + newLines
            )
        }
    }

    private fun generateAutoLoto4(defaultMise: Double) {
        val existingLines = _uiState.value.lines.map { Pair(it.jeu, it.valeur) }
        val autoLoto4 = GameGenerators.generateAutoLoto4(existingLines, defaultMise)
        
        val globalOpts = _uiState.value.globalLoto4Options.ifEmpty { setOf(1) }
        val newLines = autoLoto4.map { (jeu, valeur, mise) ->
            TicketLineWithOptions(
                jeu = jeu, 
                valeur = valeur, 
                miseBase = mise, 
                options = globalOpts,
                useGlobalOptions = true
            )
        }
        
        if (newLines.isNotEmpty()) {
            _uiState.value = _uiState.value.copy(
                lines = _uiState.value.lines + newLines
            )
        }
    }

    private fun generateAutoLoto5(defaultMise: Double) {
        val boules = _uiState.value.lines
            .filter { it.jeu.lowercase() == "boule" }
            .map { it.valeur }
            .distinct()
        
        if (boules.isEmpty()) return
        
        val existingLoto5 = _uiState.value.lines
            .filter { it.jeu.lowercase() == "loto5" }
            .map { it.valeur }
            .toSet()
        
        val globalOpts = _uiState.value.globalLoto5Options.ifEmpty { setOf(1) }
        val newLines = mutableListOf<TicketLineWithOptions>()
        
        boules.forEach { boule ->
            (1..9).forEach { digit ->
                val loto5Value = "$digit$boule$boule"
                if (loto5Value !in existingLoto5) {
                    newLines.add(TicketLineWithOptions(
                        jeu = "loto5",
                        valeur = loto5Value,
                        miseBase = defaultMise,
                        options = globalOpts,
                        useGlobalOptions = true
                    ))
                }
            }
        }
        
        if (newLines.isNotEmpty()) {
            _uiState.value = _uiState.value.copy(
                lines = _uiState.value.lines + newLines
            )
        }
    }

    fun toggleAutoLoto5(enabled: Boolean, defaultMise: Double) {
        _uiState.value = _uiState.value.copy(autoLoto5Enabled = enabled)
        if (enabled) {
            generateAutoLoto5(defaultMise)
        }
    }

    fun regenerateAutomations(defaultMise: Double) {
        if (_uiState.value.autoMariageEnabled) {
            generateAutoMariages(defaultMise)
        }
        if (_uiState.value.autoLoto4Enabled) {
            generateAutoLoto4(defaultMise)
        }
    }

    fun createTicket(tirageId: Int) {
        if (_uiState.value.lines.isEmpty()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val apiLines = _uiState.value.lines.flatMap { it.toApiLines() }
            if (apiLines.isEmpty()) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Aucune ligne valide"
                )
                return@launch
            }

            if (!networkMonitor.isCurrentlyOnline()) {
                // Offline mode
                try {
                    val tirage = _uiState.value.availableTirages.find { it.id == tirageId }
                    if (tirage == null) {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = "Tirage non trouvé pour mode hors-ligne")
                        return@launch
                    }
                    
                    val dummyTicketInfo = saveTicketOffline(tirage, apiLines)
                    
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        ticketCreated = true,
                        error = "Ticket créé hors ligne (HL)"
                    )
                    
                    // Offline printing support
                    val allowOfflinePrint = agentConfigDataStore.getAllowOfflinePrint()
                    if (allowOfflinePrint && printer.isConnected()) {
                        val printData = buildOfflinePrintData(dummyTicketInfo, apiLines)
                        printer.printTicket(printData)
                    }
                } catch (e: Exception) {
                    _uiState.value = _uiState.value.copy(isLoading = false, error = "Erreur hors-ligne: ${e.message}")
                }
                return@launch
            }

            try {
                val request = TicketCreateRequest(
                    drawIds = listOf(tirageId),
                    lines = apiLines
                )

                val response = apiService.createTicket(request)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true && body.ticket != null) {
                        printTicket(body.ticket.id)
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            ticketCreated = true
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur création ticket"
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Erreur serveur"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    fun createAndShareTicket(tirageId: Int) {
        if (_uiState.value.lines.isEmpty()) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val apiLines = _uiState.value.lines.flatMap { it.toApiLines() }
            if (apiLines.isEmpty()) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Aucune ligne valide"
                )
                return@launch
            }

            if (!networkMonitor.isCurrentlyOnline()) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Connexion requise pour enregistrer et partager"
                )
                return@launch
            }

            try {
                val request = TicketCreateRequest(
                    drawIds = listOf(tirageId),
                    lines = apiLines
                )

                val response = apiService.createTicket(request)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true && body.ticket != null) {
                        val ticket = body.ticket
                        val tirage = _uiState.value.availableTirages.find { it.id == tirageId }
                        val now = java.time.LocalDateTime.now()
                        
                        val shareInfo = TicketShareInfo(
                            ticketNo = ticket.numero,
                            tirageNom = tirage?.nom ?: "Tirage",
                            date = now.toLocalDate().toString(),
                            time = now.toLocalTime().toString().take(5),
                            lines = apiLines.map { "${it.jeu}:${it.valeur}:${it.option}" to it.mise },
                            totalMise = apiLines.sumOf { it.mise }.toDouble(),
                            groupId = ticket.groupId,
                            ticketId = ticket.id.toString(),
                            borletteName = _uiState.value.borletteName,
                            borletteSlogan = _uiState.value.borletteSlogan,
                            borletteTel = _uiState.value.borletteTel,
                            borletteAdresse = _uiState.value.borletteAdresse,
                            borletteLogoUrl = _uiState.value.borletteLogoUrl,
                            agentName = _uiState.value.agentName,
                            ticketFooterText = _uiState.value.ticketFooterText,
                            mariageGratuitActif = _uiState.value.mariageGratuitActif,
                            mariageGratuitMontant = _uiState.value.mariageGratuitMontant
                        )
                        
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            ticketCreated = true,
                            ticketToShare = shareInfo
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur création ticket"
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Erreur serveur"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    fun clearTicketToShare() {
        _uiState.value = _uiState.value.copy(ticketToShare = null)
    }

    fun printLastTicket() {
        viewModelScope.launch {
            val ticketId = _uiState.value.ticketToShare?.ticketId
            if (!ticketId.isNullOrBlank()) {
                printTicket(ticketId)
            }
        }
    }

    fun createAndShareMultiTickets() {
        viewModelScope.launch {
            val selectedIds = _uiState.value.selectedTirageIds.toList()
            if (selectedIds.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "Sélectionnez au moins un tirage")
                return@launch
            }

            _uiState.value = _uiState.value.copy(
                isLoading = true,
                error = null,
                creationProgress = "Création..."
            )

            if (!networkMonitor.isCurrentlyOnline()) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Connexion requise pour enregistrer et partager"
                )
                return@launch
            }

            try {
                val entries = _uiState.value.lines.flatMap { line ->
                    val expandedBets = LotoOptionsHelper.expandLineToBets(line)
                    expandedBets.map { bet ->
                        MultiTicketEntry(
                            game = bet.game,
                            number = bet.number,
                            stake = bet.mise,
                            gratuit = bet.gratuit,
                            option = if (bet.option > 0) bet.option else null
                        )
                    }
                }.toMutableList()

                if (_uiState.value.freeMariageEnabled && _uiState.value.freeMariageChecked) {
                    val linePairs = _uiState.value.lines.map { Pair(it.jeu, it.valeur) }
                    val boules = GameGenerators.extractBoulesFromLines(linePairs)
                    if (boules.size >= 2) {
                        val mariages = GameGenerators.generateMariages(boules)
                        mariages.forEach { mariage ->
                            entries.add(MultiTicketEntry(game = "mariage", number = mariage, stake = 0.0))
                        }
                    }
                }

                if (entries.isEmpty()) {
                    _uiState.value = _uiState.value.copy(isLoading = false, error = "Aucune entrée valide")
                    return@launch
                }

                val sessionKey = _uiState.value.availableTirages
                    .find { it.id == selectedIds.first() }
                    ?.sessionKey

                val request = MultiTicketCreateRequest(
                    tirageIds = selectedIds,
                    entries = entries,
                    sessionKey = sessionKey
                )

                val response = apiService.createMultiTicket(request)
                
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true && !body.tickets.isNullOrEmpty()) {
                        val tickets = body.tickets
                        val now = java.time.LocalDateTime.now()
                        
                        // Use first ticket info for sharing (group_id is shared)
                        val firstTicket = tickets.first()
                        val tirageNames = tickets.mapNotNull { t -> 
                            _uiState.value.availableTirages.find { it.id == t.tirageId }?.nom 
                        }.joinToString(", ")
                        
                        val shareInfo = TicketShareInfo(
                            ticketNo = if (tickets.size > 1) "${tickets.size} tickets" else firstTicket.ticketNo,
                            tirageNom = tirageNames,
                            date = now.toLocalDate().toString(),
                            time = now.toLocalTime().toString().take(5),
                            lines = entries.map { "${it.game}:${it.number}:${it.option ?: 1}" to it.stake },
                            totalMise = tickets.sumOf { it.totalMise },
                            groupId = firstTicket.groupId,
                            ticketId = firstTicket.ticketId.toString(),
                            borletteName = _uiState.value.borletteName,
                            borletteSlogan = _uiState.value.borletteSlogan,
                            borletteTel = _uiState.value.borletteTel,
                            borletteAdresse = _uiState.value.borletteAdresse,
                            borletteLogoUrl = _uiState.value.borletteLogoUrl,
                            agentName = _uiState.value.agentName,
                            ticketFooterText = _uiState.value.ticketFooterText,
                            mariageGratuitActif = _uiState.value.mariageGratuitActif,
                            mariageGratuitMontant = _uiState.value.mariageGratuitMontant
                        )
                        
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            ticketCreated = true,
                            ticketToShare = shareInfo,
                            creationProgress = null
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur création tickets",
                            creationProgress = null
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Erreur serveur: ${response.code()}",
                        creationProgress = null
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur: ${e.message}",
                    creationProgress = null
                )
            }
        }
    }

    private suspend fun saveTicketOffline(
        tirage: Tirage,
        apiLines: List<TicketLine>
    ): CreatedTicketInfo {
        val totalMise = apiLines.sumOf { it.mise }
        val localId = UUID.randomUUID().toString()
        val localTicketNo = "HL-${localId.take(8).uppercase()}"
        
        val request = MultiTicketCreateRequest(
            tirageIds = listOf(tirage.id),
            entries = apiLines.map { MultiTicketEntry(game = it.jeu, number = it.valeur, stake = it.mise, gratuit = it.gratuit) },
            sessionKey = tirage.sessionKey
        )
        
        val payloadJson = gson.toJson(request)
        val linesSummary = apiLines.take(5).joinToString(", ") { "${it.jeu}:${it.valeur}" } + 
                           if (apiLines.size > 5) "..." else ""
                           
        val deviceCreds = agentConfigDataStore.getDeviceCredentials()
        val hmacSignature = if (deviceCreds != null) {
            HmacUtil.signPayload(
                deviceSecret = deviceCreds.deviceSecret,
                payloadJson = payloadJson,
                sessionKey = tirage.sessionKey ?: ""
            )
        } else null
        
        val pendingTicket = PendingTicketEntity(
            id = localId,
            payloadJson = payloadJson,
            tirageIds = tirage.id.toString(),
            tirageId = tirage.id,
            sessionKey = tirage.sessionKey,
            totalMise = totalMise,
            linesSummary = linesSummary,
            syncStatus = SyncStatus.PENDING,
            hmacSignature = hmacSignature
        )
        pendingTicketDao.insert(pendingTicket)
        
        return CreatedTicketInfo(
            ticketId = localId,
            ticketNo = localTicketNo,
            tirageId = tirage.id,
            tirageNom = tirage.nom,
            totalMise = totalMise,
            isOffline = true
        )
    }

    private fun buildOfflinePrintData(ticket: CreatedTicketInfo, apiLines: List<TicketLine>): PrintData {
        val lines = apiLines.map { line ->
            String.format("%-7s %-9s %6.0f", line.jeu, line.valeur, line.mise)
        }
        val now = java.util.Date()
        val dateFormat = java.text.SimpleDateFormat("dd/MM/yyyy", java.util.Locale.getDefault())
        val timeFormat = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())

        return PrintData(
            borletteName = _uiState.value.borletteName.ifEmpty { "Gaboom" },
            borletteSlogan = _uiState.value.borletteSlogan,
            borletteTel = _uiState.value.borletteTel,
            borletteAdresse = _uiState.value.borletteAdresse,
            borletteLogoUrl = _uiState.value.borletteLogoUrl,
            agentName = _uiState.value.agentName.ifEmpty { "Agent" },
            ticketNumber = ticket.ticketNo,
            date = dateFormat.format(now),
            time = timeFormat.format(now),
            tirages = listOf(ticket.tirageNom),
            lines = lines,
            totalMise = ticket.totalMise,
            isOffline = true,
            ticketFooterText = _uiState.value.ticketFooterText,
            mariageGratuitActif = _uiState.value.mariageGratuitActif,
            mariageGratuitMontant = _uiState.value.mariageGratuitMontant
        )
    }

    private suspend fun printTicket(ticketId: String): com.gaboom.agent.data.model.PrintData? {
        return try {
            val printResponse = apiService.getTicketPrint(ticketId)
            if (printResponse.isSuccessful) {
                val printData = printResponse.body()?.printData
                if (printData != null) {
                    if (printer.isConnected()) {
                        printer.printTicket(printData)
                    }
                    printData
                } else {
                    null
                }
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MULTI-TIRAGE MODE
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * Initialize with a default tirage pre-selected.
     * Called when screen opens with a selected tirage from TirageSelectionScreen.
     */
    fun setDefaultTirage(defaultTirageId: Int, defaultTirageNom: String) {
        viewModelScope.launch {
            // Always load available tirages for potential multi-selection
            if (_uiState.value.availableTirages.isEmpty()) {
                loadAvailableTiragesForDefault(defaultTirageId)
            } else {
                // Just ensure default is selected
                val current = _uiState.value.selectedTirageIds.toMutableSet()
                current.add(defaultTirageId)
                _uiState.value = _uiState.value.copy(selectedTirageIds = current)
            }
        }
    }

    private suspend fun loadAvailableTiragesForDefault(defaultTirageId: Int) {
        _uiState.value = _uiState.value.copy(isLoadingTirages = true)
        try {
            val response = apiService.getTiragesActifs()
            if (response.isSuccessful) {
                val tirages = response.body()?.tirages?.filter { it.etat == "OUVERT" } ?: emptyList()
                // Pre-select the default tirage
                val defaultSelected = setOf(defaultTirageId)
                _uiState.value = _uiState.value.copy(
                    availableTirages = tirages,
                    selectedTirageIds = defaultSelected,
                    isLoadingTirages = false,
                    multiTirageMode = false // Start in single mode, user can enable multi
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isLoadingTirages = false,
                    error = "Erreur chargement tirages"
                )
            }
        } catch (e: Exception) {
            _uiState.value = _uiState.value.copy(
                isLoadingTirages = false,
                error = "Erreur: ${e.message}"
            )
        }
    }

    fun toggleMultiTirageMode(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(
            multiTirageMode = enabled,
            error = null
        )
        if (enabled && _uiState.value.availableTirages.isEmpty()) {
            loadAvailableTirages()
        }
    }

    private fun loadAvailableTirages() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingTirages = true)
            try {
                val response = apiService.getTiragesActifs()
                if (response.isSuccessful) {
                    val tirages = response.body()?.tirages?.filter { it.etat == "OUVERT" } ?: emptyList()
                    _uiState.value = _uiState.value.copy(
                        availableTirages = tirages,
                        isLoadingTirages = false
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoadingTirages = false,
                        error = "Erreur chargement tirages"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoadingTirages = false,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    fun toggleTirageSelection(tirageId: Int) {
        val current = _uiState.value.selectedTirageIds.toMutableSet()
        if (current.contains(tirageId)) {
            current.remove(tirageId)
        } else {
            current.add(tirageId)
        }
        _uiState.value = _uiState.value.copy(selectedTirageIds = current)
    }

    fun selectAllTirages() {
        val allIds = _uiState.value.availableTirages.map { it.id }.toSet()
        _uiState.value = _uiState.value.copy(selectedTirageIds = allIds)
    }

    fun clearAllTirages() {
        _uiState.value = _uiState.value.copy(selectedTirageIds = emptySet())
    }

    /**
     * Create multi-tirage tickets using create-multi endpoint.
     * Returns N tickets for N selected tirages.
     */
    fun createMultiTickets() {
        viewModelScope.launch {
            val selectedIds = _uiState.value.selectedTirageIds.toList()
            if (selectedIds.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "Sélectionnez au moins un tirage")
                return@launch
            }

            _uiState.value = _uiState.value.copy(
                isLoading = true,
                error = null,
                creationProgress = "Création 0/${selectedIds.size}..."
            )

            try {
                // Convert lines to MultiTicketEntry format using LotoOptionsHelper
                // Each option for Loto4/Loto5 becomes a separate entry (separate bet)
                // CRITICAL: Include the specific option number for Loto4/Loto5 bets
                val entries = _uiState.value.lines.flatMap { line ->
                    val expandedBets = LotoOptionsHelper.expandLineToBets(line)
                    expandedBets.map { bet ->
                        MultiTicketEntry(
                            game = bet.game,
                            number = bet.number,
                            stake = bet.mise,
                            gratuit = bet.gratuit,
                            option = if (bet.option > 0) bet.option else null  // Send option for Loto4/Loto5
                        )
                    }
                }.toMutableList()

                // Add free marriage line if enabled and checked
                if (_uiState.value.freeMariageEnabled && _uiState.value.freeMariageChecked) {
                    // Convert lines to Pair<String, String> for GameGenerators
                    val linePairs = _uiState.value.lines.map { Pair(it.jeu, it.valeur) }
                    val boules = GameGenerators.extractBoulesFromLines(linePairs)
                    if (boules.size >= 2) {
                        val mariages = GameGenerators.generateMariages(boules)
                        mariages.forEach { mariage ->
                            entries.add(MultiTicketEntry(
                                game = "mariage",
                                number = mariage,
                                stake = 0.0  // FREE marriage
                            ))
                        }
                    }
                }

                if (entries.isEmpty()) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Aucune entrée valide"
                    )
                    return@launch
                }

                if (!networkMonitor.isCurrentlyOnline()) {
                    // Offline Multi-Tirage: Save each one as HL
                    try {
                        val batchId = UUID.randomUUID().toString()
                        val selectedTirages = _uiState.value.availableTirages.filter { it.id in selectedIds }
                        val createdOffline = mutableListOf<CreatedTicketInfo>()
                        
                        selectedTirages.forEach { tirage ->
                            val offlineInfo = saveTicketOffline(
                                tirage = tirage,
                                apiLines = entries.map { TicketLine(jeu = it.game, valeur = it.number, mise = it.stake, gratuit = it.gratuit) }
                            )
                            createdOffline.add(offlineInfo)
                        }
                        
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            createdTickets = createdOffline,
                            currentPrintIndex = 0,
                            ticketCreated = true,
                            error = "Tickets créés hors ligne (${createdOffline.size})"
                        )
                        
                        // Start printing if allowed
                        val allowOfflinePrint = agentConfigDataStore.getAllowOfflinePrint()
                        if (allowOfflinePrint) {
                            printCurrentTicketMulti()
                        }
                    } catch (e: Exception) {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = "Erreur hors-ligne multiple: ${e.message}")
                    }
                    return@launch
                }

                // Get session key from first selected tirage
                val sessionKey = _uiState.value.availableTirages
                    .find { it.id == selectedIds.first() }
                    ?.sessionKey

                val request = MultiTicketCreateRequest(
                    tirageIds = selectedIds,
                    entries = entries,
                    sessionKey = sessionKey
                )

                val response = apiService.createMultiTicket(request)
                
                if (response.isSuccessful) {
                    val body = response.body()
                    handleMultiTicketResponse(body, selectedIds)
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Erreur serveur: ${response.code()}"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    private fun handleMultiTicketResponse(
        body: MultiTicketCreateResponse?, 
        requestedIds: List<Int>
    ) {
        if (body?.success != true) {
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                error = body?.error ?: "Erreur création tickets"
            )
            return
        }

        val tickets = body.tickets ?: emptyList()
        val failed = body.failed ?: emptyList()

        if (tickets.isEmpty()) {
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                error = "Aucun ticket créé"
            )
            return
        }

        // Convert to CreatedTicketInfo for printing
        val createdTickets = tickets.map { t ->
            CreatedTicketInfo(
                ticketId = t.ticketId,
                ticketNo = t.ticketNo,
                tirageId = t.tirageId,
                tirageNom = t.tirageNom,
                totalMise = t.totalMise,
                printed = false,
                isOffline = false
            )
        }

        val failedCount = failed.size
        val errorMsg = if (failedCount > 0) {
            "⚠️ $failedCount/${requestedIds.size} échecs - ${failed.firstOrNull()?.error ?: ""}"
        } else null

        _uiState.value = _uiState.value.copy(
            isLoading = false,
            createdTickets = createdTickets,
            currentPrintIndex = 0,
            ticketCreated = true,
            error = errorMsg,
            creationProgress = null
        )

        // Start chained printing
        printCurrentTicketMulti()
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CHAINED PRINTING FOR MULTI-TIRAGE
    // ═══════════════════════════════════════════════════════════════════════

    private fun printCurrentTicketMulti() {
        viewModelScope.launch {
            val tickets = _uiState.value.createdTickets
            val index = _uiState.value.currentPrintIndex
            if (index >= tickets.size) {
                // All printed
                return@launch
            }

            val ticket = tickets[index]
            _uiState.value = _uiState.value.copy(
                printError = null,
                creationProgress = "Impression ${index + 1}/${tickets.size}..."
            )

            try {
                val printData = if (ticket.isOffline) {
                    // Build print data locally for offline ticket
                    // Need to find the lines for this ticket.
                    // For now, assume global lines are used if it's a multi-tirage batch
                    val apiLines = _uiState.value.lines.flatMap { it.toApiLines() }
                    buildOfflinePrintData(ticket, apiLines)
                } else {
                    val printResponse = apiService.getTicketPrint(ticket.ticketId)
                    if (printResponse.isSuccessful) {
                        printResponse.body()?.printData
                    } else {
                        null
                    }
                }

                if (printData != null) {
                    if (printer.isConnected()) {
                        printer.printTicket(printData)
                        markTicketPrinted(index)
                    } else {
                        _uiState.value = _uiState.value.copy(
                            printError = "Imprimante non connectée",
                            creationProgress = null
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        printError = "Erreur récupération données impression",
                        creationProgress = null
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    printError = "Erreur: ${e.message}",
                    creationProgress = null
                )
            }
        }
    }

    private fun markTicketPrinted(index: Int) {
        val tickets = _uiState.value.createdTickets.toMutableList()
        if (index in tickets.indices) {
            tickets[index] = tickets[index].copy(printed = true)
            _uiState.value = _uiState.value.copy(createdTickets = tickets)
        }
    }

    fun printNextTicketMulti() {
        val nextIndex = _uiState.value.currentPrintIndex + 1
        if (nextIndex >= _uiState.value.createdTickets.size) {
            // All done
            _uiState.value = _uiState.value.copy(
                creationProgress = null,
                printError = null
            )
        } else {
            _uiState.value = _uiState.value.copy(currentPrintIndex = nextIndex)
            printCurrentTicketMulti()
        }
    }

    fun skipPrintMulti() {
        printNextTicketMulti()
    }

    fun retryPrintMulti() {
        printCurrentTicketMulti()
    }

    fun toggleFreeMariage(checked: Boolean) {
        _uiState.value = _uiState.value.copy(freeMariageChecked = checked)
    }

    fun resetMultiTirageState() {
        _uiState.value = _uiState.value.copy(
            createdTickets = emptyList(),
            currentPrintIndex = 0,
            printError = null,
            creationProgress = null,
            ticketCreated = false,
            freeMariageChecked = false,
            lines = emptyList() // Added to clear lines on reset
        )
    }

    // ─── Refaire Fiche (Blueprint Pre-fill) ─────────────────────────────────

    private fun prefillFromBlueprint(blueprintLines: List<BlueprintLine>) {
        val newLines = blueprintLines.map { line ->
            TicketLineWithOptions(
                jeu = line.jeu,
                valeur = line.valeur,
                miseBase = line.mise,
                options = emptySet(), // Blueprints are usually simple lines
                useGlobalOptions = false
            )
        }
        _uiState.value = _uiState.value.copy(lines = newLines)
    }

    fun loadBlueprint(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = apiService.getTicketBlueprint(ticketId)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true && body.lines != null) {
                        prefillFromBlueprint(body.lines)
                        _uiState.value = _uiState.value.copy(isLoading = false)
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur récupération blueprint"
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Erreur serveur: ${response.code()}"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }
}
