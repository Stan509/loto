package com.gaboom.agent.ui.screens.tickets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.TicketGroupItem
import com.gaboom.agent.data.model.TicketListItem
import com.gaboom.agent.data.model.Tirage
import com.gaboom.agent.print.BluetoothPrinter
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import javax.inject.Inject

enum class TicketStatusFilter(val value: String, val display: String) {
    ALL("", "Tous"),
    PENDING("pending", "En cours"),
    WON("won", "Gagné"),
    LOST("lost", "Perdu"),
    PAID("paid", "Déjà payé"),
    CANCELLED("cancelled", "Annulé")
}

data class TicketManagementUiState(
    val isLoading: Boolean = false,
    val tickets: List<TicketListItem> = emptyList(),
    val totalTickets: Int = 0,
    val error: String? = null,
    val successMessage: String? = null,
    
    // Filters
    val selectedDate: LocalDate? = LocalDate.now(),
    val selectedTirageId: Int? = null,
    val statusFilter: TicketStatusFilter = TicketStatusFilter.ALL,
    val searchQuery: String = "",
    
    // Available tirages for filter dropdown
    val availableTirages: List<Tirage> = emptyList(),
    
    // Action states
    val payingTicketId: String? = null,
    val voidingTicketId: String? = null,
    val reprintingTicketId: String? = null,
    
    // Group search (QR code)
    val groupTickets: List<TicketGroupItem> = emptyList(),
    val isSearchingGroup: Boolean = false,
    
    // Pagination
    val currentPage: Int = 0,
    val pageSize: Int = 50,
    val hasMore: Boolean = false
)

@HiltViewModel
class TicketManagementViewModel @Inject constructor(
    private val apiService: AgentApiService,
    private val bluetoothPrinter: BluetoothPrinter
) : ViewModel() {

    private val _uiState = MutableStateFlow(TicketManagementUiState())
    val uiState: StateFlow<TicketManagementUiState> = _uiState.asStateFlow()

    init {
        loadTirages()
        loadTickets()
    }

    private fun loadTirages() {
        viewModelScope.launch {
            try {
                val response = apiService.getTiragesActifs()
                if (response.isSuccessful && response.body()?.success == true) {
                    _uiState.value = _uiState.value.copy(
                        availableTirages = response.body()?.tirages ?: emptyList()
                    )
                }
            } catch (e: Exception) {
                // Ignore - tirages filter is optional
            }
        }
    }

    fun loadTickets(refresh: Boolean = false) {
        viewModelScope.launch {
            val currentState = _uiState.value
            val offset = if (refresh) 0 else currentState.currentPage * currentState.pageSize

            _uiState.value = currentState.copy(
                isLoading = true,
                error = null,
                currentPage = if (refresh) 0 else currentState.currentPage
            )

            try {
                val dateStr = currentState.selectedDate?.format(DateTimeFormatter.ISO_LOCAL_DATE)
                val response = apiService.listTickets(
                    date = dateStr,
                    tirageId = currentState.selectedTirageId,
                    status = currentState.statusFilter.value.ifEmpty { null },
                    limit = currentState.pageSize,
                    offset = offset
                )

                if (response.isSuccessful && response.body()?.success == true) {
                    val body = response.body()!!
                    val newTickets = body.tickets ?: emptyList()
                    
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        tickets = if (refresh) newTickets else currentState.tickets + newTickets,
                        totalTickets = body.total ?: newTickets.size,
                        hasMore = newTickets.size >= currentState.pageSize
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = response.body()?.error ?: "Erreur lors du chargement"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur réseau: ${e.message}"
                )
            }
        }
    }

    fun loadMore() {
        if (_uiState.value.isLoading || !_uiState.value.hasMore) return
        _uiState.value = _uiState.value.copy(currentPage = _uiState.value.currentPage + 1)
        loadTickets(refresh = false)
    }

    fun setDateFilter(date: LocalDate?) {
        _uiState.value = _uiState.value.copy(selectedDate = date)
        loadTickets(refresh = true)
    }

    fun setTirageFilter(tirageId: Int?) {
        _uiState.value = _uiState.value.copy(selectedTirageId = tirageId)
        loadTickets(refresh = true)
    }

    fun setStatusFilter(filter: TicketStatusFilter) {
        _uiState.value = _uiState.value.copy(statusFilter = filter)
        loadTickets(refresh = true)
    }

    fun setSearchQuery(query: String) {
        _uiState.value = _uiState.value.copy(searchQuery = query)
    }

    fun searchByQuery() {
        val query = _uiState.value.searchQuery.trim()
        if (query.isEmpty()) {
            loadTickets(refresh = true)
            return
        }
        
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            
            try {
                val response = apiService.searchTickets(query)
                if (response.isSuccessful && response.body()?.success == true) {
                    // Convert search results to list items (simplified)
                    val searchResults = response.body()?.tickets ?: emptyList()
                    val items = searchResults.map { result ->
                        TicketListItem(
                            id = result.id,
                            numero = result.ticketNo,
                            tirageId = result.tirageId,
                            tirageNom = result.tirageNom,
                            tirageOpen = false,
                            status = when {
                                result.statut == "ANNULE" -> "cancelled"
                                result.isPaid -> "paid"
                                result.isWinner -> "won"
                                else -> "pending"
                            },
                            numBets = result.lines?.size ?: 0,
                            totalMise = result.totalMise,
                            totalGainDu = result.totalGainDu,
                            totalGainPaye = 0.0,
                            isWinner = result.isWinner,
                            isPaid = result.isPaid,
                            canPay = result.isWinner && !result.isPaid,
                            canVoid = result.canVoid,
                            canReprint = result.statut != "ANNULE",
                            createdAt = result.createdAt,
                            ageMinutes = 0.0
                        )
                    }
                    
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        tickets = items,
                        totalTickets = items.size,
                        hasMore = false
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = response.body()?.error ?: "Ticket non trouvé"
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

    fun payTicket(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(payingTicketId = ticketId, error = null)
            
            try {
                val response = apiService.payTicket(ticketId)
                if (response.isSuccessful && response.body()?.success == true) {
                    val amount = response.body()?.amountPaid ?: 0.0
                    _uiState.value = _uiState.value.copy(
                        payingTicketId = null,
                        successMessage = "Ticket payé: ${amount.toInt()} G"
                    )
                    // Refresh to update status
                    loadTickets(refresh = true)
                } else {
                    _uiState.value = _uiState.value.copy(
                        payingTicketId = null,
                        error = response.body()?.error ?: "Erreur lors du paiement"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    payingTicketId = null,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    fun voidTicket(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(voidingTicketId = ticketId, error = null)
            
            try {
                val response = apiService.voidTicket(ticketId)
                if (response.isSuccessful && response.body()?.success == true) {
                    _uiState.value = _uiState.value.copy(
                        voidingTicketId = null,
                        successMessage = "Ticket annulé"
                    )
                    // Refresh to update status
                    loadTickets(refresh = true)
                } else {
                    _uiState.value = _uiState.value.copy(
                        voidingTicketId = null,
                        error = response.body()?.error ?: "Erreur lors de l'annulation"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    voidingTicketId = null,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    suspend fun voidTicketSync(ticketId: String): Boolean {
        return try {
            val response = apiService.voidTicket(ticketId)
            response.isSuccessful && response.body()?.success == true
        } catch (e: Exception) {
            false
        }
    }

    fun reprintTicket(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(reprintingTicketId = ticketId, error = null)
            
            try {
                val response = apiService.getTicketPrint(ticketId)
                if (response.isSuccessful && response.body()?.success == true) {
                    val printData = response.body()?.printData
                    if (printData != null) {
                        val printResult = bluetoothPrinter.printTicket(printData)
                        if (printResult.isSuccess) {
                            _uiState.value = _uiState.value.copy(
                                reprintingTicketId = null,
                                successMessage = "Ticket réimprimé"
                            )
                        } else {
                            _uiState.value = _uiState.value.copy(
                                reprintingTicketId = null,
                                error = "Erreur impression: ${printResult.exceptionOrNull()?.message}"
                            )
                        }
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        reprintingTicketId = null,
                        error = response.body()?.error ?: "Erreur récupération données"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    reprintingTicketId = null,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccessMessage() {
        _uiState.value = _uiState.value.copy(successMessage = null)
    }

    fun onQrCodeScanned(content: String) {
        // QR code contains ticket number or ID
        _uiState.value = _uiState.value.copy(searchQuery = content)
        searchByQuery()
    }

    fun searchByGroupId(groupId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSearchingGroup = true, error = null)
            
            try {
                val response = apiService.searchTicketsByGroup(groupId)
                if (response.isSuccessful && response.body()?.success == true) {
                    _uiState.value = _uiState.value.copy(
                        isSearchingGroup = false,
                        groupTickets = response.body()?.tickets ?: emptyList()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isSearchingGroup = false,
                        error = response.body()?.error ?: "Aucun ticket trouvé pour ce QR code"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isSearchingGroup = false,
                    error = "Erreur: ${e.message}"
                )
            }
        }
    }

    fun clearGroupResults() {
        _uiState.value = _uiState.value.copy(groupTickets = emptyList())
    }

    suspend fun getTicketPrintData(ticketId: String): com.gaboom.agent.data.model.PrintData? {
        return try {
            val response = apiService.getTicketPrint(ticketId)
            if (response.isSuccessful && response.body()?.success == true) {
                response.body()?.printData
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }
}
