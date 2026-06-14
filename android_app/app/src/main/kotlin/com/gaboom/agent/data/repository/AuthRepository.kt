package com.gaboom.agent.data.repository

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.model.AgentInfo
import com.gaboom.agent.data.model.BorletteInfo
import com.gaboom.agent.data.model.LoginRequest
import com.gaboom.agent.data.config.AgentConfigDataStore
import com.gaboom.agent.data.model.DeviceRegisterRequest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val dataStore: DataStore<Preferences>,
    private val apiService: AgentApiService,
    private val agentConfigDataStore: AgentConfigDataStore
) {
    companion object {
        private val KEY_ACCESS_TOKEN = stringPreferencesKey("access_token")
        private val KEY_REFRESH_TOKEN = stringPreferencesKey("refresh_token")
        private val KEY_AGENT_ID = stringPreferencesKey("agent_id")
        private val KEY_AGENT_NOM = stringPreferencesKey("agent_nom")
        private val KEY_BORLETTE_ID = stringPreferencesKey("borlette_id")
        private val KEY_BORLETTE_NOM = stringPreferencesKey("borlette_nom")
        private val KEY_BORLETTE_SLOGAN = stringPreferencesKey("borlette_slogan")
        private val KEY_BORLETTE_TEL = stringPreferencesKey("borlette_tel")
        private val KEY_BORLETTE_ADRESSE = stringPreferencesKey("borlette_adresse")
        private val KEY_BORLETTE_LOGO = stringPreferencesKey("borlette_logo")
        private val KEY_TICKET_FOOTER_TEXT = stringPreferencesKey("ticket_footer_text")
        private val KEY_MARIAGE_GRATUIT_ACTIF = stringPreferencesKey("mariage_gratuit_actif")
        private val KEY_MARIAGE_GRATUIT_MONTANT = stringPreferencesKey("mariage_gratuit_montant")
    }

    suspend fun login(username: String, password: String): Result<Unit> {
        return try {
            val response = apiService.login(LoginRequest(username, password))

            if (response.isSuccessful) {
                val body = response.body()
                if (body?.success == true && body.tokens != null && body.agent != null) {
                    // Sauvegarder tokens et info agent
                    saveSession(
                        accessToken = body.tokens.access,
                        refreshToken = body.tokens.refresh,
                        agent = body.agent,
                        borlette = body.borlette
                    )
                    
                    // Phase I-A: Register device for HMAC signing and fetch config
                    registerDeviceAndFetchConfig()
                    
                    Result.success(Unit)
                } else {
                    Result.failure(Exception(body?.error ?: "Erreur de connexion"))
                }
            } else {
                Result.failure(Exception("Identifiants invalides"))
            }
        } catch (e: Exception) {
            Result.failure(Exception("Erreur réseau: ${e.message}"))
        }
    }
    
    /**
     * Phase I-A: Register device for offline HMAC signing and fetch agent config.
     */
    private suspend fun registerDeviceAndFetchConfig() {
        try {
            // Check if device already registered
            val existingCreds = agentConfigDataStore.getDeviceCredentials()
            if (existingCreds == null) {
                // Register new device
                val deviceResponse = apiService.registerDevice(DeviceRegisterRequest("Android Agent App"))
                if (deviceResponse.isSuccessful && deviceResponse.body()?.success == true) {
                    val deviceBody = deviceResponse.body()!!
                    deviceBody.deviceId?.let { deviceId ->
                        deviceBody.deviceSecret?.let { deviceSecret ->
                            agentConfigDataStore.saveDeviceCredentials(deviceId, deviceSecret, "Android Agent App")
                        }
                    }
                }
            }
            
            // Fetch agent config (allow_offline_print, etc.)
            val configResponse = apiService.getAgentConfig()
            if (configResponse.isSuccessful && configResponse.body()?.success == true) {
                val configBody = configResponse.body()!!
                agentConfigDataStore.setAllowOfflinePrint(configBody.allowOfflinePrint)
                
                // Update cached borlette configuration dynamically
                configBody.borlette?.let { borlette ->
                    dataStore.edit { prefs ->
                        prefs[KEY_BORLETTE_ID] = borlette.id.toString()
                        prefs[KEY_BORLETTE_NOM] = borlette.nom
                        prefs[KEY_BORLETTE_SLOGAN] = borlette.slogan
                        prefs[KEY_BORLETTE_TEL] = borlette.telephone
                        prefs[KEY_BORLETTE_ADRESSE] = borlette.adresse
                        prefs[KEY_BORLETTE_LOGO] = borlette.logoUrl
                        prefs[KEY_TICKET_FOOTER_TEXT] = borlette.ticketFooterText
                        prefs[KEY_MARIAGE_GRATUIT_ACTIF] = if (borlette.mariageGratuitActif) "true" else "false"
                        prefs[KEY_MARIAGE_GRATUIT_MONTANT] = borlette.mariageGratuitMontant
                    }
                }
            }
        } catch (e: Exception) {
            // Non-blocking: device registration failure shouldn't prevent login
            // The sync will fail later with clear error message
            e.printStackTrace()
        }
    }

    private suspend fun saveSession(
        accessToken: String,
        refreshToken: String,
        agent: AgentInfo,
        borlette: BorletteInfo?
    ) {
        dataStore.edit { prefs ->
            prefs[KEY_ACCESS_TOKEN] = accessToken
            prefs[KEY_REFRESH_TOKEN] = refreshToken
            prefs[KEY_AGENT_ID] = agent.id.toString()
            prefs[KEY_AGENT_NOM] = agent.nom
            prefs[KEY_BORLETTE_ID] = borlette?.id?.toString() ?: ""
            prefs[KEY_BORLETTE_NOM] = borlette?.nom ?: ""
            prefs[KEY_BORLETTE_SLOGAN] = borlette?.slogan ?: ""
            prefs[KEY_BORLETTE_TEL] = borlette?.telephone ?: ""
            prefs[KEY_BORLETTE_ADRESSE] = borlette?.adresse ?: ""
            prefs[KEY_BORLETTE_LOGO] = borlette?.logoUrl ?: ""
            prefs[KEY_TICKET_FOOTER_TEXT] = borlette?.ticketFooterText ?: ""
            prefs[KEY_MARIAGE_GRATUIT_ACTIF] = if (borlette?.mariageGratuitActif == true) "true" else "false"
            prefs[KEY_MARIAGE_GRATUIT_MONTANT] = borlette?.mariageGratuitMontant ?: "0"
        }
    }

    suspend fun hasValidToken(): Boolean {
        return getAccessToken() != null
    }

    suspend fun getAccessToken(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_ACCESS_TOKEN]
        }.first()
    }

    suspend fun getRefreshToken(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_REFRESH_TOKEN]
        }.first()
    }

    suspend fun getAgentNom(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_AGENT_NOM]
        }.first()
    }
    
    suspend fun getBorletteNom(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_BORLETTE_NOM]
        }.first()
    }
    
    suspend fun getBorletteSlogan(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_BORLETTE_SLOGAN]
        }.first()
    }
    
    suspend fun getBorletteTel(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_BORLETTE_TEL]
        }.first()
    }
    
    suspend fun getBorletteAdresse(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_BORLETTE_ADRESSE]
        }.first()
    }
    
    suspend fun getBorletteLogoUrl(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_BORLETTE_LOGO]
        }.first()
    }
    
    suspend fun getTicketFooterText(): String? {
        return dataStore.data.map { prefs ->
            prefs[KEY_TICKET_FOOTER_TEXT]
        }.first()
    }
    
    suspend fun getMariageGratuitActif(): Boolean {
        return dataStore.data.map { prefs ->
            prefs[KEY_MARIAGE_GRATUIT_ACTIF] == "true"
        }.first()
    }
    
    suspend fun getMariageGratuitMontant(): String {
        return dataStore.data.map { prefs ->
            prefs[KEY_MARIAGE_GRATUIT_MONTANT] ?: "0"
        }.first()
    }

    suspend fun logout() {
        dataStore.edit { prefs ->
            prefs.clear()
        }
    }
}
