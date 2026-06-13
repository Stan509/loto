package com.gaboom.agent.di

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import androidx.room.Room
import com.gaboom.agent.data.api.AgentApiService
import com.gaboom.agent.data.api.DynamicRetrofitProvider
import com.gaboom.agent.data.config.AgentConfigDataStore
import com.gaboom.agent.data.config.AppConfigDataStore
import com.gaboom.agent.data.local.AgentDatabase
import com.gaboom.agent.data.local.LocalTicketCacheDao
import com.gaboom.agent.data.local.PendingTicketDao
import com.gaboom.agent.data.local.TirageSessionCacheDao
import com.gaboom.agent.data.network.NetworkMonitor
import com.gaboom.agent.data.sync.SyncManager
import com.gaboom.agent.print.BluetoothPrinter
import com.google.gson.Gson
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "auth_prefs")

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideDataStore(@ApplicationContext context: Context): DataStore<Preferences> {
        return context.dataStore
    }

    @Provides
    @Singleton
    fun provideAppConfigDataStore(@ApplicationContext context: Context): AppConfigDataStore {
        return AppConfigDataStore(context)
    }

    @Provides
    @Singleton
    fun provideAgentConfigDataStore(@ApplicationContext context: Context): AgentConfigDataStore {
        return AgentConfigDataStore(context)
    }

    @Provides
    @Singleton
    fun provideDynamicRetrofitProvider(
        @ApplicationContext context: Context,
        appConfigDataStore: AppConfigDataStore,
        dataStore: DataStore<Preferences>
    ): DynamicRetrofitProvider {
        return DynamicRetrofitProvider(context, appConfigDataStore, dataStore)
    }

    @Provides
    @Singleton
    fun provideAgentApiService(dynamicRetrofitProvider: DynamicRetrofitProvider): AgentApiService {
        return dynamicRetrofitProvider.getApiService()
    }

    @Provides
    @Singleton
    fun provideBluetoothPrinter(@ApplicationContext context: Context): BluetoothPrinter {
        return BluetoothPrinter(context)
    }

    // ─── Room Database ────────────────────────────────────────────────────────

    @Provides
    @Singleton
    fun provideAgentDatabase(@ApplicationContext context: Context): AgentDatabase {
        return Room.databaseBuilder(
            context,
            AgentDatabase::class.java,
            "agent_database"
        )
        .fallbackToDestructiveMigration()  // For dev - use proper migration in prod
        .build()
    }

    @Provides
    fun provideLocalTicketCacheDao(database: AgentDatabase): LocalTicketCacheDao {
        return database.localTicketCacheDao()
    }

    @Provides
    fun provideTirageSessionCacheDao(database: AgentDatabase): TirageSessionCacheDao {
        return database.tirageSessionCacheDao()
    }

    @Provides
    fun providePendingTicketDao(database: AgentDatabase): PendingTicketDao {
        return database.pendingTicketDao()
    }

    // ─── Network & Sync ────────────────────────────────────────────────────────

    @Provides
    @Singleton
    fun provideNetworkMonitor(@ApplicationContext context: Context): NetworkMonitor {
        return NetworkMonitor(context)
    }

    @Provides
    @Singleton
    fun provideGson(): Gson {
        return Gson()
    }

    @Provides
    @Singleton
    fun provideSyncManager(
        pendingTicketDao: PendingTicketDao,
        dynamicRetrofitProvider: DynamicRetrofitProvider,
        networkMonitor: NetworkMonitor,
        gson: Gson,
        agentConfigDataStore: AgentConfigDataStore
    ): SyncManager {
        return SyncManager(pendingTicketDao, dynamicRetrofitProvider, networkMonitor, gson, agentConfigDataStore)
    }
}
