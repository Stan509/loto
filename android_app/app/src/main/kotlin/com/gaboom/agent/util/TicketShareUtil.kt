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
import android.widget.Toast
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

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
        val mariageGratuitMontant: String = "0",
        val isOffline: Boolean = false
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
        if (!data.borletteName.isNullOrBlank()) {
            sb.appendLine("    ${data.borletteName.uppercase()}")
        }
        if (!data.borletteSlogan.isNullOrBlank()) {
            sb.appendLine("    ${data.borletteSlogan}")
        }
        if (!data.borletteTel.isNullOrBlank()) {
            sb.appendLine("    Tel: ${data.borletteTel}")
        }
        sb.appendLine("================================")
        sb.appendLine()
        
        // Ticket info
        sb.appendLine("Ticket: #${data.ticketNo}")
        sb.appendLine("Date: ${data.date}")
        sb.appendLine("Tirage: ${data.tirageNom}")
        if (!data.agentName.isNullOrBlank()) {
            sb.appendLine("Agent: ${data.agentName}")
        }
        if (data.isOffline) {
            sb.appendLine()
            sb.appendLine("*** HORS-LIGNE ***")
            sb.appendLine("A valider en ligne")
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
        if (!data.ticketFooterText.isNullOrBlank()) {
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
            textSize = 14f
            isAntiAlias = true
            textAlign = Paint.Align.CENTER
        }
        
        val paintSmall = Paint().apply {
            color = Color.GRAY
            textSize = 11f
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
        
        val hasBothLogoAndQr = data.logoBitmap != null && !data.qrCode.isNullOrBlank()
        if (hasBothLogoAndQr) {
            calcHeight += maxOf(logoSize, qrCodeSize) + 30 // side-by-side logo + QR + label
        } else {
            if (data.logoBitmap != null) calcHeight += logoSize + 10 // logo
            if (!data.qrCode.isNullOrBlank()) calcHeight += qrCodeSize + 30 // QR + label
        }
        
        calcHeight += 30 // borlette name
        if (!data.borletteSlogan.isNullOrBlank()) calcHeight += 18
        if (!data.borletteAdresse.isNullOrBlank()) calcHeight += 16
        if (!data.borletteTel.isNullOrBlank()) calcHeight += 18
        calcHeight += 15 // space
        
        calcHeight += 25 // separator
        calcHeight += 25 * 4 // ticket info (4 lines)
        if (data.isOffline) calcHeight += 45 // offline watermark
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
        if (!data.ticketFooterText.isNullOrBlank()) {
            val estimatedLines = (data.ticketFooterText.length / 45) + 1
            calcHeight += estimatedLines * 15
        }
        calcHeight += 70 // brand info + separator + bonne chance + merci
        
        val height = calcHeight
        val centerX = width / 2f
        
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        
        // Background couleur crème comme le preview
        canvas.drawColor(Color.rgb(255, 251, 230))
        
        var y = padding.toFloat()
        
        // ═══════════════════════════════════════════════════════════
        // LOGO (seulement en haut si pas côte à côte)
        // ═══════════════════════════════════════════════════════════
        if (data.logoBitmap != null && !hasBothLogoAndQr) {
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
        if (!data.borletteSlogan.isNullOrBlank()) {
            canvas.drawText(data.borletteSlogan, centerX, y + 12, paintSmall)
            y += 18
        }
        
        // Adresse
        if (!data.borletteAdresse.isNullOrBlank()) {
            canvas.drawText(data.borletteAdresse, centerX, y + 11, paintSmall)
            y += 16
        }
        
        // Téléphone
        if (!data.borletteTel.isNullOrBlank()) {
            canvas.drawText("Tel: ${data.borletteTel}", centerX, y + 14, paintNormalCenter)
            y += 18
        }
        
        y += 10
        
        // ═══════════════════════════════════════════════════════════
        // QR CODE / LOGO+QR CÔTE À CÔTE
        // ═══════════════════════════════════════════════════════════
        if (hasBothLogoAndQr) {
            val qrBitmap = QrCodeGenerator.generateQrCode(data.qrCode!!, qrCodeSize)
            if (qrBitmap != null && data.logoBitmap != null) {
                val gap = 20
                val combinedWidth = logoSize + gap + qrCodeSize
                val startX = (width - combinedWidth) / 2f
                
                // Draw logo
                val scaledLogo = Bitmap.createScaledBitmap(data.logoBitmap, logoSize, logoSize, true)
                val logoY = y + (maxOf(logoSize, qrCodeSize) - logoSize) / 2f
                canvas.drawBitmap(scaledLogo, startX, logoY, null)
                
                // Draw QR code
                val qrY = y + (maxOf(logoSize, qrCodeSize) - qrCodeSize) / 2f
                canvas.drawBitmap(qrBitmap, startX + logoSize + gap, qrY, null)
                
                y += maxOf(logoSize, qrCodeSize) + 5
                canvas.drawText("QR Code Groupe", centerX, y + 12, paintSmall)
                y += 20
            }
        } else if (!data.qrCode.isNullOrBlank()) {
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
        if (!data.agentName.isNullOrBlank()) {
            canvas.drawText("Agent: ${data.agentName}", padding.toFloat(), y + 16, paintNormal)
            y += 22
        }
        canvas.drawText("Tirage(s): ${data.tirageNom}", padding.toFloat(), y + 16, paintNormal)
        y += 22
        
        if (data.isOffline) {
            val paintOfflineTitle = Paint().apply {
                color = Color.RED
                textSize = 20f
                typeface = Typeface.DEFAULT_BOLD
                isAntiAlias = true
                textAlign = Paint.Align.CENTER
            }
            val paintOfflineSub = Paint().apply {
                color = Color.RED
                textSize = 14f
                isAntiAlias = true
                textAlign = Paint.Align.CENTER
            }
            canvas.drawText("*** HORS-LIGNE ***", centerX, y + 18, paintOfflineTitle)
            y += 22
            canvas.drawText("A valider en ligne", centerX, y + 14, paintOfflineSub)
            y += 18
        }
        
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
        
        if (!data.ticketFooterText.isNullOrBlank()) {
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
                canvas.drawText(fl, centerX, y + 12, paintSmall)
                y += 15
            }
            y += 5
        }
        
        canvas.drawText("Gaboom Borlette OS  www.gaboombos.com", centerX, y + 12, paintSmall)
        y += 15
        canvas.drawText("--------------------------------", centerX, y + 12, paintSeparator)
        y += 15
        canvas.drawText("Bonne chance", centerX, y + 14, paintNormalCenter)
        y += 18
        canvas.drawText("Merci pour votre confiance", centerX, y + 14, paintNormalCenter)
        
        return bitmap
    }

    /**
     * Convertit PrintData en TicketShareData
     */
    fun fromPrintData(
        printData: com.gaboom.agent.data.model.PrintData,
        logoBitmap: Bitmap? = null,
        totalGainDu: Double = 0.0,
        isWinner: Boolean = false
    ): TicketShareData {
        val parsedLines = (printData.lines ?: emptyList()).map { lineStr ->
            val tokens = lineStr.split("\\s+".toRegex()).filter { it.isNotBlank() }
            val jeuRaw = tokens.getOrElse(0) { "" }
            val valeur = tokens.getOrElse(1) { "" }
            
            var mise = 0.0
            var opt: String? = null
            
            if (tokens.size >= 4) {
                // Format: JEU VALEUR OPTX MISE (e.g. LOTO4 1234 OPT2 10.0)
                val optToken = tokens[2]
                val miseToken = tokens[3]
                opt = if (optToken.startsWith("OPT", ignoreCase = true)) optToken else null
                mise = if (miseToken.equals("GRATUIT", ignoreCase = true)) 0.0 
                       else (miseToken.replace("[^\\d\\.]".toRegex(), "").toDoubleOrNull() ?: 0.0)
            } else {
                // Format: JEU VALEUR MISE (e.g. BOULE 12 10.0)
                val miseToken = tokens.getOrElse(2) { "0" }
                mise = if (miseToken.equals("GRATUIT", ignoreCase = true)) 0.0 
                       else (miseToken.replace("[^\\d\\.]".toRegex(), "").toDoubleOrNull() ?: 0.0)
                
                // fallback to check if option is in jeuRaw (e.g. LOTO4-2)
                val optionParts = jeuRaw.split("-")
                if (optionParts.size > 1) {
                    opt = "OPT${optionParts[1]}"
                }
            }
            
            val optionParts = jeuRaw.split("-")
            val baseJeu = optionParts.getOrElse(0) { jeuRaw }

            TicketLineData(
                jeu = baseJeu,
                valeur = valeur,
                mise = mise,
                option = opt
            )
        }
        return TicketShareData(
            ticketNo = printData.ticketNumber ?: "",
            tirageNom = printData.tirages?.joinToString(", ") ?: "",
            date = "${printData.date ?: ""}  ${printData.time ?: ""}",
            lines = parsedLines,
            totalMise = printData.totalMise ?: 0.0,
            totalGainDu = totalGainDu,
            isWinner = isWinner,
            qrCode = printData.groupId,
            logoBitmap = logoBitmap,
            ticketFooterText = printData.ticketFooterText ?: "",
            mariageGratuitActif = printData.mariageGratuitActif ?: false,
            mariageGratuitMontant = printData.mariageGratuitMontant ?: "0",
            borletteName = printData.borletteName ?: "",
            borletteSlogan = printData.borletteSlogan ?: "",
            borletteTel = printData.borletteTel ?: "",
            borletteAdresse = printData.borletteAdresse ?: "",
            agentName = printData.agentName ?: ""
        )
    }

    /**
     * Helper to retrieve the underlying Activity from a Context wrapper.
     */
    fun findActivity(context: Context): android.app.Activity? {
        var ctx = context
        while (ctx is android.content.ContextWrapper) {
            if (ctx is android.app.Activity) {
                return ctx
            }
            ctx = ctx.baseContext
        }
        return null
    }

    /**
     * Télécharge le logo de la borlette depuis une URL
     */
    suspend fun downloadLogo(context: Context, logoUrl: String): Bitmap? = withContext(Dispatchers.IO) {
        if (logoUrl.isBlank()) return@withContext null
        try {
            val loader = ImageLoader(context)
            val request = ImageRequest.Builder(context)
                .data(logoUrl)
                .allowHardware(false)
                .build()
            val result = loader.execute(request)
            (result.drawable as? android.graphics.drawable.BitmapDrawable)?.bitmap
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur downloadLogo: ${e.message}", e)
            null
        }
    }

    /**
     * Génère l'intent pour le partage texte
     */
    fun getShareTextIntent(data: TicketShareData): Intent {
        val text = generateTicketText(data)
        return Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
            putExtra(Intent.EXTRA_SUBJECT, "Ticket ${data.ticketNo}")
        }
    }

    /**
     * Génère l'intent pour le partage d'image
     */
    suspend fun getShareImageIntent(context: Context, data: TicketShareData): Intent? = withContext(Dispatchers.IO) {
        try {
            val bitmap = generateTicketImage(context, data)
            val safeTicketNo = data.ticketNo.replace("[^a-zA-Z0-9]".toRegex(), "_")
            val cachePath = File(context.cacheDir, "shared_tickets")
            cachePath.mkdirs()
            val file = File(cachePath, "ticket_$safeTicketNo.png")

            FileOutputStream(file).use { out ->
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
            }

            val uri = FileProvider.getUriForFile(
                context.applicationContext,
                "${context.packageName}.fileprovider",
                file
            )

            Intent(Intent.ACTION_SEND).apply {
                type = "image/png"
                putExtra(Intent.EXTRA_STREAM, uri)
                clipData = android.content.ClipData.newUri(context.contentResolver, "ticket", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur getShareImageIntent: ${e.message}", e)
            null
        }
    }

    /**
     * Génère l'intent pour le partage PDF
     */
    suspend fun getSharePdfIntent(context: Context, bitmap: Bitmap, ticketNo: String): Intent? = withContext(Dispatchers.IO) {
        try {
            val pdfDocument = android.graphics.pdf.PdfDocument()
            val pageInfo = android.graphics.pdf.PdfDocument.PageInfo.Builder(bitmap.width, bitmap.height, 1).create()
            val page = pdfDocument.startPage(pageInfo)
            page.canvas.drawBitmap(bitmap, 0f, 0f, null)
            pdfDocument.finishPage(page)

            val safeTicketNo = ticketNo.replace("[^a-zA-Z0-9]".toRegex(), "_")
            val cachePath = File(context.cacheDir, "shared_tickets")
            cachePath.mkdirs()
            val file = File(cachePath, "ticket_$safeTicketNo.pdf")

            FileOutputStream(file).use { out ->
                pdfDocument.writeTo(out)
            }
            pdfDocument.close()

            val uri = FileProvider.getUriForFile(
                context.applicationContext,
                "${context.packageName}.fileprovider",
                file
            )

            Intent(Intent.ACTION_SEND).apply {
                type = "application/pdf"
                putExtra(Intent.EXTRA_STREAM, uri)
                clipData = android.content.ClipData.newUri(context.contentResolver, "ticket", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur getSharePdfIntent: ${e.message}", e)
            null
        }
    }

    private fun launchShareIntent(context: Context, intent: Intent, title: String) {
        val activity = findActivity(context)
        val targetContext = activity ?: context.applicationContext
        
        if (activity == null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        
        try {
            // Tenter de démarrer avec un sélecteur d'applications standard
            val chooser = Intent.createChooser(intent, title)
            if (activity == null) {
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            targetContext.startActivity(chooser)
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Chooser launch failed: ${e.message}, trying direct start", e)
            try {
                // Tenter de démarrer l'intention directement (très fiable sur les POS personnalisés)
                targetContext.startActivity(intent)
            } catch (ex: Throwable) {
                android.util.Log.e("TicketShare", "Direct start also failed: ${ex.message}", ex)
                Toast.makeText(context.applicationContext, "Aucune application de partage trouvée", Toast.LENGTH_LONG).show()
            }
        }
    }

    /**
     * Partage un bitmap existant (ne le regénère pas) - Méthode fallback
     */
    suspend fun shareBitmapAsImage(context: Context, bitmap: Bitmap, ticketNo: String) = withContext(Dispatchers.IO) {
        try {
            val safeTicketNo = ticketNo.replace("[^a-zA-Z0-9]".toRegex(), "_")
            val cachePath = File(context.cacheDir, "shared_tickets")
            cachePath.mkdirs()
            val file = File(cachePath, "ticket_$safeTicketNo.png")

            FileOutputStream(file).use { out ->
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
            }

            val uri = FileProvider.getUriForFile(
                context.applicationContext,
                "${context.packageName}.fileprovider",
                file
            )

            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "image/png"
                putExtra(Intent.EXTRA_STREAM, uri)
                clipData = android.content.ClipData.newUri(context.contentResolver, "ticket", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }

            withContext(Dispatchers.Main) {
                launchShareIntent(context, intent, "Partager le ticket")
            }
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur shareBitmapAsImage: ${e.message}", e)
            withContext(Dispatchers.Main) {
                Toast.makeText(context.applicationContext, "Erreur de partage d'image: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    /**
     * Partage le ticket en texte via Intent - Méthode fallback
     */
    suspend fun shareAsText(context: Context, data: TicketShareData) = withContext(Dispatchers.IO) {
        try {
            val intent = getShareTextIntent(data)
            withContext(Dispatchers.Main) {
                launchShareIntent(context, intent, "Partager le ticket")
            }
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur shareAsText: ${e.message}", e)
            withContext(Dispatchers.Main) {
                Toast.makeText(context.applicationContext, "Erreur de partage texte: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    /**
     * Partage le ticket en image via Intent - Méthode fallback
     */
    suspend fun shareAsImage(context: Context, data: TicketShareData) = withContext(Dispatchers.IO) {
        try {
            val bitmap = generateTicketImage(context, data)
            shareBitmapAsImage(context, bitmap, data.ticketNo)
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur shareAsImage: ${e.message}", e)
            withContext(Dispatchers.Main) {
                Toast.makeText(context.applicationContext, "Erreur de partage d'image: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    /**
     * Sauvegarde le ticket en PDF et lance le partage - Méthode fallback
     */
    suspend fun saveAsPdf(context: Context, bitmap: Bitmap, ticketNo: String) = withContext(Dispatchers.IO) {
        try {
            val pdfDocument = android.graphics.pdf.PdfDocument()
            val pageInfo = android.graphics.pdf.PdfDocument.PageInfo.Builder(bitmap.width, bitmap.height, 1).create()
            val page = pdfDocument.startPage(pageInfo)
            page.canvas.drawBitmap(bitmap, 0f, 0f, null)
            pdfDocument.finishPage(page)

            val safeTicketNo = ticketNo.replace("[^a-zA-Z0-9]".toRegex(), "_")
            val cachePath = File(context.cacheDir, "shared_tickets")
            cachePath.mkdirs()
            val file = File(cachePath, "ticket_$safeTicketNo.pdf")

            FileOutputStream(file).use { out ->
                pdfDocument.writeTo(out)
            }
            pdfDocument.close()

            val uri = FileProvider.getUriForFile(
                context.applicationContext,
                "${context.packageName}.fileprovider",
                file
            )

            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "application/pdf"
                putExtra(Intent.EXTRA_STREAM, uri)
                clipData = android.content.ClipData.newUri(context.contentResolver, "ticket", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }

            withContext(Dispatchers.Main) {
                launchShareIntent(context, intent, "Partager le ticket PDF")
            }
        } catch (e: Throwable) {
            android.util.Log.e("TicketShare", "Erreur saveAsPdf: ${e.message}", e)
            withContext(Dispatchers.Main) {
                Toast.makeText(context.applicationContext, "Erreur de génération PDF: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
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
