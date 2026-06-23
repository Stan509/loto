package com.gaboom.agent.print

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import com.gaboom.agent.data.model.PrintData
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter

/**
 * Générateur de commandes ESC/POS pour impression thermique 58mm
 * Compatible avec toutes les imprimantes ESC/POS (Bluetooth/USB)
 */
object EscPosBuilder {

    // Commandes ESC/POS de base
    private val ESC = 0x1B.toByte()
    private val GS = 0x1D.toByte()
    private val LF = 0x0A.toByte()

    // Initialisation
    private val INIT = byteArrayOf(ESC, '@'.code.toByte())

    // Alignement
    private val ALIGN_LEFT = byteArrayOf(ESC, 'a'.code.toByte(), 0)
    private val ALIGN_CENTER = byteArrayOf(ESC, 'a'.code.toByte(), 1)
    private val ALIGN_RIGHT = byteArrayOf(ESC, 'a'.code.toByte(), 2)

    // Styles
    private val BOLD_ON = byteArrayOf(ESC, 'E'.code.toByte(), 1)
    private val BOLD_OFF = byteArrayOf(ESC, 'E'.code.toByte(), 0)
    private val DOUBLE_HEIGHT_ON = byteArrayOf(GS, '!'.code.toByte(), 0x10)
    private val DOUBLE_WIDTH_ON = byteArrayOf(GS, '!'.code.toByte(), 0x20)
    private val DOUBLE_SIZE_ON = byteArrayOf(GS, '!'.code.toByte(), 0x30)
    private val NORMAL_SIZE = byteArrayOf(GS, '!'.code.toByte(), 0x00)
    private val FONT_A = byteArrayOf(ESC, 'M'.code.toByte(), 0)
    private val FONT_B = byteArrayOf(ESC, 'M'.code.toByte(), 1)

    // Coupe papier
    private val CUT_PARTIAL = byteArrayOf(GS, 'V'.code.toByte(), 1)
    private val CUT_FULL = byteArrayOf(GS, 'V'.code.toByte(), 0)

    // Feed
    private val FEED_LINE = byteArrayOf(LF)
    private val FEED_LINES_3 = byteArrayOf(ESC, 'd'.code.toByte(), 3)
    private val FEED_LINES_5 = byteArrayOf(ESC, 'd'.code.toByte(), 5)

    /**
     * Convertit un Bitmap en données raster ESC/POS (GS v 0)
     * Utilisé pour imprimer le logo de la borlette
     */
    private fun buildLogoBytes(bitmap: Bitmap, maxWidth: Int = 360): ByteArray {
        val targetWidth = minOf(bitmap.width, maxWidth)
        val scale = targetWidth.toFloat() / bitmap.width
        val targetHeight = (bitmap.height * scale).toInt().coerceAtLeast(1)

        val scaled = Bitmap.createScaledBitmap(bitmap, targetWidth, targetHeight, true)

        val bytesPerRow = (targetWidth + 7) / 8
        val buffer = mutableListOf<Byte>()

        // GS v 0: raster bit image (normal density)
        buffer.addAll(byteArrayOf(
            GS, 'v'.code.toByte(), '0'.code.toByte(), 0,
            (bytesPerRow and 0xFF).toByte(), ((bytesPerRow shr 8) and 0xFF).toByte(),
            (targetHeight and 0xFF).toByte(), ((targetHeight shr 8) and 0xFF).toByte()
        ).toList())

        for (y in 0 until targetHeight) {
            for (xByte in 0 until bytesPerRow) {
                var byteVal = 0
                for (bit in 0 until 8) {
                    val x = xByte * 8 + bit
                    if (x < targetWidth) {
                        val pixel = scaled.getPixel(x, y)
                        val luminance = (
                            0.299 * Color.red(pixel) +
                            0.587 * Color.green(pixel) +
                            0.114 * Color.blue(pixel)
                        ).toInt()
                        if (luminance < 128) {
                            byteVal = byteVal or (0x80 ushr bit)
                        }
                    }
                }
                buffer.add(byteVal.toByte())
            }
        }
        return buffer.toByteArray()
    }

    /**
     * Génère un QR code comme Bitmap (via ZXing) pour composition côte à côte avec le logo
     */
    private fun generateQrBitmap(content: String, size: Int = 180): Bitmap? {
        return try {
            val hints = mapOf(EncodeHintType.MARGIN to 1)
            val bitMatrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size, hints)
            val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
            for (y in 0 until size) {
                for (x in 0 until size) {
                    bitmap.setPixel(x, y, if (bitMatrix[x, y]) Color.BLACK else Color.WHITE)
                }
            }
            bitmap
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Compose logo (gauche) et QR code (droite) côte à côte dans un seul bitmap 58mm
     */
    private fun combineSideBySide(logo: Bitmap, qr: Bitmap, totalWidth: Int = 360): Bitmap {
        val gap = 8
        val halfWidth = (totalWidth - gap) / 2

        val logoH = (halfWidth.toFloat() / logo.width * logo.height).toInt().coerceAtLeast(1)
        val scaledLogo = Bitmap.createScaledBitmap(logo, halfWidth, logoH, true)

        val qrH = (halfWidth.toFloat() / qr.width * qr.height).toInt().coerceAtLeast(1)
        val scaledQr = Bitmap.createScaledBitmap(qr, halfWidth, qrH, true)

        val totalH = maxOf(logoH, qrH)
        val combined = Bitmap.createBitmap(totalWidth, totalH, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(combined)
        canvas.drawColor(Color.WHITE)

        canvas.drawBitmap(scaledLogo, 0f, ((totalH - logoH) / 2).toFloat(), null)
        canvas.drawBitmap(scaledQr, (halfWidth + gap).toFloat(), ((totalH - qrH) / 2).toFloat(), null)

        return combined
    }

    /**
     * Génère les commandes ESC/POS pour un QR code natif (utilisé sans logo)
     * Compatible avec la plupart des imprimantes thermiques ESC/POS
     */
    private fun buildQrCode(content: String, size: Int = 6): ByteArray {
        val buffer = mutableListOf<Byte>()
        val contentBytes = content.toByteArray(Charsets.UTF_8)
        val contentLen = contentBytes.size + 3
        val pL = (contentLen % 256).toByte()
        val pH = (contentLen / 256).toByte()

        // QR Code: Sélectionner le modèle (Model 2)
        buffer.addAll(byteArrayOf(GS, '('.code.toByte(), 'k'.code.toByte(), 4, 0, 0x31, 0x41, 0x32, 0x00).toList())

        // QR Code: Définir la taille des modules (1-16)
        buffer.addAll(byteArrayOf(GS, '('.code.toByte(), 'k'.code.toByte(), 3, 0, 0x31, 0x43, size.toByte()).toList())

        // QR Code: Définir le niveau de correction d'erreur (L=48, M=49, Q=50, H=51)
        buffer.addAll(byteArrayOf(GS, '('.code.toByte(), 'k'.code.toByte(), 3, 0, 0x31, 0x45, 0x31).toList())

        // QR Code: Stocker les données
        buffer.addAll(byteArrayOf(GS, '('.code.toByte(), 'k'.code.toByte(), pL, pH, 0x31, 0x50, 0x30).toList())
        buffer.addAll(contentBytes.toList())

        // QR Code: Imprimer le code stocké
        buffer.addAll(byteArrayOf(GS, '('.code.toByte(), 'k'.code.toByte(), 3, 0, 0x31, 0x51, 0x30).toList())

        return buffer.toByteArray()
    }

    /**
     * Construit les données binaires ESC/POS pour un ticket
     * @param logoBitmap Logo de la borlette (optionnel) — imprimé au-dessus du QR code
     */
    fun buildTicket(data: PrintData, logoBitmap: Bitmap? = null): ByteArray {
        val buffer = mutableListOf<Byte>()

        // Init et séléction de la police par défaut (Font A)
        buffer.addAll(INIT.toList())
        buffer.addAll(FONT_A.toList())

        // ─── Header Borlette ───────────────────────────────────────────────
        buffer.addAll(ALIGN_CENTER.toList())
        buffer.addAll(DOUBLE_SIZE_ON.toList())
        buffer.addAll(BOLD_ON.toList())
        buffer.addAll(data.borletteName.stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll(NORMAL_SIZE.toList())
        buffer.addAll(BOLD_OFF.toList())

        if (data.borletteSlogan.isNotBlank()) {
            buffer.addAll(data.borletteSlogan.stripAccents().toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
        }

        if (data.borletteTel.isNotBlank()) {
            buffer.addAll("Tel: ${data.borletteTel}".stripAccents().toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
        }

        buffer.add(LF)

        // ─── Logo + QR Code (côte à côte si les deux sont disponibles) ────────────
        buffer.addAll(ALIGN_CENTER.toList())
        if (logoBitmap != null && data.qrCodeUrl.isNotBlank()) {
            val qrBitmap = generateQrBitmap(data.qrCodeUrl)
            if (qrBitmap != null) {
                val combined = combineSideBySide(logoBitmap, qrBitmap)
                buffer.addAll(buildLogoBytes(combined, maxWidth = 360).toList())
                buffer.add(LF)
            } else {
                buffer.addAll(buildLogoBytes(logoBitmap).toList())
                buffer.add(LF)
                buffer.addAll(buildQrCode(data.qrCodeUrl, 5).toList())
                buffer.add(LF)
            }
        } else if (logoBitmap != null) {
            buffer.addAll(buildLogoBytes(logoBitmap).toList())
            buffer.add(LF)
        } else if (data.qrCodeUrl.isNotBlank()) {
            buffer.addAll(buildQrCode(data.qrCodeUrl, 5).toList())
            buffer.add(LF)
        }

        // ─── Ligne séparatrice ─────────────────────────────────────────────
        buffer.addAll("--------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // ─── Info Ticket ───────────────────────────────────────────────────
        buffer.addAll(ALIGN_LEFT.toList())
        buffer.addAll(BOLD_ON.toList())
        buffer.addAll("Ticket: ${data.ticketNumber}".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll(BOLD_OFF.toList())

        buffer.addAll("Date: ${data.date}  ${data.time}".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        buffer.addAll("Agent: ${data.agentName}".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // Tirages
        buffer.addAll("Tirage(s): ${data.tirages.joinToString(", ")}".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // Phase I-A2: Offline watermark
        if (data.isOffline) {
            buffer.add(LF)
            buffer.addAll(ALIGN_CENTER.toList())
            buffer.addAll(BOLD_ON.toList())
            buffer.addAll(DOUBLE_HEIGHT_ON.toList())
            buffer.addAll("*** OFFLINE ***".toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
            buffer.addAll(NORMAL_SIZE.toList())
            buffer.addAll(BOLD_OFF.toList())
            buffer.addAll(ALIGN_LEFT.toList())
            buffer.addAll("A valider en ligne".stripAccents().toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
        }

        buffer.addAll("--------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // ─── Lignes de mise ────────────────────────────────────────────────
        buffer.addAll(BOLD_ON.toList())
        buffer.addAll("JEU     NUMERO    MISE".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll(BOLD_OFF.toList())

        for (line in data.lines) {
            buffer.addAll(line.stripAccents().toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
        }

        buffer.addAll("--------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // ─── Total ─────────────────────────────────────────────────────────
        buffer.addAll(BOLD_ON.toList())
        buffer.addAll(DOUBLE_HEIGHT_ON.toList())
        val totalStr = "TOTAL: ${String.format("%.0f", data.totalMise)} HTG"
        buffer.addAll(totalStr.stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll(NORMAL_SIZE.toList())
        buffer.addAll(BOLD_OFF.toList())

        buffer.addAll("--------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // ─── Mariage Gratuit (si activé) ────────────────────────────────────
        if (data.mariageGratuitActif) {
            buffer.addAll(ALIGN_CENTER.toList())
            buffer.addAll(BOLD_ON.toList())
            buffer.addAll("Mariage Gratuit ${data.mariageGratuitMontant} Gdes".stripAccents().toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
            buffer.addAll(BOLD_OFF.toList())
            buffer.add(LF)
        }

        // ─── Texte de pied de page (Petite police Font B) ──────────────────
        buffer.addAll(FONT_B.toList())
        buffer.addAll(ALIGN_CENTER.toList())
        if (data.ticketFooterText.isNotBlank()) {
            buffer.addAll(data.ticketFooterText.stripAccents().toByteArray(Charsets.UTF_8).toList())
            buffer.add(LF)
            buffer.add(LF)
        }
        buffer.addAll("Gaboom Borlette OS  www.gaboombos.com".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll("------------------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll("Bonne chance".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll("Merci pour votre confiance".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        // Restauration de la police par défaut (Font A)
        buffer.addAll(FONT_A.toList())

        // Feed et coupe
        buffer.addAll(FEED_LINES_5.toList())
        buffer.addAll(CUT_PARTIAL.toList())

        return buffer.toByteArray()
    }

    /**
     * Construit un ticket de test pour vérifier l'imprimante
     */
    fun buildTestTicket(): ByteArray {
        val buffer = mutableListOf<Byte>()

        buffer.addAll(INIT.toList())
        buffer.addAll(FONT_A.toList())
        buffer.addAll(ALIGN_CENTER.toList())

        buffer.addAll(DOUBLE_SIZE_ON.toList())
        buffer.addAll(BOLD_ON.toList())
        buffer.addAll("TEST IMPRESSION".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll(NORMAL_SIZE.toList())
        buffer.addAll(BOLD_OFF.toList())

        buffer.add(LF)
        buffer.addAll("--------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        buffer.addAll(ALIGN_LEFT.toList())
        buffer.addAll("Gaboom Agent".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)
        buffer.addAll("Imprimante OK".stripAccents().toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        buffer.addAll("--------------------------------".toByteArray(Charsets.UTF_8).toList())
        buffer.add(LF)

        buffer.addAll(FEED_LINES_3.toList())
        buffer.addAll(CUT_PARTIAL.toList())

        return buffer.toByteArray()
    }

    /**
     * Supprime les accents et caractères diacritiques d'une chaîne pour la compatibilité d'impression
     */
    private fun String.stripAccents(): String {
        val normalized = java.text.Normalizer.normalize(this, java.text.Normalizer.Form.NFD)
        val pattern = java.util.regex.Pattern.compile("\\p{InCombiningDiacriticalMarks}+")
        return pattern.matcher(normalized).replaceAll("")
            .replace("ç", "c")
            .replace("Ç", "C")
    }
}
