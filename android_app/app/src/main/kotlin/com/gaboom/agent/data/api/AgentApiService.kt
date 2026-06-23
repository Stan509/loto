package com.gaboom.agent.data.api

import com.gaboom.agent.data.model.AgentConfigResponse
import com.gaboom.agent.data.model.CommissionHistoryResponse
import com.gaboom.agent.data.model.DashboardResponse
import com.gaboom.agent.data.model.DeviceRegisterRequest
import com.gaboom.agent.data.model.WithdrawCommissionResponse
import com.gaboom.agent.data.model.DeviceRegisterResponse
import com.gaboom.agent.data.model.DisponiblesResponse
import com.gaboom.agent.data.model.HeartbeatResponse
import com.gaboom.agent.data.model.HeartbeatRequest
import com.gaboom.agent.data.model.HistoriqueResponse
import com.gaboom.agent.data.model.LoginRequest
import com.gaboom.agent.data.model.LoginResponse
import com.gaboom.agent.data.model.MultiTicketCreateRequest
import com.gaboom.agent.data.model.MultiTicketCreateResponse
import com.gaboom.agent.data.model.ResultatsResponse
import com.gaboom.agent.data.model.TicketBlueprintResponse
import com.gaboom.agent.data.model.TicketCreateRequest
import com.gaboom.agent.data.model.TicketCreateResponse
import com.gaboom.agent.data.model.TicketGroupResponse
import com.gaboom.agent.data.model.TicketListResponse
import com.gaboom.agent.data.model.TicketPayResponse
import com.gaboom.agent.data.model.TicketPreviewResponse
import com.gaboom.agent.data.model.TicketPrintResponse
import com.gaboom.agent.data.model.TicketSearchResponse
import com.gaboom.agent.data.model.TicketVoidResponse
import com.gaboom.agent.data.model.TiragesResponse
import retrofit2.Response
import retrofit2.http.*

/**
 * Interface Retrofit pour l'API Agent
 */
interface AgentApiService {

    // ─── Auth ──────────────────────────────────────────────────────────────

    @POST("auth/login/")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    // ─── Tirages ───────────────────────────────────────────────────────────

    @GET("tirages/")
    suspend fun getTiragesActifs(): Response<TiragesResponse>

    @GET("tirage/{tirageId}/disponibles/")
    suspend fun getDisponibles(@Path("tirageId") tirageId: Int): Response<DisponiblesResponse>

    // ─── Tickets ───────────────────────────────────────────────────────────

    @POST("ticket/preview/")
    suspend fun previewTicket(@Body request: TicketCreateRequest): Response<TicketPreviewResponse>

    @POST("ticket/create/")
    suspend fun createTicket(@Body request: TicketCreateRequest): Response<TicketCreateResponse>

    @POST("ticket/create-multi/")
    suspend fun createMultiTicket(@Body request: MultiTicketCreateRequest): Response<MultiTicketCreateResponse>

    @POST("ticket/create-multi/")
    suspend fun createMultiTicketWithHeaders(
        @Body request: MultiTicketCreateRequest,
        @Header("X-DEVICE-ID") deviceId: String,
        @Header("X-PAYLOAD-SIGN") payloadSign: String
    ): Response<MultiTicketCreateResponse>

    @GET("ticket/{ticketId}/")
    suspend fun getTicketDetail(@Path("ticketId") ticketId: String): Response<TicketCreateResponse>

    @GET("ticket/{ticketId}/print/")
    suspend fun getTicketPrint(@Path("ticketId") ticketId: String): Response<TicketPrintResponse>

    // ─── Historique & Résultats ────────────────────────────────────────────

    @GET("historique/")
    suspend fun getHistorique(
        @Query("limit") limit: Int = 20,
        @Query("offset") offset: Int = 0
    ): Response<HistoriqueResponse>

    @GET("resultats/")
    suspend fun getResultats(@Query("limit") limit: Int = 20): Response<ResultatsResponse>

    // ─── Dashboard ─────────────────────────────────────────────────────────

    @GET("dashboard/")
    suspend fun getDashboard(@Query("period") period: Int = 7): Response<DashboardResponse>

    // ─── Commission ─────────────────────────────────────────────────────────

    @POST("commission/withdraw/")
    suspend fun withdrawCommission(): Response<WithdrawCommissionResponse>

    @GET("commission/history/")
    suspend fun getCommissionHistory(@Query("period") period: Int = 30): Response<CommissionHistoryResponse>

    // ─── Ticket Search / Pay / Void ───────────────────────────────────────────

    @GET("tickets/list/")
    suspend fun listTickets(
        @Query("date") date: String? = null,
        @Query("tirage_id") tirageId: Int? = null,
        @Query("status") status: String? = null,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<TicketListResponse>

    @GET("tickets/search/")
    suspend fun searchTickets(@Query("q") query: String): Response<TicketSearchResponse>

    @GET("tickets/group/{groupId}/")
    suspend fun searchTicketsByGroup(@Path("groupId") groupId: String): Response<TicketGroupResponse>

    @POST("ticket/{ticketId}/pay/")
    suspend fun payTicket(@Path("ticketId") ticketId: String): Response<TicketPayResponse>

    @POST("ticket/{ticketId}/void/")
    suspend fun voidTicket(@Path("ticketId") ticketId: String): Response<TicketVoidResponse>

    @GET("ticket/{ticketId}/blueprint/")
    suspend fun getTicketBlueprint(@Path("ticketId") ticketId: String): Response<TicketBlueprintResponse>

    // ─── Heartbeat ──────────────────────────────────────────────────────────

    @POST("heartbeat/")
    suspend fun heartbeat(@Body request: HeartbeatRequest): Response<HeartbeatResponse>

    // ─── Device Registration & Config (Phase I-A) ───────────────────────────

    @POST("device/register/")
    suspend fun registerDevice(@Body request: DeviceRegisterRequest): Response<DeviceRegisterResponse>

    @GET("config/")
    suspend fun getAgentConfig(): Response<AgentConfigResponse>
}
