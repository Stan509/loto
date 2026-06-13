package com.gaboom.agent.ui.screens.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.BlueprintLine
import com.gaboom.agent.data.model.TicketSearchResult
import com.gaboom.agent.print.BluetoothPrinter
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SearchTicketUiState(
    val isLoading: Boolean = false,
    val tickets: List<TicketSearchResult> = emptyList(),
    val error: String? = null,
    val successMessage: String? = null,
    val hasSearched: Boolean = false,
    // Blueprint for refaire fiche
    val blueprintLines: List<BlueprintLine>? = null,
    val blueprintReady: Boolean = false,
    val blueprintSourceTicketId: String? = null
)

@HiltViewModel
class SearchTicketViewModel @Inject constructor(
    private val apiService: AgentApiService,
    private val printer: BluetoothPrinter
) : ViewModel() {

    private val _uiState = MutableStateFlow(SearchTicketUiState())
    val uiState: StateFlow<SearchTicketUiState> = _uiState.asStateFlow()

    fun search(query: String) {
        if (query.length < 3) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                error = null,
                successMessage = null,
                hasSearched = true
            )

            try {
                val response = apiService.searchTickets(query)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            tickets = body.tickets ?: emptyList()
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur de recherche"
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
                    error = "Erreur réseau: ${e.message}"
                )
            }
        }
    }

    fun clearResults() {
        _uiState.value = SearchTicketUiState()
    }

    fun printTicket(ticketId: String) {
        viewModelScope.launch {
            try {
                val response = apiService.getTicketPrint(ticketId)
                if (response.isSuccessful) {
                    val printData = response.body()?.printData
                    if (printData != null) {
                        printer.printTicket(printData)
                        _uiState.value = _uiState.value.copy(
                            successMessage = "Impression envoyée"
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    error = "Erreur impression: ${e.message}"
                )
            }
        }
    }

    fun payTicket(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, successMessage = null)

            try {
                val response = apiService.payTicket(ticketId)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            successMessage = "Paiement effectué: ${body.amountPaid?.toInt() ?: 0} HTG"
                        )
                        // Refresh results
                        val currentTickets = _uiState.value.tickets
                        if (currentTickets.isNotEmpty()) {
                            search(currentTickets.first().ticketNo)
                        }
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur paiement"
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
                    error = "Erreur réseau: ${e.message}"
                )
            }
        }
    }

    fun voidTicket(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, successMessage = null)

            try {
                val response = apiService.voidTicket(ticketId)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            successMessage = "Ticket annulé"
                        )
                        // Refresh results
                        val currentTickets = _uiState.value.tickets
                        if (currentTickets.isNotEmpty()) {
                            search(currentTickets.first().ticketNo)
                        }
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur annulation"
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
                    error = "Erreur réseau: ${e.message}"
                )
            }
        }
    }

    // ─── Refaire Fiche (Blueprint) ──────────────────────────────────────────

    fun fetchBlueprint(ticketId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                error = null,
                blueprintReady = false,
                blueprintLines = null
            )

            try {
                val response = apiService.getTicketBlueprint(ticketId)
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true && body.lines != null) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            blueprintLines = body.lines,
                            blueprintReady = true,
                            blueprintSourceTicketId = ticketId
                        )
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
                    error = "Erreur réseau: ${e.message}"
                )
            }
        }
    }

    fun clearBlueprint() {
        _uiState.value = _uiState.value.copy(
            blueprintLines = null,
            blueprintReady = false,
            blueprintSourceTicketId = null
        )
    }
}
