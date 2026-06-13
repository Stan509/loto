package com.gaboom.agent.ui.screens.sync

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.data.local.PendingTicketDao
import com.gaboom.agent.data.local.PendingTicketEntity
import com.gaboom.agent.data.local.SyncStatus
import com.gaboom.agent.data.network.NetworkMonitor
import com.gaboom.agent.data.sync.SyncEvent
import com.gaboom.agent.data.sync.SyncManager
import com.gaboom.agent.data.sync.SyncState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Represents a batch of tickets for UI display
 */
data class TicketBatchUi(
    val batchId: String,
    val batchLabel: String,
    val tickets: List<PendingTicketEntity>,
    val overallStatus: BatchOverallStatus,
    val totalAmount: Double,
    val createdAt: Long
) {
    val successCount: Int get() = tickets.count { it.syncStatus == SyncStatus.SYNCED }
    val failedCount: Int get() = tickets.count { it.syncStatus == SyncStatus.FAILED }
    val pendingCount: Int get() = tickets.count { it.syncStatus == SyncStatus.PENDING }
    val syncingCount: Int get() = tickets.count { it.syncStatus == SyncStatus.SYNCING }
}

enum class BatchOverallStatus {
    PENDING,      // All tickets pending
    SYNCING,      // Currently syncing
    SYNCED,       // All tickets synced
    PARTIAL,      // Some success, some failed
    FAILED        // All failed
}

data class SyncUiState(
    val isOnline: Boolean = true,
    val isSyncing: Boolean = false,
    val batches: List<TicketBatchUi> = emptyList(),
    val pendingCount: Int = 0,
    val failedCount: Int = 0,
    val successMessage: String? = null,
    val errorMessage: String? = null
)

@HiltViewModel
class SyncViewModel @Inject constructor(
    private val syncManager: SyncManager,
    private val pendingTicketDao: PendingTicketDao,
    private val networkMonitor: NetworkMonitor
) : ViewModel() {

    private val _uiState = MutableStateFlow(SyncUiState())
    val uiState: StateFlow<SyncUiState> = _uiState.asStateFlow()

    init {
        observeNetworkStatus()
        observePendingTickets()
        observeSyncState()
        observeSyncEvents()
    }

    private fun observeNetworkStatus() {
        viewModelScope.launch {
            networkMonitor.isOnline.collect { isOnline ->
                _uiState.update { it.copy(isOnline = isOnline) }
            }
        }
    }

    private fun observePendingTickets() {
        viewModelScope.launch {
            pendingTicketDao.getAllFlow().collect { tickets ->
                val unsynced = tickets.filter { it.syncStatus != SyncStatus.SYNCED }
                val pending = unsynced.filter { it.syncStatus == SyncStatus.PENDING || it.syncStatus == SyncStatus.SYNCING }
                val failed = unsynced.filter { it.syncStatus == SyncStatus.FAILED }
                
                // Group by batch
                val batches = groupTicketsIntoBatches(unsynced)
                
                _uiState.update { 
                    it.copy(
                        batches = batches,
                        pendingCount = pending.size,
                        failedCount = failed.size
                    )
                }
            }
        }
    }

    private fun groupTicketsIntoBatches(tickets: List<PendingTicketEntity>): List<TicketBatchUi> {
        val grouped = tickets.groupBy { it.batchId ?: "single_${it.id}" }
        
        return grouped.map { (batchId, ticketList) ->
            val label = ticketList.firstOrNull()?.batchLabel ?: "Ticket unique"
            val status = determineBatchStatus(ticketList)
            val totalAmount = ticketList.sumOf { it.totalMise }
            val createdAt = ticketList.minOfOrNull { it.createdAt } ?: System.currentTimeMillis()
            
            TicketBatchUi(
                batchId = batchId,
                batchLabel = label,
                tickets = ticketList.sortedBy { it.createdAt },
                overallStatus = status,
                totalAmount = totalAmount,
                createdAt = createdAt
            )
        }.sortedByDescending { it.createdAt }
    }

    private fun determineBatchStatus(tickets: List<PendingTicketEntity>): BatchOverallStatus {
        val statuses = tickets.map { it.syncStatus }
        
        return when {
            statuses.all { it == SyncStatus.SYNCED } -> BatchOverallStatus.SYNCED
            statuses.all { it == SyncStatus.FAILED } -> BatchOverallStatus.FAILED
            statuses.any { it == SyncStatus.SYNCING } -> BatchOverallStatus.SYNCING
            statuses.any { it == SyncStatus.SYNCED } && statuses.any { it == SyncStatus.FAILED } -> BatchOverallStatus.PARTIAL
            else -> BatchOverallStatus.PENDING
        }
    }

    private fun observeSyncState() {
        viewModelScope.launch {
            syncManager.syncState.collect { state ->
                _uiState.update { it.copy(isSyncing = state.isSyncing) }
            }
        }
    }

    private fun observeSyncEvents() {
        viewModelScope.launch {
            syncManager.syncEvents.collect { event ->
                when (event) {
                    is SyncEvent.TicketSynced -> {
                        _uiState.update { 
                            it.copy(successMessage = "Ticket ${event.serverTicketNo} synchronisé ✓")
                        }
                    }
                    is SyncEvent.TicketFailed -> {
                        _uiState.update { 
                            it.copy(errorMessage = "Échec sync: ${event.error}")
                        }
                    }
                    is SyncEvent.TicketDeleted -> {
                        _uiState.update { 
                            it.copy(successMessage = "Ticket supprimé")
                        }
                    }
                    is SyncEvent.BatchSuccess -> {
                        _uiState.update {
                            it.copy(successMessage = "Lot synchronisé avec succès ✓")
                        }
                    }
                    is SyncEvent.BatchPartial -> {
                        _uiState.update {
                            it.copy(successMessage = "Lot partiel: ${event.successCount} OK, ${event.failedCount} échecs")
                        }
                    }
                    is SyncEvent.BatchFailed -> {
                        _uiState.update {
                            it.copy(errorMessage = "Échec lot: ${event.error}")
                        }
                    }
                    is SyncEvent.BatchDeleted -> {
                        _uiState.update {
                            it.copy(successMessage = "Lot supprimé")
                        }
                    }
                    is SyncEvent.Error -> {
                        _uiState.update { 
                            it.copy(errorMessage = event.message)
                        }
                    }
                }
            }
        }
    }

    fun syncNow() {
        if (!networkMonitor.isCurrentlyOnline()) {
            _uiState.update { it.copy(errorMessage = "Pas de connexion internet") }
            return
        }
        syncManager.syncPendingTickets()
    }

    fun syncBatch(batchId: String) {
        if (!networkMonitor.isCurrentlyOnline()) {
            _uiState.update { it.copy(errorMessage = "Pas de connexion internet") }
            return
        }
        viewModelScope.launch {
            syncManager.retryBatch(batchId)
        }
    }

    fun deleteBatch(batchId: String) {
        viewModelScope.launch {
            syncManager.deleteBatch(batchId)
        }
    }

    fun retryTicket(ticketId: String) {
        viewModelScope.launch {
            syncManager.retryTicket(ticketId)
        }
    }

    fun deleteTicket(ticketId: String) {
        viewModelScope.launch {
            syncManager.deleteTicket(ticketId)
        }
    }

    fun cleanupSynced() {
        viewModelScope.launch {
            syncManager.cleanupSynced()
            _uiState.update { it.copy(successMessage = "Tickets synchronisés nettoyés") }
        }
    }

    fun clearMessages() {
        _uiState.update { it.copy(successMessage = null, errorMessage = null) }
    }
}
