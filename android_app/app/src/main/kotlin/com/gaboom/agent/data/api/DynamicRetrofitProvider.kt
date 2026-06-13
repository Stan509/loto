package com.gaboom.agent.data.api

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.stringPreferencesKey
import com.gaboom.agent.data.config.AppConfigDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Dynamic Retrofit provider that can rebuild when base URL changes.
 * Uses atomic reference for thread-safe Retrofit instance swapping.
 */
@Singleton
class DynamicRetrofitProvider @Inject constructor(
    @ApplicationContext private val context: Context,
    private val appConfigDataStore: AppConfigDataStore,
    private val dataStore: DataStore<Preferences>
) {
    private val currentBaseUrl = AtomicReference<String>()
    private val retrofitRef = AtomicReference<Retrofit>()
    private val apiServiceRef = AtomicReference<AgentApiService>()
    
    init {
        // Initialize with current base URL
        val baseUrl = appConfigDataStore.getBaseUrlSync()
        currentBaseUrl.set(baseUrl)
        retrofitRef.set(buildRetrofit(baseUrl))
        apiServiceRef.set(retrofitRef.get().create(AgentApiService::class.java))
    }
    
    /**
     * Get current AgentApiService instance.
     * Call refreshIfNeeded() before using in case base URL changed.
     */
    fun getApiService(): AgentApiService {
        return apiServiceRef.get()
    }
    
    /**
     * Check if base URL changed and rebuild Retrofit if needed.
     */
    fun refreshIfNeeded() {
        val newBaseUrl = appConfigDataStore.getBaseUrlSync()
        val oldBaseUrl = currentBaseUrl.get()
        
        if (newBaseUrl != oldBaseUrl) {
            synchronized(this) {
                // Double-check after acquiring lock
                if (currentBaseUrl.get() != newBaseUrl) {
                    rebuildRetrofit(newBaseUrl)
                }
            }
        }
    }
    
    /**
     * Force rebuild Retrofit with new base URL.
     */
    fun rebuildRetrofit(baseUrl: String) {
        currentBaseUrl.set(baseUrl)
        retrofitRef.set(buildRetrofit(baseUrl))
        apiServiceRef.set(retrofitRef.get().create(AgentApiService::class.java))
    }
    
    /**
     * Get current base URL.
     */
    fun getCurrentBaseUrl(): String {
        return currentBaseUrl.get()
    }
    
    private fun buildRetrofit(baseUrl: String): Retrofit {
        val okHttpClient = buildOkHttpClient()
        
        // Ensure base URL ends with /
        val normalizedUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        
        return Retrofit.Builder()
            .baseUrl(normalizedUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
    
    private fun buildOkHttpClient(): OkHttpClient {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        
        val authInterceptor = Interceptor { chain ->
            val token = runBlocking {
                dataStore.data.map { prefs ->
                    prefs[stringPreferencesKey("access_token")]
                }.first()
            }
            val request = if (token != null) {
                chain.request().newBuilder()
                    .addHeader("Authorization", "Bearer $token")
                    .build()
            } else {
                chain.request()
            }
            chain.proceed(request)
        }
        
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }
    
    /**
     * Create a temporary Retrofit for testing connection to a different URL.
     * Does not affect the main instance.
     */
    fun createTestRetrofit(testBaseUrl: String): Retrofit {
        val normalizedUrl = if (testBaseUrl.endsWith("/")) testBaseUrl else "$testBaseUrl/"
        
        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
        
        return Retrofit.Builder()
            .baseUrl(normalizedUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
}
