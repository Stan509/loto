package com.gaboom.agent.data.config

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.gaboom.agent.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import javax.inject.Inject
import javax.inject.Singleton

private val Context.configDataStore: DataStore<Preferences> by preferencesDataStore(name = "app_config")

/**
 * DataStore for app configuration (base URL, etc.)
 * Allows runtime configuration without recompiling.
 */
@Singleton
class AppConfigDataStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private val BASE_URL_KEY = stringPreferencesKey("base_url")
        private val THEME_MODE_KEY = stringPreferencesKey("theme_mode")
        
        // Default from BuildConfig, but can be overridden at runtime
        val DEFAULT_BASE_URL: String = BuildConfig.API_BASE_URL
        
        // Theme modes: "default", "light", "dark"
        const val THEME_DEFAULT = "default"
        const val THEME_LIGHT = "light"
        const val THEME_DARK = "dark"
    }
    
    /**
     * Flow of current base URL (API endpoint)
     */
    val baseUrlFlow: Flow<String> = context.configDataStore.data.map { prefs ->
        prefs[BASE_URL_KEY] ?: DEFAULT_BASE_URL
    }
    
    /**
     * Get current base URL synchronously (for Retrofit initialization)
     */
    fun getBaseUrlSync(): String {
        return runBlocking {
            context.configDataStore.data.map { prefs ->
                prefs[BASE_URL_KEY] ?: DEFAULT_BASE_URL
            }.first()
        }
    }
    
    /**
     * Save new base URL
     */
    suspend fun setBaseUrl(url: String) {
        context.configDataStore.edit { prefs ->
            prefs[BASE_URL_KEY] = url.trimEnd('/')
        }
    }
    
    /**
     * Reset to default base URL
     */
    suspend fun resetToDefault() {
        context.configDataStore.edit { prefs ->
            prefs.remove(BASE_URL_KEY)
        }
    }
    
    /**
     * Check if a custom base URL is set
     */
    suspend fun hasCustomBaseUrl(): Boolean {
        return context.configDataStore.data.map { prefs ->
            prefs[BASE_URL_KEY] != null
        }.first()
    }
    
    /**
     * Flow of current theme mode
     */
    val themeModeFlow: Flow<String> = context.configDataStore.data.map { prefs ->
        prefs[THEME_MODE_KEY] ?: THEME_DEFAULT
    }
    
    /**
     * Get current theme mode synchronously
     */
    fun getThemeModeSync(): String {
        return runBlocking {
            context.configDataStore.data.map { prefs ->
                prefs[THEME_MODE_KEY] ?: THEME_DEFAULT
            }.first()
        }
    }
    
    /**
     * Save theme mode
     */
    suspend fun setThemeMode(mode: String) {
        context.configDataStore.edit { prefs ->
            prefs[THEME_MODE_KEY] = mode
        }
    }
}
