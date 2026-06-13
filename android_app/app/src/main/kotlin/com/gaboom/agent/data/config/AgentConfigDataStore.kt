package com.gaboom.agent.data.config

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.agentConfigDataStore: DataStore<Preferences> by preferencesDataStore(name = "agent_config")

/**
 * DataStore for agent/borlette configuration including offline mode settings.
 * Phase I-A: Stores allow_offline_print and device credentials.
 */
@Singleton
class AgentConfigDataStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val dataStore = context.agentConfigDataStore

    companion object {
        val ALLOW_OFFLINE_PRINT = booleanPreferencesKey("allow_offline_print")
        val FREE_MARIAGE_ENABLED = booleanPreferencesKey("free_mariage_enabled")
        val DEVICE_ID = stringPreferencesKey("device_id")
        val DEVICE_SECRET = stringPreferencesKey("device_secret")
        val DEVICE_NAME = stringPreferencesKey("device_name")
    }

    // ─── Free Marriage Option ─────────────────────────────────────────────────

    val freeMariageEnabled: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[FREE_MARIAGE_ENABLED] ?: true  // FORCED TO TRUE for testing
    }

    suspend fun getFreeMariageEnabled(): Boolean {
        return freeMariageEnabled.first()
    }

    suspend fun setFreeMariageEnabled(enabled: Boolean) {
        dataStore.edit { prefs ->
            prefs[FREE_MARIAGE_ENABLED] = enabled
        }
    }

    // ─── Offline Print Policy ─────────────────────────────────────────────────

    val allowOfflinePrint: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[ALLOW_OFFLINE_PRINT] ?: false
    }

    suspend fun getAllowOfflinePrint(): Boolean {
        return allowOfflinePrint.first()
    }

    suspend fun setAllowOfflinePrint(allowed: Boolean) {
        dataStore.edit { prefs ->
            prefs[ALLOW_OFFLINE_PRINT] = allowed
        }
    }

    // ─── Device Credentials (for HMAC signing) ─────────────────────────────────

    val deviceId: Flow<String?> = dataStore.data.map { prefs ->
        prefs[DEVICE_ID]
    }

    val deviceSecret: Flow<String?> = dataStore.data.map { prefs ->
        prefs[DEVICE_SECRET]
    }

    val hasDeviceCredentials: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[DEVICE_ID] != null && prefs[DEVICE_SECRET] != null
    }

    suspend fun saveDeviceCredentials(deviceId: String, deviceSecret: String, deviceName: String = "") {
        dataStore.edit { prefs ->
            prefs[DEVICE_ID] = deviceId
            prefs[DEVICE_SECRET] = deviceSecret
            prefs[DEVICE_NAME] = deviceName
        }
    }

    suspend fun getDeviceCredentials(): DeviceCredentials? {
        return dataStore.data.map { prefs ->
            val id = prefs[DEVICE_ID]
            val secret = prefs[DEVICE_SECRET]
            if (id != null && secret != null) {
                DeviceCredentials(id, secret, prefs[DEVICE_NAME] ?: "")
            } else null
        }.first()
    }

    suspend fun clearDeviceCredentials() {
        dataStore.edit { prefs ->
            prefs.remove(DEVICE_ID)
            prefs.remove(DEVICE_SECRET)
            prefs.remove(DEVICE_NAME)
        }
    }

    // ─── Clear All ─────────────────────────────────────────────────────────────

    suspend fun clearAll() {
        dataStore.edit { it.clear() }
    }
}

data class DeviceCredentials(
    val deviceId: String,
    val deviceSecret: String,
    val deviceName: String
)
