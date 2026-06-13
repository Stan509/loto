package com.gaboom.agent.ui.screens.tirages

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.Tirage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TiragesUiState(
    val isLoading: Boolean = false,
    val tirages: List<Tirage> = emptyList(),
    val error: String? = null,
    val isOnline: Boolean = true,
    val lastSyncTime: String? = null,
    val serverTime: String? = null
)

@HiltViewModel
class TiragesViewModel @Inject constructor(
    private val apiService: AgentApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(TiragesUiState())
    val uiState: StateFlow<TiragesUiState> = _uiState.asStateFlow()

    fun startAutoRefresh() {
        viewModelScope.launch {
            while (isActive) {
                loadTirages()
                delay(30_000L) // 30 secondes
            }
        }
    }

    fun loadTirages() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.getTiragesActifs()
                if (response.isSuccessful) {
                    val body = response.body()
                    if (body?.success == true) {
                        val now = java.time.LocalTime.now()
                        val syncTime = String.format("%02d:%02d", now.hour, now.minute)
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            tirages = body.tirages ?: emptyList(),
                            isOnline = true,
                            lastSyncTime = syncTime,
                            serverTime = body.serverTime,
                            error = null
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            error = body?.error ?: "Erreur",
                            isOnline = true
                        )
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Erreur serveur",
                        isOnline = false
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Erreur réseau: ${e.message}",
                    isOnline = false
                )
            }
        }
    }
}
