package com.gaboom.agent.print

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/**
 * Service d'impression Bluetooth universelle ESC/POS
 * Compatible avec toutes les imprimantes thermiques Bluetooth
 */
class BluetoothPrinter(private val context: Context) {

    companion object {
        // UUID standard pour Serial Port Profile (SPP)
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }

    private val bluetoothManager: BluetoothManager? by lazy {
        try {
            context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
        } catch (e: Throwable) {
            null
        }
    }

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        try {
            bluetoothManager?.adapter
        } catch (e: Throwable) {
            null
        }
    }

    private var socket: BluetoothSocket? = null

    /**
     * Vérifie si Bluetooth est disponible et activé
     */
    fun isBluetoothAvailable(): Boolean {
        return try {
            bluetoothAdapter?.isEnabled == true
        } catch (e: Throwable) {
            false
        }
    }

    /**
     * Vérifie les permissions Bluetooth
     */
    fun hasBluetoothPermission(): Boolean {
        return try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.BLUETOOTH_CONNECT
                ) == PackageManager.PERMISSION_GRANTED
            } else {
                true
            }
        } catch (e: Throwable) {
            false
        }
    }

    /**
     * Liste les appareils Bluetooth appairés
     */
    @SuppressLint("MissingPermission")
    fun getPairedDevices(): List<BluetoothDevice> {
        if (!hasBluetoothPermission()) return emptyList()
        return try {
            bluetoothAdapter?.bondedDevices?.toList() ?: emptyList()
        } catch (e: Throwable) {
            emptyList()
        }
    }

    /**
     * Filtre les imprimantes parmi les appareils appairés
     * (heuristique basée sur le nom, mais retourne TOUS les appareils si le filtre est vide)
     */
    @SuppressLint("MissingPermission")
    fun getPairedPrinters(): List<BluetoothDevice> {
        return try {
            val allDevices = getPairedDevices()
            val filtered = allDevices.filter { device ->
                val name = try { device.name } catch (e: Throwable) { null }?.lowercase() ?: ""
                name.contains("printer") ||
                name.contains("pos") ||
                name.contains("thermal") ||
                name.contains("print") ||
                name.contains("58") ||
                name.contains("80") ||
                name.contains("sunmi") ||
                name.contains("telpo") ||
                name.contains("imin") ||
                name.contains("bt") ||
                name.contains("receipt") ||
                name.contains("label") ||
                name.contains("ts-") ||
                name.contains("mtp-") ||
                name.contains("rpp") ||
                name.contains("spp") ||
                name.contains("zj-") ||
                name.contains("inner") ||
                name.contains("gprinter") ||
                name.contains("xprinter") ||
                name.contains("star") ||
                name.contains("epson")
            }
            // Si le filtre ne trouve rien, retourner tous les appareils pour permettre à
            // l'utilisateur de choisir manuellement
            filtered.ifEmpty { allDevices }
        } catch (e: Throwable) {
            emptyList()
        }
    }

    /**
     * Connecte à une imprimante Bluetooth
     */
    @SuppressLint("MissingPermission")
    suspend fun connect(device: BluetoothDevice): Result<Unit> = withContext(Dispatchers.IO) {
        val deviceName = try { device.name } catch (e: Throwable) { null } ?: "Imprimante"
        try {
            // Fermer connexion existante
            disconnect()

            // Annuler la découverte Bluetooth en cours (obligatoire avant connect())
            try {
                bluetoothAdapter?.cancelDiscovery()
            } catch (_: Throwable) {}

            // Créer socket standard
            socket = device.createRfcommSocketToServiceRecord(SPP_UUID)

            // Connecter
            socket?.connect()

            Result.success(Unit)
        } catch (e: Throwable) {
            // Tentative de fallback par réflexion (port 1)
            try {
                disconnect()
                try {
                    bluetoothAdapter?.cancelDiscovery()
                } catch (_: Throwable) {}
                val method = device.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
                socket = method.invoke(device, 1) as? BluetoothSocket
                socket?.connect()
                Result.success(Unit)
            } catch (fallbackEx: Throwable) {
                // Tentative fallback port 2
                try {
                    disconnect()
                    val method2 = device.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
                    socket = method2.invoke(device, 2) as? BluetoothSocket
                    socket?.connect()
                    Result.success(Unit)
                } catch (ex3: Throwable) {
                    val errorMsg = ex3.message ?: fallbackEx.message ?: e.message ?: "Échec de connexion"
                    Result.failure(Exception("Impossible de se connecter à $deviceName: $errorMsg"))
                }
            }
        }
    }

    /**
     * Déconnecte de l'imprimante
     */
    fun disconnect() {
        try {
            socket?.close()
        } catch (e: Throwable) {
            // Ignorer
        }
        socket = null
    }

    /**
     * Vérifie si connecté
     */
    fun isConnected(): Boolean {
        return try {
            socket?.isConnected == true
        } catch (e: Throwable) {
            false
        }
    }

    /**
     * Imprime des données brutes ESC/POS
     */
    suspend fun print(data: ByteArray): Result<Unit> = withContext(Dispatchers.IO) {
        val outputStream = try { socket?.outputStream } catch (e: Throwable) { null }
            ?: return@withContext Result.failure(Exception("Non connecté à une imprimante"))

        try {
            outputStream.write(data)
            outputStream.flush()
            Result.success(Unit)
        } catch (e: Throwable) {
            Result.failure(Exception("Erreur d'impression: ${e.message}"))
        }
    }

    /**
     * Télécharge un logo depuis une URL HTTP (timeout 5s, silencieux si erreur)
     */
    private suspend fun downloadLogoBitmap(url: String): Bitmap? = withContext(Dispatchers.IO) {
        if (url.isBlank()) return@withContext null
        try {
            val connection = URL(url).openConnection() as HttpURLConnection
            connection.connectTimeout = 5_000
            connection.readTimeout = 5_000
            connection.doInput = true
            connection.connect()
            val bitmap = BitmapFactory.decodeStream(connection.inputStream)
            connection.disconnect()
            bitmap
        } catch (_: Throwable) {
            null
        }
    }

    /**
     * Tente de se connecter automatiquement à la première imprimante Bluetooth appairée
     */
    @SuppressLint("MissingPermission")
    suspend fun connectToFirstPrinter(): Result<Unit> {
        return try {
            val printers = getPairedPrinters()
            if (printers.isEmpty()) {
                return Result.failure(Exception("Aucune imprimante Bluetooth appairée trouvée dans l'appareil"))
            }
            var lastError: Exception? = null
            for (device in printers) {
                val result = connect(device)
                if (result.isSuccess) {
                    return Result.success(Unit)
                } else {
                    lastError = result.exceptionOrNull() as? Exception
                }
            }
            Result.failure(lastError ?: Exception("Échec de la connexion à l'imprimante"))
        } catch (e: Throwable) {
            Result.failure(Exception("Erreur lors de la connexion automatique: ${e.message}"))
        }
    }

    /**
     * Imprime un ticket complet (télécharge le logo si disponible)
     */
    suspend fun printTicket(printData: com.gaboom.agent.data.model.PrintData): Result<Unit> {
        return try {
            if (!isConnected()) {
                val connResult = connectToFirstPrinter()
                if (connResult.isFailure) {
                    return connResult
                }
            }
            val logoBitmap = downloadLogoBitmap(printData.borletteLogoUrl)
            val escPosData = EscPosBuilder.buildTicket(printData, logoBitmap)
            print(escPosData)
        } catch (e: Throwable) {
            Result.failure(Exception("Erreur d'impression: ${e.message}"))
        }
    }

    /**
     * Imprime un ticket de test
     */
    suspend fun printTest(): Result<Unit> {
        return try {
            if (!isConnected()) {
                val connResult = connectToFirstPrinter()
                if (connResult.isFailure) {
                    return connResult
                }
            }
            val testData = EscPosBuilder.buildTestTicket()
            print(testData)
        } catch (e: Throwable) {
            Result.failure(Exception("Erreur d'impression test: ${e.message}"))
        }
    }
}

/**
 * État de l'imprimante
 */
sealed class PrinterState {
    object Disconnected : PrinterState()
    object Connecting : PrinterState()
    data class Connected(val deviceName: String) : PrinterState()
    data class Error(val message: String) : PrinterState()
}
