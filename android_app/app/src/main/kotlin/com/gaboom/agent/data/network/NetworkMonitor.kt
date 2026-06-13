package com.gaboom.agent.data.network

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Network connectivity monitor using ConnectivityManager.
 * Provides real-time network status updates via Flow.
 */
@Singleton
class NetworkMonitor @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    
    private val _isOnline = MutableStateFlow(checkCurrentConnectivity())
    
    /**
     * StateFlow of current network connectivity status.
     * true = online, false = offline
     */
    val isOnline: StateFlow<Boolean> = _isOnline.asStateFlow()
    
    /**
     * Flow that emits network connectivity changes.
     * Useful for triggering sync when coming back online.
     */
    val connectivityFlow: Flow<Boolean> = callbackFlow {
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                _isOnline.value = true
                trySend(true)
            }
            
            override fun onLost(network: Network) {
                // Double-check if we really lost all connectivity
                val stillConnected = checkCurrentConnectivity()
                _isOnline.value = stillConnected
                trySend(stillConnected)
            }
            
            override fun onCapabilitiesChanged(
                network: Network,
                networkCapabilities: NetworkCapabilities
            ) {
                val hasInternet = networkCapabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                val validated = networkCapabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
                val isConnected = hasInternet && validated
                _isOnline.value = isConnected
                trySend(isConnected)
            }
        }
        
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        
        connectivityManager.registerNetworkCallback(request, callback)
        
        // Emit initial state
        trySend(checkCurrentConnectivity())
        
        awaitClose {
            connectivityManager.unregisterNetworkCallback(callback)
        }
    }.distinctUntilChanged()
    
    /**
     * Check current network connectivity synchronously.
     */
    fun checkCurrentConnectivity(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
               capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
    
    /**
     * Check if currently online (synchronous check).
     */
    fun isCurrentlyOnline(): Boolean = _isOnline.value
}
