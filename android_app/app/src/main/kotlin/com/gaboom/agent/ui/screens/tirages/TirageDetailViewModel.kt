package com.gaboom.agent.ui.screens.tirages

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.local.LocalTicketCache
import com.gaboom.agent.data.local.LocalTicketCacheDao
import com.gaboom.agent.data.local.TirageSessionCache
import com.gaboom.agent.data.local.TirageSessionCacheDao
import com.gaboom.agent.data.api.AgentApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TirageDetailUiState(
    val isLoading: Boolean = false,
    val tickets: List<LocalTicketCache> = emptyList(),
    val error: String? = null
)

@HiltViewModel
class TirageDetailViewModel @Inject constructor(
    private val apiService: AgentApiService,
    private val localTicketCacheDao: LocalTicketCacheDao,
    private val tirageSessionCacheDao: TirageSessionCacheDao
) : ViewModel() {

    private val _uiState = MutableStateFlow(TirageDetailUiState())
    val uiState: StateFlow<TirageDetailUiState> = _uiState.asStateFlow()

    fun loadTicketsForTirage(tirageId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            try {
                // Fetch current session_key from API
                val response = apiService.getTiragesActifs()
                if (response.isSuccessful) {
                    val tirages = response.body()?.tirages ?: emptyList()
                    val tirage = tirages.find { it.id == tirageId }
                    
                    if (tirage != null && tirage.sessionKey != null) {
                        val currentSessionKey = tirage.sessionKey
                        
                        // Check if session changed - purge old tickets if so
                        val cachedSession = tirageSessionCacheDao.getSessionForTirage(tirageId)
                        if (cachedSession != null && cachedSession.sessionKey != currentSessionKey) {
                            // Session changed - purge old tickets (éphémère local only)
                            localTicketCacheDao.purgeOldSessions(tirageId, currentSessionKey)
                        }
                        
                        // Update session cache
                        tirageSessionCacheDao.upsert(
                            TirageSessionCache(
                                tirageId = tirageId,
                                sessionKey = currentSessionKey
                            )
                        )
                    }
                }
            } catch (e: Exception) {
                // Network error - continue with cached data
            }

            // Load from local cache
            viewModelScope.launch {
                localTicketCacheDao.getTicketsForTirage(tirageId).collect { tickets ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        tickets = tickets
                    )
                }
            }
        }
    }

    fun cacheTicket(
        tirageId: Int,
        sessionKey: String,
        ticketUuid: String,
        ticketNo: String,
        totalMise: Double
    ) {
        viewModelScope.launch {
            localTicketCacheDao.insert(
                LocalTicketCache(
                    ticketUuid = ticketUuid,
                    tirageId = tirageId,
                    sessionKey = sessionKey,
                    ticketNo = ticketNo,
                    totalMise = totalMise
                )
            )
        }
    }
}
