package com.gaboom.agent.ui.screens.historique

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.TicketInfo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HistoriqueUiState(
    val isLoading: Boolean = false,
    val tickets: List<TicketInfo> = emptyList(),
    val error: String? = null
)

@HiltViewModel
class HistoriqueViewModel @Inject constructor(
    private val apiService: AgentApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(HistoriqueUiState())
    val uiState: StateFlow<HistoriqueUiState> = _uiState.asStateFlow()

    fun loadHistorique() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val response = apiService.getHistorique()
                if (response.isSuccessful && response.body()?.success == true) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        tickets = response.body()?.tickets ?: emptyList()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
            }
        }
    }
}
