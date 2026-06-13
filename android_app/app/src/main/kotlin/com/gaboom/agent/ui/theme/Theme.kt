package com.gaboom.agent.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// ═══════════════════════════════════════════════════════════════════════════
// THEME MODE: DEFAULT (Violet sombre premium)
// ═══════════════════════════════════════════════════════════════════════════
private val DefaultPrimary = Color(0xFF7C4DFF)  // Violet
private val DefaultSecondary = Color(0xFF10B981)
private val DefaultBackground = Color(0xFF1A1025)  // Violet très sombre
private val DefaultSurface = Color(0xFF2D1B42)
private val DefaultSurfaceVariant = Color(0xFF3D2952)

private val DefaultColorScheme = darkColorScheme(
    primary = DefaultPrimary,
    secondary = DefaultSecondary,
    tertiary = Color(0xFF9C27B0),
    background = DefaultBackground,
    surface = DefaultSurface,
    surfaceVariant = DefaultSurfaceVariant,
    primaryContainer = Color(0xFF5B21B6),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onTertiary = Color.White,
    onBackground = Color(0xFFE8EAED),
    onSurface = Color(0xFFE8EAED),
    error = Color(0xFFFF4D6D),
)

// ═══════════════════════════════════════════════════════════════════════════
// THEME MODE: DARK (Bleu sombre)
// ═══════════════════════════════════════════════════════════════════════════
private val DarkPrimary = Color(0xFF3AA0FF)
private val DarkSecondary = Color(0xFF10B981)
private val DarkBackground = Color(0xFF0A101E)
private val DarkSurface = Color(0xFF141B2D)
private val DarkSurfaceVariant = Color(0xFF1A2235)

private val DarkColorScheme = darkColorScheme(
    primary = DarkPrimary,
    secondary = DarkSecondary,
    tertiary = Color(0xFF7C4DFF),
    background = DarkBackground,
    surface = DarkSurface,
    surfaceVariant = DarkSurfaceVariant,
    primaryContainer = Color(0xFF1E3A5F),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onTertiary = Color.White,
    onBackground = Color(0xFFE8EAED),
    onSurface = Color(0xFFE8EAED),
    error = Color(0xFFFF4D6D),
)

// ═══════════════════════════════════════════════════════════════════════════
// THEME MODE: LIGHT (Clair)
// ═══════════════════════════════════════════════════════════════════════════
private val LightPrimary = Color(0xFF6200EE)
private val LightSecondary = Color(0xFF03DAC6)

private val LightColorScheme = lightColorScheme(
    primary = LightPrimary,
    secondary = LightSecondary,
    tertiary = Color(0xFF7C4DFF),
    background = Color(0xFFF8F9FA),
    surface = Color.White,
    surfaceVariant = Color(0xFFE8EAED),
    primaryContainer = Color(0xFFE8DEF8),
    onPrimary = Color.White,
    onSecondary = Color.Black,
    onTertiary = Color.White,
    onBackground = Color(0xFF1A1A1A),
    onSurface = Color(0xFF1A1A1A),
    error = Color(0xFFB00020),
)

@Composable
fun GaboomAgentTheme(
    themeMode: String = "default",  // "default", "light", "dark"
    content: @Composable () -> Unit
) {
    val colorScheme = when (themeMode) {
        "light" -> LightColorScheme
        "dark" -> DarkColorScheme
        else -> DefaultColorScheme  // "default" = violet sombre
    }
    
    val isDark = themeMode != "light"

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !isDark
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
