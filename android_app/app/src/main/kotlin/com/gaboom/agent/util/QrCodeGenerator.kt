package com.gaboom.agent.util

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter

/**
 * Utilitaire pour générer des QR codes
 */
object QrCodeGenerator {

    /**
     * Génère un bitmap de QR code à partir d'une chaîne de caractères
     * @param content Le contenu à encoder dans le QR code
     * @param size La taille du QR code en pixels
     * @return Le bitmap du QR code ou null en cas d'erreur
     */
    fun generateQrCode(content: String, size: Int = 200): Bitmap? {
        return try {
            val hints = hashMapOf<EncodeHintType, Any>()
            hints[EncodeHintType.MARGIN] = 1
            hints[EncodeHintType.CHARACTER_SET] = "UTF-8"

            val writer = QRCodeWriter()
            val bitMatrix = writer.encode(content, BarcodeFormat.QR_CODE, size, size, hints)

            val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.RGB_565)
            for (x in 0 until size) {
                for (y in 0 until size) {
                    bitmap.setPixel(x, y, if (bitMatrix[x, y]) Color.BLACK else Color.WHITE)
                }
            }
            bitmap
        } catch (e: Throwable) {
            e.printStackTrace()
            null
        }
    }
}

/**
 * Composable pour afficher un QR code
 * @param content Le contenu à encoder
 * @param size La taille du QR code
 * @param modifier Modifier optionnel
 */
@Composable
fun QrCodeImage(
    content: String,
    size: Dp = 100.dp,
    modifier: Modifier = Modifier
) {
    val bitmap = remember(content) {
        QrCodeGenerator.generateQrCode(content, (size.value * 2).toInt())
    }

    if (bitmap != null) {
        Image(
            bitmap = bitmap.asImageBitmap(),
            contentDescription = "QR Code",
            modifier = modifier.size(size)
        )
    } else {
        // Fallback si le QR code ne peut pas être généré
        Box(
            modifier = modifier
                .size(size)
                .background(
                    androidx.compose.ui.graphics.Color.LightGray,
                    RoundedCornerShape(4.dp)
                ),
            contentAlignment = Alignment.Center
        ) {
            Text(
                "QR",
                fontSize = 12.sp,
                color = androidx.compose.ui.graphics.Color.DarkGray
            )
        }
    }
}
