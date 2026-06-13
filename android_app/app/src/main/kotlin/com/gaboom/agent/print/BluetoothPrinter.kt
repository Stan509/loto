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
        context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    }

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        bluetoothManager?.adapter
    }

    private var socket: BluetoothSocket? = null

    /**
     * Vérifie si Bluetooth est disponible et activé
     */
    fun isBluetoothAvailable(): Boolean {
        return bluetoothAdapter?.isEnabled == true
    }

    /**
     * Vérifie les permissions Bluetooth
     */
    fun hasBluetoothPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.BLUETOOTH_CONNECT
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Liste les appareils Bluetooth appairés
     */
    @SuppressLint("MissingPermission")
    fun getPairedDevices(): List<BluetoothDevice> {
        if (!hasBluetoothPermission()) return emptyList()
        return bluetoothAdapter?.bondedDevices?.toList() ?: emptyList()
    }

    /**
     * Filtre les imprimantes parmi les appareils appairés
     * (heuristique basée sur le nom)
     */
    @SuppressLint("MissingPermission")
    fun getPairedPrinters(): List<BluetoothDevice> {
        return getPairedDevices().filter { device ->
            val name = device.name?.lowercase() ?: ""
            name.contains("printer") ||
            name.contains("pos") ||
            name.contains("thermal") ||
            name.contains("print") ||
            name.contains("58") ||
            name.contains("80")
        }
    }

    /**
     * Connecte à une imprimante Bluetooth
     */
    @SuppressLint("MissingPermission")
    suspend fun connect(device: BluetoothDevice): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            // Fermer connexion existante
            disconnect()

            // Créer socket
            socket = device.createRfcommSocketToServiceRecord(SPP_UUID)

            // Connecter
            socket?.connect()

            Result.success(Unit)
        } catch (e: IOException) {
            Result.failure(Exception("Impossible de se connecter à ${device.name}: ${e.message}"))
        } catch (e: SecurityException) {
            Result.failure(Exception("Permission Bluetooth refusée"))
        }
    }

    /**
     * Déconnecte de l'imprimante
     */
    fun disconnect() {
        try {
            socket?.close()
        } catch (e: IOException) {
            // Ignorer
        }
        socket = null
    }

    /**
     * Vérifie si connecté
     */
    fun isConnected(): Boolean {
        return socket?.isConnected == true
    }

    /**
     * Imprime des données brutes ESC/POS
     */
    suspend fun print(data: ByteArray): Result<Unit> = withContext(Dispatchers.IO) {
        val outputStream = socket?.outputStream
            ?: return@withContext Result.failure(Exception("Non connecté à une imprimante"))

        try {
            outputStream.write(data)
            outputStream.flush()
            Result.success(Unit)
        } catch (e: IOException) {
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
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Imprime un ticket complet (télécharge le logo si disponible)
     */
    suspend fun printTicket(printData: com.gaboom.agent.data.model.PrintData): Result<Unit> {
        val logoBitmap = downloadLogoBitmap(printData.borletteLogoUrl)
        val escPosData = EscPosBuilder.buildTicket(printData, logoBitmap)
        return print(escPosData)
    }

    /**
     * Imprime un ticket de test
     */
    suspend fun printTest(): Result<Unit> {
        val testData = EscPosBuilder.buildTestTicket()
        return print(testData)
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
