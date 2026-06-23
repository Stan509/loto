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
import android.content.Intent
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.PrintManager
import android.print.pdf.PrintedPdfDocument
import android.widget.Toast
import com.gaboom.agent.util.TicketShareUtil
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
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
     * Connecte à une imprimante Bluetooth par son adresse MAC
     */
    suspend fun connect(address: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (address.isBlank()) {
                return@withContext Result.failure(Exception("Adresse MAC invalide ou vide"))
            }
            val adapter = bluetoothAdapter ?: return@withContext Result.failure(Exception("Bluetooth non disponible"))
            if (!adapter.isEnabled) {
                return@withContext Result.failure(Exception("Bluetooth désactivé"))
            }
            val device = try {
                adapter.getRemoteDevice(address)
            } catch (e: Throwable) {
                return@withContext Result.failure(Exception("Impossible d'obtenir l'appareil pour l'adresse $address: ${e.message}"))
            }
            if (device == null) {
                return@withContext Result.failure(Exception("Appareil null pour l'adresse $address"))
            }
            connect(device)
        } catch (e: Throwable) {
            Result.failure(Exception("Erreur de connexion Bluetooth: ${e.message}"))
        }
    }

    /**
     * Connecte à une imprimante Bluetooth
     */
    fun checkBluetoothPermission(): Boolean {
        return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            try {
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.BLUETOOTH_CONNECT
                ) == PackageManager.PERMISSION_GRANTED
            } catch (e: Throwable) {
                false
            }
        } else {
            true
        }
    }

    @SuppressLint("MissingPermission")
    suspend fun connect(device: BluetoothDevice): Result<Unit> = withContext(Dispatchers.IO) {
        val deviceName = try { device.name } catch (e: Throwable) { null } ?: "Imprimante"
        
        // Vérifier la permission BLUETOOTH_CONNECT sur Android 12+
        if (!checkBluetoothPermission()) {
            return@withContext Result.failure(Exception("Permission Bluetooth requise (BLUETOOTH_CONNECT)"))
        }
        
        try {
            // Fermer connexion existante
            disconnect()

            // Créer socket standard
            socket = device.createRfcommSocketToServiceRecord(SPP_UUID)

            // Annuler la découverte avant la connexion pour éviter les crashs natifs et les timeouts sur les terminaux POS
            try {
                bluetoothAdapter?.cancelDiscovery()
            } catch (e: Throwable) {
                // Ignorer
            }

            // Connecter
            socket?.connect()

            Result.success(Unit)
        } catch (e: Throwable) {
            // Tentative de fallback par réflexion (port 1)
            try {
                disconnect()
                val method = device.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
                socket = method.invoke(device, 1) as? BluetoothSocket
                try { bluetoothAdapter?.cancelDiscovery() } catch (e: Throwable) {}
                socket?.connect()
                Result.success(Unit)
            } catch (fallbackEx: Throwable) {
                // Tentative fallback port 2
                try {
                    disconnect()
                    val method2 = device.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
                    socket = method2.invoke(device, 2) as? BluetoothSocket
                    try { bluetoothAdapter?.cancelDiscovery() } catch (e: Throwable) {}
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
     * Imprime un ticket complet en utilisant l'architecture hybride
     */
    suspend fun printTicket(printData: com.gaboom.agent.data.model.PrintData): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            // Téléchargement préalable du logo (si présent)
            val logoBitmap = TicketShareUtil.downloadLogo(context, printData.borletteLogoUrl)

            // Convertir les données d'impression en TicketShareData pour générer le Bitmap de rendu
            val shareData = TicketShareUtil.fromPrintData(printData, logoBitmap)
            val ticketBitmap = TicketShareUtil.generateTicketImage(context, shareData)

            // ─── Méthode A : Framework d'impression standard d'Android (Print Spooler) ───
            android.util.Log.d("UniversalPrinter", "Tentative d'impression via Android Print Framework (Méthode A)...")
            val systemPrintSuccess = printViaSystem(ticketBitmap, printData.ticketNumber)
            if (systemPrintSuccess) {
                android.util.Log.d("UniversalPrinter", "Méthode A initiée avec succès.")
                return@withContext Result.success(Unit)
            }

            // ─── Méthode B : Fallback ESC/POS (Communication Raw) ───
            android.util.Log.w("UniversalPrinter", "Méthode A indisponible ou en échec. Bascule automatique vers Méthode B (ESC/POS)...")
            val escPosData = EscPosBuilder.buildTicket(printData, logoBitmap)

            // 1. Fallback USB Direct
            android.util.Log.d("UniversalPrinter", "Tentative d'impression brute via USB...")
            if (printViaUsb(escPosData)) {
                android.util.Log.d("UniversalPrinter", "Impression brute USB réussie.")
                return@withContext Result.success(Unit)
            }

            // 2. Fallback Port Série /dev/ttyS* ou /dev/usb/lp*
            android.util.Log.d("UniversalPrinter", "Tentative d'impression brute via Port Série (/dev/ttyS*)...")
            if (printViaSerial(escPosData)) {
                android.util.Log.d("UniversalPrinter", "Impression brute Port Série réussie.")
                return@withContext Result.success(Unit)
            }

            // 3. Fallback Bluetooth
            android.util.Log.d("UniversalPrinter", "Tentative d'impression brute via Bluetooth BluetoothRFCOMM...")
            if (!isConnected()) {
                val connResult = connectToFirstPrinter()
                if (connResult.isFailure) {
                    return@withContext Result.failure(
                        Exception("Tous les canaux d'impression ont échoué. Bluetooth : ${connResult.exceptionOrNull()?.message}")
                    )
                }
            }

            val printResult = print(escPosData)
            if (printResult.isSuccess) {
                android.util.Log.d("UniversalPrinter", "Impression brute Bluetooth réussie.")
                Result.success(Unit)
            } else {
                Result.failure(Exception("Échec de l'impression sur tous les canaux : Bluetooth a échoué."))
            }
        } catch (e: Throwable) {
            android.util.Log.e("UniversalPrinter", "Exception globale lors de l'impression : ${e.message}", e)
            Result.failure(Exception("Erreur d'impression critique : ${e.message}"))
        }
    }

    /**
     * Imprime un ticket de test en utilisant le pipeline hybride
     */
    suspend fun printTest(): Result<Unit> {
        return try {
            val dummyPrintData = com.gaboom.agent.data.model.PrintData(
                borletteName = "GABOOM TEST PRINTER",
                borletteSlogan = "Test de connexion universelle",
                borletteTel = "000-000-0000",
                borletteAdresse = "Port-au-Prince, Haiti",
                agentName = "Test Agent",
                ticketNumber = "TEST-999999",
                date = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date()),
                time = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date()),
                tirages = listOf("FLORIDA MID"),
                lines = listOf("BOULE 12 100 HTG", "MARIAGE 12-34 50 HTG", "LOTO3 123 25 HTG"),
                totalMise = 175.0
            )
            printTicket(dummyPrintData)
        } catch (e: Throwable) {
            Result.failure(Exception("Erreur lors de l'impression de test: ${e.message}"))
        }
    }

    /**
     * Méthode A : Envoi du Bitmap au gestionnaire d'impression système
     * Note: Cette méthode retourne FALSE car le Print Spooler Android n'est pas
     * disponible sur la plupart des terminaux POS (Sunmi, Telpo, etc.).
     * Elle est conservée pour compatibilité avec des imprimantes Wi-Fi/Cloud
     * mais ne doit PAS bloquer le fallback ESC/POS.
     */
    private suspend fun printViaSystem(bitmap: Bitmap, ticketNo: String): Boolean = withContext(Dispatchers.Main) {
        try {
            val printManager = context.getSystemService(Context.PRINT_SERVICE) as? PrintManager ?: return@withContext false
            val jobName = "Ticket_$ticketNo"
            // Sur les terminaux POS sans Print Spooler, on retourne false
            // pour laisser le fallback ESC/POS (Bluetooth/USB/Serial) s'exécuter
            printManager.print(jobName, TicketPrintAdapter(context, bitmap, jobName), null)
            // Retourne false pour toujours passer au fallback ESC/POS sur les terminaux POS
            // Le Print Spooler Android n'est pas le mécanisme d'impression souhaité sur Sunmi/Telpo
            false
        } catch (e: Throwable) {
            android.util.Log.e("UniversalPrinter", "Erreur printViaSystem: ${e.message}", e)
            false
        }
    }

    /**
     * Méthode B.1 : Envoi de données ESC/POS brutes par transfert bulk USB
     */
    private suspend fun printViaUsb(data: ByteArray): Boolean = withContext(Dispatchers.IO) {
        try {
            val usbManager = context.getSystemService(Context.USB_SERVICE) as? UsbManager ?: return@withContext false
            val deviceList = usbManager.deviceList
            var printerDevice: UsbDevice? = null

            for (device in deviceList.values) {
                if (device.deviceClass == UsbConstants.USB_CLASS_PRINTER) {
                    printerDevice = device
                    break
                }
                for (i in 0 until device.interfaceCount) {
                    val usbInterface = device.getInterface(i)
                    if (usbInterface.interfaceClass == UsbConstants.USB_CLASS_PRINTER) {
                        printerDevice = device
                        break
                    }
                }
                if (printerDevice != null) break
            }

            if (printerDevice == null) return@withContext false

            if (!usbManager.hasPermission(printerDevice)) {
                val intent = android.app.PendingIntent.getBroadcast(
                    context, 0, Intent("com.gaboom.agent.USB_PERMISSION"),
                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
                        android.app.PendingIntent.FLAG_IMMUTABLE
                    } else {
                        0
                    }
                )
                usbManager.requestPermission(printerDevice, intent)
                return@withContext false
            }

            var connection: UsbDeviceConnection? = null
            var usbInterface: UsbInterface? = null
            try {
                connection = usbManager.openDevice(printerDevice) ?: return@withContext false
                
                for (i in 0 until printerDevice.interfaceCount) {
                    val iface = printerDevice.getInterface(i)
                    if (iface.interfaceClass == UsbConstants.USB_CLASS_PRINTER) {
                        usbInterface = iface
                        break
                    }
                }
                if (usbInterface == null && printerDevice.interfaceCount > 0) {
                    usbInterface = printerDevice.getInterface(0)
                }
                
                val iface = usbInterface ?: return@withContext false
                if (!connection.claimInterface(iface, true)) return@withContext false

                var endpointOut: UsbEndpoint? = null
                for (e in 0 until iface.endpointCount) {
                    val endpoint = iface.getEndpoint(e)
                    if (endpoint.type == UsbConstants.USB_ENDPOINT_XFER_BULK &&
                        endpoint.direction == UsbConstants.USB_DIR_OUT) {
                        endpointOut = endpoint
                        break
                    }
                }

                val ep = endpointOut ?: return@withContext false
                
                val maxPacketSize = ep.maxPacketSize
                var bytesWritten = 0
                while (bytesWritten < data.size) {
                    val length = minOf(maxPacketSize, data.size - bytesWritten)
                    val packet = data.copyOfRange(bytesWritten, bytesWritten + length)
                    val result = connection.bulkTransfer(ep, packet, packet.size, 5000)
                    if (result < 0) {
                        return@withContext false
                    }
                    bytesWritten += result
                }
                true
            } finally {
                try {
                    usbInterface?.let { connection?.releaseInterface(it) }
                    connection?.close()
                } catch (_: Throwable) {}
            }
        } catch (e: Throwable) {
            android.util.Log.e("UniversalPrinter", "Erreur printViaUsb: ${e.message}", e)
            false
        }
    }

    /**
     * Méthode B.2 : Écriture directe des octets ESC/POS vers les ports série POS /dev/ttyS* /dev/usb/lp*
     */
    private suspend fun printViaSerial(data: ByteArray): Boolean = withContext(Dispatchers.IO) {
        val serialPaths = arrayOf(
            "/dev/ttyS0", "/dev/ttyS1", "/dev/ttyS2", "/dev/ttyS3", "/dev/ttyS4",
            "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/usb/lp0", "/dev/usb/lp1"
        )
        for (path in serialPaths) {
            try {
                val file = File(path)
                if (file.exists() && file.canWrite()) {
                    FileOutputStream(file).use { out ->
                        out.write(data)
                        out.flush()
                    }
                    android.util.Log.d("UniversalPrinter", "Impression série réussie sur : $path")
                    return@withContext true
                }
            } catch (e: Throwable) {
                android.util.Log.w("UniversalPrinter", "Impossible d'écrire sur le port série $path: ${e.message}")
            }
        }
        false
    }
}

/**
 * Adapter personnalisé pour le service de Spooler d'impression Android
 */
class TicketPrintAdapter(
    private val context: Context,
    private val bitmap: Bitmap,
    private val jobName: String
) : PrintDocumentAdapter() {

    private var pdfDocument: PrintedPdfDocument? = null

    override fun onLayout(
        oldAttributes: PrintAttributes?,
        newAttributes: PrintAttributes,
        cancellationSignal: CancellationSignal?,
        callback: LayoutResultCallback,
        extras: Bundle?
    ) {
        if (cancellationSignal?.isCanceled == true) {
            callback.onLayoutCancelled()
            return
        }

        pdfDocument = PrintedPdfDocument(context, newAttributes)

        val info = PrintDocumentInfo.Builder(jobName)
            .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
            .setPageCount(1)
            .build()

        callback.onLayoutFinished(info, true)
    }

    override fun onWrite(
        pages: Array<out PageRange>?,
        destination: ParcelFileDescriptor,
        cancellationSignal: CancellationSignal?,
        callback: WriteResultCallback
    ) {
        val pdf = pdfDocument ?: return
        val page = pdf.startPage(0)

        if (cancellationSignal?.isCanceled == true) {
            callback.onWriteCancelled()
            pdf.close()
            pdfDocument = null
            return
        }

        val canvas = page.canvas
        val pageWidth = canvas.width
        
        val scale = pageWidth.toFloat() / bitmap.width.toFloat()
        val scaledWidth = pageWidth.toFloat()
        val scaledHeight = bitmap.height.toFloat() * scale
        
        val srcRect = android.graphics.Rect(0, 0, bitmap.width, bitmap.height)
        val dstRect = android.graphics.RectF(0f, 0f, scaledWidth, scaledHeight)
        
        canvas.drawBitmap(bitmap, srcRect, dstRect, null)
        pdf.finishPage(page)

        try {
            pdf.writeTo(FileOutputStream(destination.fileDescriptor))
            callback.onWriteFinished(arrayOf(PageRange.ALL_PAGES))
        } catch (e: IOException) {
            callback.onWriteFailed(e.message)
        } finally {
            pdf.close()
            pdfDocument = null
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
