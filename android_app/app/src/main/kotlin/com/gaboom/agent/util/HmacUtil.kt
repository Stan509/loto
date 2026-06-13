package com.gaboom.agent.util

import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * HMAC utility for offline ticket signing (Phase I-A Anti-Tamper)
 * 
 * Signature: HMAC_SHA256(deviceSecret, payloadJson + sessionKey)
 */
object HmacUtil {
    
    private const val HMAC_ALGORITHM = "HmacSHA256"
    
    /**
     * Generate HMAC-SHA256 signature for offline ticket payload.
     * 
     * @param deviceSecret The device secret from server registration
     * @param payloadJson The JSON payload (must be consistently serialized)
     * @param sessionKey The tirage session key
     * @return Hex-encoded HMAC signature
     */
    fun signPayload(deviceSecret: String, payloadJson: String, sessionKey: String): String {
        val message = "$payloadJson$sessionKey"
        val keySpec = SecretKeySpec(deviceSecret.toByteArray(Charsets.UTF_8), HMAC_ALGORITHM)
        val mac = Mac.getInstance(HMAC_ALGORITHM)
        mac.init(keySpec)
        val bytes = mac.doFinal(message.toByteArray(Charsets.UTF_8))
        return bytes.toHex()
    }
    
    /**
     * Verify HMAC signature (for testing/validation).
     */
    fun verifySignature(deviceSecret: String, payloadJson: String, sessionKey: String, signature: String): Boolean {
        val expected = signPayload(deviceSecret, payloadJson, sessionKey)
        // Constant-time comparison to prevent timing attacks
        return MessageDigest.isEqual(
            expected.toByteArray(Charsets.UTF_8),
            signature.toByteArray(Charsets.UTF_8)
        )
    }
    
    private fun ByteArray.toHex(): String {
        return joinToString("") { "%02x".format(it) }
    }
}
