package com.gaboom.agent.util

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.net.Uri
import androidx.core.content.FileProvider
import coil.ImageLoader
import coil.request.ImageRequest
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Utilitaire pour partager des tickets via différents formats (texte, image, PDF)
 */
object TicketShareUtil {

    data class TicketShareData(
        val ticketNo: String,
        val tirageNom: String,
        val date: String,
        val lines: List<TicketLineData>,
        val totalMise: Double,
        val totalGainDu: Double = 0.0,
        val isWinner: Boolean = false,
        val borletteName: String = "",
        val borletteSlogan: String = "",
        val borletteTel: String = "",
        val borletteAdresse: String = "",
        val agentName: String = "",
        val qrCode: String? = null,
        val logoBitmap: Bitmap? = null,
        val ticketFooterText: String = "",
        val mariageGratuitActif: Boolean = false,
        val mariageGratuitMontant: String = "0"
    )

    data class TicketLineData(
        val jeu: String,
        val valeur: String,
        val mise: Double,
        val option: String? = null,
        val isWinner: Boolean = false,
        val gainDu: Double = 0.0
    )

    /**
     * Génère le texte formaté du ticket pour partage SMS - format fiche simple sans logo/QR
     */
    fun generateTicketText(data: TicketShareData): String {
        val sb = StringBuilder()
        
        // Header simple
        sb.appendLine("================================")
        if (data.borletteName.isNotBlank()) {
            sb.appendLine("    ${data.borletteName.uppercase()}")
        }
        if (data.borletteSlogan.isNotBlank()) {
            sb.appendLine("    ${data.borletteSlogan}")
        }
        if (data.borletteTel.isNotBlank()) {
            sb.appendLine("    Tel: ${data.borletteTel}")
        }
        sb.appendLine("================================")
        sb.appendLine()
        
        // Ticket info
        sb.appendLine("Ticket: #${data.ticketNo}")
        sb.appendLine("Date: ${data.date}")
        sb.appendLine("Tirage: ${data.tirageNom}")
        if (data.agentName.isNotBlank()) {
            sb.appendLine("Agent: ${data.agentName}")
        }
        sb.appendLine()
        sb.appendLine("--------------------------------")
        sb.appendLine("JEU      NUMERO    MISE")
        sb.appendLine("--------------------------------")
        
        // Lines - format tableau
        data.lines.forEach { line ->
            val jeuDisplay = if (line.option != null) "${line.jeu.uppercase()}-${line.option}" else line.jeu.uppercase()
            val winMark = if (line.isWinner) " *" else ""
            sb.appendLine(String.format("%-8s %-9s %5d$winMark", jeuDisplay, line.valeur, line.mise.toInt()))
            if (line.isWinner && line.gainDu > 0) {
                sb.appendLine("         Gain: ${line.gainDu.toInt()} HTG")
            }
        }
        
        sb.appendLine("--------------------------------")
        sb.appendLine("TOTAL: ${data.totalMise.toInt()} HTG")
        
        if (data.isWinner && data.totalGainDu > 0) {
            sb.appendLine("GAIN DU: ${data.totalGainDu.toInt()} HTG")
        }
        
        sb.appendLine("================================")
        if (data.mariageGratuitActif) {
            sb.appendLine("Mariage Gratuit ${data.mariageGratuitMontant} Gdes")
            sb.appendLine("--------------------------------")
        }
        if (data.ticketFooterText.isNotBlank()) {
            sb.appendLine(data.ticketFooterText)
            sb.appendLine()
        }
        sb.appendLine("Gaboom Borlette OS  www.gaboombos.com")
        sb.appendLine("--------------------------------")
        sb.appendLine("Bonne chance")
        sb.appendLine("Merci pour votre confiance")
        sb.appendLine("================================")
        
        return sb.toString()
    }

    /**
     * Génère une image du ticket identique au preview d'impression
     */
    fun generateTicketImage(context: Context, data: TicketShareData): Bitmap {
        val width = 420
        val padding = 24
        val qrCodeSize = 100
        
        // Paints
        val paintTitle = Paint().apply {
            color = Color.BLACK
            textSize = 22f
            typeface = Typeface.DEFAULT_BOLD
            isAntiAlias = true
            textAlign = Paint.Align.CENTER
        }
        
        val paintNormal = Paint().apply {
            color = Color.BLACK
            textSize = 16f
            isAntiAlias = true
        }
        
        val paintNormalCenter = Paint().apply {
            color = Color.BLACK
            textSize = 16f
            isAntiAlias = true
            textAlign = Paint.Align.CENTER
        }
        
        val paintSmall = Paint().apply {
            color = Color.GRAY
            textSize = 14f
            isAntiAlias = true
            textAlign = Paint.Align.CENTER
        }
        
        val paintMono = Paint().apply {
            color = Color.BLACK
            textSize = 15f
            typeface = Typeface.MONOSPACE
            isAntiAlias = true
        }
        
        val paintMonoBold = Paint().apply {
            color = Color.BLACK
            textSize = 15f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
            isAntiAlias = true
        }
        
        val paintBold = Paint().apply {
            color = Color.BLACK
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
            isAntiAlias = true
        }
        
        val paintWinner = Paint().apply {
            color = Color.rgb(16, 185, 129)
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
            isAntiAlias = true
        }
        
        val paintSeparator = Paint().apply {
            color = Color.DKGRAY
            textSize = 14f
            typeface = Typeface.MONOSPACE
            isAntiAlias = true
            textAlign = Paint.Align.CENTER
        }
        
        // Calculate height
        val logoSize = 70
        var calcHeight = padding * 2
        if (data.logoBitmap != null) calcHeight += logoSize + 10 // logo
        calcHeight += 30 // borlette name
        if (data.borletteSlogan.isNotBlank()) calcHeight += 20
        if (data.borletteAdresse.isNotBlank()) calcHeight += 18
        if (data.borletteTel.isNotBlank()) calcHeight += 20
        calcHeight += 20 // space
        if (!data.qrCode.isNullOrBlank()) calcHeight += qrCodeSize + 30 // QR + label
        calcHeight += 25 // separator
        calcHeight += 25 * 4 // ticket info (4 lines)
        calcHeight += 25 // separator
        calcHeight += 22 // header ligne
        calcHeight += 22 * data.lines.size // lines
        calcHeight += 22 * data.lines.count { it.isWinner && it.gainDu > 0 } // gains
        calcHeight += 25 // separator
        calcHeight += 25 // total
        if (data.isWinner && data.totalGainDu > 0) calcHeight += 25
        calcHeight += 25 // separator
        if (data.mariageGratuitActif) calcHeight += 44 // mariage gratuit + separator
        // Footer text (estimate word-wrapped lines)
        if (data.ticketFooterText.isNotBlank()) {
            val estimatedLines = (data.ticketFooterText.length / 35) + 1
            calcHeight += estimatedLines * 18
        }
        calcHeight += 76 // brand info + separator + bonne chance + merci
        
        val height = calcHeight
        val centerX = width / 2f
        
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        
        // Background couleur crème comme le preview
        canvas.drawColor(Color.rgb(255, 251, 230))
        
        var y = padding.toFloat()
        
        // ═══════════════════════════════════════════════════════════
        // LOGO
        // ═══════════════════════════════════════════════════════════
        
        if (data.logoBitmap != null) {
            val scaledLogo = Bitmap.createScaledBitmap(data.logoBitmap, logoSize, logoSize, true)
            val logoX = (width - logoSize) / 2f
            canvas.drawBitmap(scaledLogo, logoX, y, null)
            y += logoSize + 10
        }
        
        // ═══════════════════════════════════════════════════════════
        // HEADER - Borlette Info
        // ═══════════════════════════════════════════════════════════
        
        // Nom de la borlette
        val borletteName = data.borletteName.ifBlank { "GABOOM BORLETTE" }
        canvas.drawText(borletteName, centerX, y + 22, paintTitle)
        y += 30
        
        // Slogan
        if (data.borletteSlogan.isNotBlank()) {
            canvas.drawText(data.borletteSlogan, centerX, y + 14, paintSmall)
            y += 20
        }
        
        // Adresse
        if (data.borletteAdresse.isNotBlank()) {
            canvas.drawText(data.borletteAdresse, centerX, y + 12, paintSmall)
            y += 18
        }
        
        // Téléphone
        if (data.borletteTel.isNotBlank()) {
            canvas.drawText("Tel: ${data.borletteTel}", centerX, y + 14, paintNormalCenter)
            y += 20
        }
        
        y += 10
        
        // ═══════════════════════════════════════════════════════════
        // QR CODE
        // ═══════════════════════════════════════════════════════════
        
        if (!data.qrCode.isNullOrBlank()) {
            val qrBitmap = QrCodeGenerator.generateQrCode(data.qrCode, qrCodeSize)
            if (qrBitmap != null) {
                val qrX = (width - qrCodeSize) / 2f
                canvas.drawBitmap(qrBitmap, qrX, y, null)
                y += qrCodeSize + 5
                canvas.drawText("QR Code Groupe", centerX, y + 12, paintSmall)
                y += 20
            }
        }
        
        y += 5
        
        // Separator
        canvas.drawText("--------------------------------", centerX, y + 12, paintSeparator)
        y += 22
        
        // ═══════════════════════════════════════════════════════════
        // TICKET INFO
        // ═══════════════════════════════════════════════════════════
        
        canvas.drawText("Ticket: #${data.ticketNo}", padding.toFloat(), y + 16, paintBold)
        y += 22
        canvas.drawText("Date: ${data.date}", padding.toFloat(), y + 16, paintNormal)
        y += 22
        if (data.agentName.isNotBlank()) {
            canvas.drawText("Agent: ${data.agentName}", padding.toFloat(), y + 16, paintNormal)
            y += 22
        }
        canvas.drawText("Tirage(s): ${data.tirageNom}", padding.toFloat(), y + 16, paintNormal)
        y += 22
        
        // Separator
        canvas.drawText("--------------------------------", centerX, y + 12, paintSeparator)
        y += 22
        
        // ═══════════════════════════════════════════════════════════
        // LINES
        // ═══════════════════════════════════════════════════════════
        
        // Header
        canvas.drawText("JEU      NUMERO    MISE", padding.toFloat(), y + 15, paintMonoBold)
        y += 22
        
        // Lines
        data.lines.forEach { line ->
            val jeuDisplay = if (line.option != null) "${line.jeu.uppercase()}-${line.option}" else line.jeu.uppercase()
            val lineText = String.format("%-8s %-9s %6.0f", jeuDisplay, line.valeur, line.mise)
            val paint = if (line.isWinner) paintWinner else paintMono
            canvas.drawText(lineText, padding.toFloat(), y + 15, paint)
            y += 22
            
            if (line.isWinner && line.gainDu > 0) {
                canvas.drawText("         Gain: ${line.gainDu.toInt()} HTG", padding.toFloat(), y + 15, paintWinner)
                y += 22
            }
        }
        
        // Separator
        canvas.drawText("--------------------------------", centerX, y + 12, paintSeparator)
        y += 22
        
        // ═══════════════════════════════════════════════════════════
        // TOTAL
        // ═══════════════════════════════════════════════════════════
        
        canvas.drawText("TOTAL: ${data.totalMise.toInt()} HTG", padding.toFloat(), y + 18, paintBold)
        y += 25
        
        if (data.isWinner && data.totalGainDu > 0) {
            canvas.drawText("GAIN DÛ: ${data.totalGainDu.toInt()} HTG", padding.toFloat(), y + 18, paintWinner)
            y += 25
        }
        
        // Separator
        canvas.drawText("--------------------------------", centerX, y + 12, paintSeparator)
        y += 22
        
        // ═══════════════════════════════════════════════════════════
        // MARIAGE GRATUIT
        // ═══════════════════════════════════════════════════════════
        
        if (data.mariageGratuitActif) {
            canvas.drawText("Mariage Gratuit ${data.mariageGratuitMontant} Gdes", centerX, y + 16, paintBold)
            y += 22
            canvas.drawText("--------------------------------", centerX, y + 12, paintSeparator)
            y += 22
        }
        
        // ═══════════════════════════════════════════════════════════
        // FOOTER
        // ═══════════════════════════════════════════════════════════
        
        if (data.ticketFooterText.isNotBlank()) {
            // Word-wrap footer text for narrow ticket width
            val footerWords = data.ticketFooterText.split(" ")
            val footerLines = mutableListOf<String>()
            var currentLine = ""
            for (word in footerWords) {
                val test = if (currentLine.isEmpty()) word else "$currentLine $word"
                if (paintSmall.measureText(test) > (width - padding * 2)) {
                    if (currentLine.isNotEmpty()) footerLines.add(currentLine)
                    currentLine = word
                } else {
                    currentLine = test
                }
            }
            if (currentLine.isNotEmpty()) footerLines.add(currentLine)
            for (fl in footerLines) {
                canvas.drawText(fl, centerX, y + 14, paintSmall)
                y += 18
            }
            y += 8
        }
        
        canvas.drawText("Gaboom Borlette OS  www.gaboombos.com", centerX, y + 14, paintSmall)
        y += 18
        canvas.drawText("--------------------------------", centerX, y + 14, paintSeparator)
        y += 18
        canvas.drawText("Bonne chance", centerX, y + 14, paintNormalCenter)
        y += 18
        canvas.drawText("Merci pour votre confiance", centerX, y + 14, paintNormalCenter)
        
        return bitmap
    }

    /**
     * Télécharge le logo de la borlette depuis une URL
     */
    suspend fun downloadLogo(context: Context, logoUrl: String): Bitmap? {
        return try {
            val loader = ImageLoader(context)
            val request = ImageRequest.Builder(context)
                .data(logoUrl)
                .allowHardware(false)
                .build()
            val result = loader.execute(request)
            (result.drawable as? android.graphics.drawable.BitmapDrawable)?.bitmap
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Partage un bitmap existant (ne le regénère pas)
     */
    fun shareBitmapAsImage(context: Context, bitmap: Bitmap, ticketNo: String) {
        val cachePath = File(context.cacheDir, "shared_tickets")
        cachePath.mkdirs()
        val file = File(cachePath, "ticket_${ticketNo.replace("-", "_")}.png")

        FileOutputStream(file).use { out ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
        }

        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )

        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Partager le ticket"))
    }

    /**
     * Partage le ticket en texte via Intent
     */
    fun shareAsText(context: Context, data: TicketShareData) {
        val text = generateTicketText(data)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
            putExtra(Intent.EXTRA_SUBJECT, "Ticket ${data.ticketNo}")
        }
        context.startActivity(Intent.createChooser(intent, "Partager le ticket"))
    }

    /**
     * Partage le ticket en image via Intent
     */
    fun shareAsImage(context: Context, data: TicketShareData) {
        val bitmap = generateTicketImage(context, data)
        
        // Save bitmap to cache
        val cachePath = File(context.cacheDir, "shared_tickets")
        cachePath.mkdirs()
        val file = File(cachePath, "ticket_${data.ticketNo.replace("-", "_")}.png")
        
        FileOutputStream(file).use { out ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
        }
        
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )
        
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Partager le ticket"))
    }

    /**
     * Sauvegarde le ticket en PDF et lance le partage
     */
    fun saveAsPdf(context: Context, bitmap: Bitmap, ticketNo: String) {
        val pdfDocument = android.graphics.pdf.PdfDocument()
        val pageInfo = android.graphics.pdf.PdfDocument.PageInfo.Builder(bitmap.width, bitmap.height, 1).create()
        val page = pdfDocument.startPage(pageInfo)
        page.canvas.drawBitmap(bitmap, 0f, 0f, null)
        pdfDocument.finishPage(page)

        val cachePath = File(context.cacheDir, "shared_tickets")
        cachePath.mkdirs()
        val file = File(cachePath, "ticket_${ticketNo.replace("-", "_")}.pdf")

        FileOutputStream(file).use { out ->
            pdfDocument.writeTo(out)
        }
        pdfDocument.close()

        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )

        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/pdf"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Partager le ticket PDF"))
    }

    /**
     * Affiche un dialog de choix de format de partage
     */
    fun showShareDialog(
        context: Context,
        data: TicketShareData,
        onShareText: () -> Unit,
        onShareImage: () -> Unit
    ) {
        val options = arrayOf("Texte (SMS/WhatsApp)", "Image")
        android.app.AlertDialog.Builder(context)
            .setTitle("Partager le ticket")
            .setItems(options) { _, which ->
                when (which) {
                    0 -> onShareText()
                    1 -> onShareImage()
                }
            }
            .show()
    }
}
