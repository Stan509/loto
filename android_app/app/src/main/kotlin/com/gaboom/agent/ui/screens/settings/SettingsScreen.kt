package com.gaboom.agent.ui.screens.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.config.AppConfigDataStore

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Paramètres") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(scrollState)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Server Configuration Section
            SettingsSection(title = "Configuration Serveur") {
                // Base URL Input
                OutlinedTextField(
                    value = uiState.baseUrl,
                    onValueChange = { viewModel.updateBaseUrl(it) },
                    label = { Text("URL du serveur") },
                    placeholder = { Text("http://192.168.1.100:8000/api/agent/") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    leadingIcon = {
                        Icon(Icons.Default.Cloud, contentDescription = null)
                    },
                    supportingText = {
                        if (uiState.isCustomUrl) {
                            Text("Configuration personnalisée", color = Color(0xFF3AA0FF))
                        } else {
                            Text("Configuration par défaut")
                        }
                    }
                )

                Spacer(modifier = Modifier.height(8.dp))

                // Action Buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Save Button
                    Button(
                        onClick = { viewModel.saveSettings() },
                        enabled = !uiState.isLoading,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        if (uiState.isLoading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                                color = MaterialTheme.colorScheme.onPrimary
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                        } else {
                            Icon(
                                Icons.Default.Save,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        Text("Sauvegarder")
                    }
                }

                // Reset to Default Button
                if (uiState.isCustomUrl) {
                    TextButton(
                        onClick = { viewModel.resetToDefault() },
                        enabled = !uiState.isLoading && !uiState.isTesting,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(
                            Icons.Default.RestartAlt,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Réinitialiser par défaut")
                    }
                }

                // Test Result
                uiState.testResult?.let { result ->
                    Spacer(modifier = Modifier.height(8.dp))
                    TestResultCard(result)
                }

                // Success Message
                if (uiState.saveSuccess) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = Color(0xFF10B981).copy(alpha = 0.1f)
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = Color(0xFF10B981),
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                "Configuration sauvegardée avec succès",
                                color = Color(0xFF10B981),
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                // Error Message
                uiState.errorMessage?.let { error ->
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = Color(0xFFEF4444).copy(alpha = 0.1f)
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.Error,
                                contentDescription = null,
                                tint = Color(0xFFEF4444),
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                error,
                                color = Color(0xFFEF4444),
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
            }

            // Theme Selection Section
            SettingsSection(title = "Apparence") {
                Text(
                    "Mode de couleur",
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(bottom = 12.dp)
                )
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Default Theme (Violet)
                    ThemeOptionCard(
                        title = "Défaut",
                        subtitle = "Violet",
                        isSelected = uiState.themeMode == AppConfigDataStore.THEME_DEFAULT,
                        color = Color(0xFF7C4DFF),
                        onClick = { viewModel.setThemeMode(AppConfigDataStore.THEME_DEFAULT) },
                        modifier = Modifier.weight(1f)
                    )
                    
                    // Light Theme
                    ThemeOptionCard(
                        title = "Jour",
                        subtitle = "Clair",
                        isSelected = uiState.themeMode == AppConfigDataStore.THEME_LIGHT,
                        color = Color(0xFF6200EE),
                        isLight = true,
                        onClick = { viewModel.setThemeMode(AppConfigDataStore.THEME_LIGHT) },
                        modifier = Modifier.weight(1f)
                    )
                    
                    // Dark Theme
                    ThemeOptionCard(
                        title = "Nuit",
                        subtitle = "Bleu",
                        isSelected = uiState.themeMode == AppConfigDataStore.THEME_DARK,
                        color = Color(0xFF3AA0FF),
                        onClick = { viewModel.setThemeMode(AppConfigDataStore.THEME_DARK) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            // App Info Section
            SettingsSection(title = "À propos") {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("Version", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                    Text(
                        "${uiState.appVersion} (${uiState.appVersionCode})",
                        fontWeight = FontWeight.Medium,
                        fontFamily = FontFamily.Monospace
                    )
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("Application", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                    Text("Gaboom Agent", fontWeight = FontWeight.Medium)
                }
            }

            // Help Section
            SettingsSection(title = "Aide") {
                Text(
                    "Pour configurer l'application, entrez l'URL du serveur fournie par votre administrateur.",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                    fontSize = 14.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Format: http://[adresse-ip]:[port]/api/agent/",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.primary
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Exemple: http://192.168.1.100:8000/api/agent/",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
            }
        }
    }

    // Clear messages when leaving screen
    DisposableEffect(Unit) {
        onDispose {
            viewModel.clearMessages()
        }
    }
}

@Composable
fun SettingsSection(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = title,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            content()
        }
    }
}

@Composable
fun TestResultCard(result: TestResult) {
    val (triple, subtitle) = when (result) {
        is TestResult.Success -> {
            val serverInfo = buildString {
                if (result.version != null) append("Version: ${result.version}")
                if (result.serverTime != null) {
                    if (isNotEmpty()) append("\n")
                    append("Heure serveur: ${result.serverTime}")
                }
            }
            Triple(
                Icons.Default.CheckCircle,
                Color(0xFF10B981),
                "Connexion réussie"
            ) to serverInfo.ifEmpty { "Serveur accessible" }
        }
        is TestResult.Error -> {
            Triple(
                Icons.Default.Error,
                Color(0xFFEF4444),
                "Échec de connexion"
            ) to result.message
        }
    }
    val (icon, color, title) = triple

    Card(
        colors = CardDefaults.cardColors(
            containerColor = color.copy(alpha = 0.1f)
        ),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.Top
        ) {
            Icon(
                icon,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    title,
                    fontWeight = FontWeight.Bold,
                    color = color
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    subtitle,
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ThemeOptionCard(
    title: String,
    subtitle: String,
    isSelected: Boolean,
    color: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    isLight: Boolean = false
) {
    Card(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) color.copy(alpha = 0.2f) else MaterialTheme.colorScheme.surfaceVariant
        ),
        border = if (isSelected) androidx.compose.foundation.BorderStroke(2.dp, color) else null
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Color preview circle
            Surface(
                modifier = Modifier.size(40.dp),
                shape = androidx.compose.foundation.shape.CircleShape,
                color = if (isLight) Color(0xFFF8F9FA) else color.copy(alpha = 0.8f),
                border = if (isLight) androidx.compose.foundation.BorderStroke(2.dp, color) else null
            ) {
                Box(
                    contentAlignment = Alignment.Center
                ) {
                    if (isSelected) {
                        Icon(
                            Icons.Default.Check,
                            contentDescription = null,
                            tint = if (isLight) color else Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = title,
                fontWeight = FontWeight.Bold,
                fontSize = 13.sp
            )
            Text(
                text = subtitle,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
    }
}
