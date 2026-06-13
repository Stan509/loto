package com.gaboom.agent.ui.screens.stats

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class StatsUiState(
    val isLoading: Boolean = false,
    val isWithdrawing: Boolean = false,
    val agentNom: String = "",
    val agentZone: String = "",
    val commissionPct: Double = 0.0,
    // Aujourd'hui
    val todayTickets: Int = 0,
    val todayMises: Double = 0.0,
    val todayGainsDu: Double = 0.0,
    val todayGainsPaye: Double = 0.0,
    val todayGainAgent: Double = 0.0,
    val todayCommission: Double = 0.0,
    // Période sélectionnée
    val selectedPeriod: Int = 7,
    val periodDays: Int = 7,
    val periodTickets: Int = 0,
    val periodMises: Double = 0.0,
    val periodGainsDu: Double = 0.0,
    val periodGainsPaye: Double = 0.0,
    val periodGainAgent: Double = 0.0,
    val periodCommission: Double = 0.0,
    // Global (gains totaux dynamiques)
    val globalGainsTotaux: Double = 0.0,
    val soldeCaisse: Double = 0.0,
    val commissionBalance: Double = 0.0,
    val commissionEarned: Double = 0.0,
    val commissionWithdrawn: Double = 0.0,
    // Messages
    val error: String? = null,
    val successMessage: String? = null
)

@HiltViewModel
class StatsViewModel @Inject constructor(
    private val apiService: AgentApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(StatsUiState())
    val uiState: StateFlow<StatsUiState> = _uiState.asStateFlow()

    fun loadStats(period: Int = _uiState.value.selectedPeriod) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, selectedPeriod = period, error = null, successMessage = null)
            try {
                val response = apiService.getDashboard(period)
                if (response.isSuccessful && response.body()?.success == true) {
                    val body = response.body()!!
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        agentNom = body.agent?.nom ?: "",
                        agentZone = body.agent?.zone ?: "",
                        commissionPct = body.agent?.commissionPct ?: 0.0,
                        // Aujourd'hui
                        todayTickets = body.today?.tickets ?: 0,
                        todayMises = body.today?.mises ?: 0.0,
                        todayGainsDu = body.today?.gainsDu ?: 0.0,
                        todayGainsPaye = body.today?.gainsPaye ?: 0.0,
                        todayGainAgent = body.today?.gainAgent ?: 0.0,
                        todayCommission = body.today?.commission ?: 0.0,
                        // Période sélectionnée
                        periodDays = body.period?.days ?: 7,
                        periodTickets = body.period?.tickets ?: 0,
                        periodMises = body.period?.mises ?: 0.0,
                        periodGainsDu = body.period?.gainsDu ?: 0.0,
                        periodGainsPaye = body.period?.gainsPaye ?: 0.0,
                        periodGainAgent = body.period?.gainAgent ?: 0.0,
                        periodCommission = body.period?.commission ?: 0.0,
                        // Global
                        globalGainsTotaux = body.global?.gainsTotaux ?: 0.0,
                        soldeCaisse = body.global?.soldeCaisse ?: 0.0,
                        commissionBalance = body.global?.commissionBalance ?: 0.0,
                        commissionEarned = body.global?.commissionEarned ?: 0.0,
                        commissionWithdrawn = body.global?.commissionWithdrawn ?: 0.0
                    )
                } else {
                    _uiState.value = _uiState.value.copy(isLoading = false, error = "Erreur de chargement")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }

    fun selectPeriod(days: Int) {
        loadStats(days)
    }

    fun withdrawCommission() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isWithdrawing = true, error = null, successMessage = null)
            try {
                val response = apiService.withdrawCommission()
                if (response.isSuccessful && response.body()?.success == true) {
                    val body = response.body()!!
                    _uiState.value = _uiState.value.copy(
                        isWithdrawing = false,
                        successMessage = "Commission de ${body.amountWithdrawn?.toInt() ?: 0} HTG retirée!",
                        commissionBalance = body.newBalance ?: 0.0
                    )
                    // Recharger les stats
                    loadStats()
                } else {
                    _uiState.value = _uiState.value.copy(
                        isWithdrawing = false,
                        error = response.body()?.error ?: "Erreur lors du retrait"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isWithdrawing = false, error = e.message)
            }
        }
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(error = null, successMessage = null)
    }
}
