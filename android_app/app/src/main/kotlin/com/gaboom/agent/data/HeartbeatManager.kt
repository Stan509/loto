package com.gaboom.agent.data

import android.content.Context
import android.location.Location
import android.location.LocationManager
import android.Manifest
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.HeartbeatRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.*
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages periodic heartbeat calls to keep agent online status updated.
 * Calls POST /api/agent/heartbeat/ every 60 seconds with location coordinates when active.
 */
@Singleton
class HeartbeatManager @Inject constructor(
    private val apiService: AgentApiService,
    @ApplicationContext private val context: Context
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
                    val loc = getLastKnownLocation()
                    val req = HeartbeatRequest(
                        latitude = loc?.latitude,
                        longitude = loc?.longitude
                    )
                    apiService.heartbeat(req)
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

    private fun getLastKnownLocation(): Location? {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return null
        }
        
        val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
        val providers = locationManager.getProviders(true)
        var bestLocation: Location? = null
        
        for (provider in providers) {
            try {
                val loc = locationManager.getLastKnownLocation(provider) ?: continue
                if (bestLocation == null || loc.accuracy < bestLocation.accuracy) {
                    bestLocation = loc
                }
            } catch (e: SecurityException) {
                // Ignore security exceptions
            }
        }
        return bestLocation
    }
}
