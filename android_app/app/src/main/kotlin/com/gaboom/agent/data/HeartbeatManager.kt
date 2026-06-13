package com.gaboom.agent.data

import com.gaboom.agent.data.api.AgentApiService
import kotlinx.coroutines.*
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages periodic heartbeat calls to keep agent online status updated.
 * Calls POST /api/agent/heartbeat/ every 60 seconds when active.
 */
@Singleton
class HeartbeatManager @Inject constructor(
    private val apiService: AgentApiService
) {
    private var heartbeatJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    companion object {
        private const val HEARTBEAT_INTERVAL_MS = 60_000L // 60 seconds
    }

    fun start() {
        if (heartbeatJob?.isActive == true) return
        
        heartbeatJob = scope.launch {
            while (isActive) {
                try {
                    apiService.heartbeat()
                } catch (e: Exception) {
                    // Silently ignore heartbeat errors
                }
                delay(HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    fun stop() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    fun isRunning(): Boolean = heartbeatJob?.isActive == true
}
