package com.gaboom.agent.data.api

import com.gaboom.agent.data.model.HealthResponse
import retrofit2.Response
import retrofit2.http.GET

/**
 * API service for health check endpoint (no auth required).
 */
interface HealthApiService {
    
    @GET("health/")
    suspend fun checkHealth(): Response<HealthResponse>
}
