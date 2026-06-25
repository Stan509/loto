package com.gaboom.agent.data

import android.content.Context
import android.location.Location
import android.location.LocationManager
import android.location.LocationListener
import android.os.Bundle
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
    private var lastLocation: Location? = null

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            lastLocation = location
        }
        @Deprecated("Deprecated in Java")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }

    companion object {
        private const val HEARTBEAT_INTERVAL_MS = 60_000L // 60 seconds
    }

    fun start() {
        if (heartbeatJob?.isActive == true) return
        
        registerLocationListener()
        
        heartbeatJob = scope.launch {
            while (isActive) {
                try {
                    val loc = lastLocation ?: getLastKnownLocation()
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
        unregisterLocationListener()
    }

    fun isRunning(): Boolean = heartbeatJob?.isActive == true

    private fun registerLocationListener() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return
        }
        try {
            val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return
            
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    10_000L,
                    10f,
                    locationListener
                )
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    10_000L,
                    10f,
                    locationListener
                )
            }
        } catch (e: SecurityException) {
            // Ignore
        } catch (e: Exception) {
            // Ignore
        }
    }

    private fun unregisterLocationListener() {
        try {
            val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return
            locationManager.removeUpdates(locationListener)
        } catch (e: Exception) {
            // Ignore
        }
    }

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
