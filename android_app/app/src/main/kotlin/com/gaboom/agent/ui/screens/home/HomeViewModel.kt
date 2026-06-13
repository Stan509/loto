package com.gaboom.agent.ui.screens.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.local.PendingTicketDao
import com.gaboom.agent.data.network.NetworkMonitor
import com.gaboom.agent.data.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val isOnline: Boolean = true,
    val lastSyncTime: String? = null,
    val serverTime: String? = null,
    val pendingSyncCount: Int = 0,
    val borletteName: String = "",
    val borletteLogoUrl: String = "",
    val borletteSlogan: String = "",
    val gainsTotaux: Double = 0.0,
    val soldeCaisse: Double = 0.0,
    val statsLoaded: Boolean = false
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val apiService: AgentApiService,
    private val authRepository: AuthRepository,
    private val pendingTicketDao: PendingTicketDao,
    private val networkMonitor: NetworkMonitor
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()
    
    init {
        observePendingCount()
        observeNetworkStatus()
        loadBorletteInfo()
        loadQuickStats()
    }
    
    private fun loadBorletteInfo() {
        viewModelScope.launch {
            val name = authRepository.getBorletteNom() ?: ""
            val logoUrl = authRepository.getBorletteLogoUrl() ?: ""
            val slogan = authRepository.getBorletteSlogan() ?: ""
            _uiState.value = _uiState.value.copy(
                borletteName = name,
                borletteLogoUrl = logoUrl,
                borletteSlogan = slogan
            )
        }
    }
    
    private fun observePendingCount() {
        viewModelScope.launch {
            pendingTicketDao.getPendingCountFlow().collect { count ->
                _uiState.value = _uiState.value.copy(pendingSyncCount = count)
            }
        }
    }
    
    private fun observeNetworkStatus() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { isOnline ->
                _uiState.value = _uiState.value.copy(isOnline = isOnline)
            }
        }
    }
    
    fun loadQuickStats() {
        viewModelScope.launch {
            try {
                val response = apiService.getDashboard(7)
                if (response.isSuccessful && response.body()?.success == true) {
                    val global = response.body()!!.global
                    _uiState.value = _uiState.value.copy(
                        gainsTotaux = global?.gainsTotaux ?: 0.0,
                        soldeCaisse = global?.soldeCaisse ?: 0.0,
                        statsLoaded = true
                    )
                }
            } catch (_: Exception) { }
        }
    }

    fun logout(onComplete: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onComplete()
        }
    }

    fun startConnectivityCheck() {
        viewModelScope.launch {
            while (isActive) {
                checkConnectivity()
                loadQuickStats()
                delay(30_000L) // 30 secondes
            }
        }
    }

    fun checkConnectivity() {
        viewModelScope.launch {
            try {
                val response = apiService.getTiragesActifs()
                if (response.isSuccessful && response.body()?.success == true) {
                    val now = java.time.LocalTime.now()
                    val syncTime = String.format("%02d:%02d", now.hour, now.minute)
                    _uiState.value = _uiState.value.copy(
                        isOnline = true,
                        lastSyncTime = syncTime,
                        serverTime = response.body()?.serverTime
                    )
                } else {
                    _uiState.value = _uiState.value.copy(isOnline = false)
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isOnline = false)
            }
        }
    }
}
