package com.gaboom.agent.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gaboom.agent.BuildConfig
import com.gaboom.agent.data.api.DynamicRetrofitProvider
import com.gaboom.agent.data.api.HealthApiService
import com.gaboom.agent.data.config.AppConfigDataStore
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

import android.bluetooth.BluetoothDevice
import com.gaboom.agent.print.BluetoothPrinter

data class SettingsUiState(
    val baseUrl: String = "",
    val isLoading: Boolean = false,
    val isTesting: Boolean = false,
    val testResult: TestResult? = null,
    val saveSuccess: Boolean = false,
    val errorMessage: String? = null,
    val appVersion: String = "",
    val appVersionCode: Int = 0,
    val isCustomUrl: Boolean = false,
    val themeMode: String = AppConfigDataStore.THEME_DEFAULT,
    
    // Printer State
    val printers: List<BluetoothDevice> = emptyList(),
    val isConnected: Boolean = false,
    val connectedDeviceName: String? = null,
    val isConnecting: Boolean = false,
    val printerError: String? = null
)

sealed class TestResult {
    data class Success(val serverTime: String?, val version: String?) : TestResult()
    data class Error(val message: String) : TestResult()
}

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val appConfigDataStore: AppConfigDataStore,
    private val dynamicRetrofitProvider: DynamicRetrofitProvider,
    private val printer: BluetoothPrinter
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        loadSettings()
        refreshPrinters()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            val currentUrl = appConfigDataStore.baseUrlFlow.first()
            val isCustom = appConfigDataStore.hasCustomBaseUrl()
            val theme = appConfigDataStore.themeModeFlow.first()
            
            _uiState.value = _uiState.value.copy(
                baseUrl = currentUrl,
                isCustomUrl = isCustom,
                appVersion = BuildConfig.VERSION_NAME,
                appVersionCode = BuildConfig.VERSION_CODE,
                themeMode = theme
            )
        }
    }
    
    fun setThemeMode(mode: String) {
        viewModelScope.launch {
            appConfigDataStore.setThemeMode(mode)
            _uiState.value = _uiState.value.copy(themeMode = mode)
        }
    }

    fun updateBaseUrl(url: String) {
        _uiState.value = _uiState.value.copy(
            baseUrl = url,
            testResult = null,
            saveSuccess = false,
            errorMessage = null
        )
    }

    fun testConnection() {
        val url = _uiState.value.baseUrl.trim()
        
        if (!isValidUrl(url)) {
            _uiState.value = _uiState.value.copy(
                testResult = TestResult.Error("URL invalide. Doit commencer par http:// ou https://"),
                errorMessage = "URL invalide"
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isTesting = true, testResult = null)
            
            try {
                // Create temporary Retrofit for testing
                val testRetrofit = dynamicRetrofitProvider.createTestRetrofit(url)
                val healthService = testRetrofit.create(HealthApiService::class.java)
                
                val response = healthService.checkHealth()
                
                if (response.isSuccessful && response.body() != null) {
                    val health = response.body()!!
                    _uiState.value = _uiState.value.copy(
                        isTesting = false,
                        testResult = TestResult.Success(
                            serverTime = health.serverTime,
                            version = health.version
                        )
                    )
                } else {
                    val errorMsg = when (response.code()) {
                        404 -> "Endpoint non trouvé (404)"
                        401, 403 -> "Erreur d'authentification (${response.code()})"
                        500 -> "Erreur serveur (500)"
                        else -> "Erreur HTTP ${response.code()}"
                    }
                    _uiState.value = _uiState.value.copy(
                        isTesting = false,
                        testResult = TestResult.Error(errorMsg)
                    )
                }
            } catch (e: java.net.SocketTimeoutException) {
                _uiState.value = _uiState.value.copy(
                    isTesting = false,
                    testResult = TestResult.Error("Timeout - serveur injoignable")
                )
            } catch (e: java.net.UnknownHostException) {
                _uiState.value = _uiState.value.copy(
                    isTesting = false,
                    testResult = TestResult.Error("Hôte inconnu - vérifiez l'adresse")
                )
            } catch (e: java.net.ConnectException) {
                _uiState.value = _uiState.value.copy(
                    isTesting = false,
                    testResult = TestResult.Error("Connexion refusée - serveur arrêté?")
                )
            } catch (e: javax.net.ssl.SSLException) {
                _uiState.value = _uiState.value.copy(
                    isTesting = false,
                    testResult = TestResult.Error("Erreur SSL - certificat invalide")
                )
            } catch (e: retrofit2.HttpException) {
                _uiState.value = _uiState.value.copy(
                    isTesting = false,
                    testResult = TestResult.Error("Erreur HTTP: ${e.code()} - ${e.message}")
                )
            } catch (e: Exception) {
                e.printStackTrace()
                _uiState.value = _uiState.value.copy(
                    isTesting = false,
                    testResult = TestResult.Error("Erreur: ${e.message ?: "inconnue"}")
                )
            }
        }
    }

    fun saveSettings() {
        val url = _uiState.value.baseUrl.trim()
        
        if (!isValidUrl(url)) {
            _uiState.value = _uiState.value.copy(
                errorMessage = "URL invalide. Doit commencer par http:// ou https://"
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            
            try {
                appConfigDataStore.setBaseUrl(url)
                // Skip rebuildRetrofit to avoid crashes - will be rebuilt on next app launch
                
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    saveSuccess = true,
                    isCustomUrl = true,
                    errorMessage = null
                )
            } catch (e: Exception) {
                e.printStackTrace()
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Erreur lors de la sauvegarde: ${e.message ?: "inconnue"}"
                )
            }
        }
    }

    fun resetToDefault() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            
            try {
                appConfigDataStore.resetToDefault()
                val defaultUrl = AppConfigDataStore.DEFAULT_BASE_URL
                dynamicRetrofitProvider.rebuildRetrofit(defaultUrl)
                
                _uiState.value = _uiState.value.copy(
                    baseUrl = defaultUrl,
                    isLoading = false,
                    isCustomUrl = false,
                    saveSuccess = true,
                    testResult = null,
                    errorMessage = null
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Erreur lors du reset: ${e.message}"
                )
            }
        }
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(
            saveSuccess = false,
            errorMessage = null
        )
    }

    // ─── Printer Management ──────────────────────────────────────────────────

    fun refreshPrinters() {
        viewModelScope.launch {
            if (printer.hasBluetoothPermission()) {
                val list = printer.getPairedPrinters()
                _uiState.value = _uiState.value.copy(
                    printers = list,
                    isConnected = printer.isConnected(),
                    connectedDeviceName = if (printer.isConnected()) printer.getPairedPrinters().firstOrNull()?.name else null,
                    printerError = null
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    printerError = "Permission Bluetooth requise pour scanner"
                )
            }
        }
    }

    fun connectPrinter(device: BluetoothDevice) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isConnecting = true, printerError = null)
            val result = printer.connect(device)
            if (result.isSuccess) {
                _uiState.value = _uiState.value.copy(
                    isConnecting = false,
                    isConnected = true,
                    connectedDeviceName = device.name
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isConnecting = false,
                    isConnected = false,
                    printerError = result.exceptionOrNull()?.message ?: "Erreur de connexion"
                )
            }
        }
    }

    fun disconnectPrinter() {
        printer.disconnect()
        _uiState.value = _uiState.value.copy(
            isConnected = false,
            connectedDeviceName = null,
            printerError = null
        )
    }

    fun printTest() {
        viewModelScope.launch {
            val result = printer.printTest()
            if (result.isFailure) {
                _uiState.value = _uiState.value.copy(
                    printerError = result.exceptionOrNull()?.message ?: "Échec de l'impression test"
                )
            }
        }
    }

    private fun isValidUrl(url: String): Boolean {
        return url.startsWith("http://") || url.startsWith("https://")
    }
}
