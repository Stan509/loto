package com.gaboom.agent.ui.screens.tirages

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TiragesScreen(
    onTirageSelected: (Int, String) -> Unit,
    onBack: () -> Unit,
    viewModel: TiragesViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.startAutoRefresh()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Tirages actifs") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadTirages() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Rafraîchir")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Status bar: Online/Offline + Last sync
            StatusBar(
                isOnline = uiState.isOnline,
                lastSyncTime = uiState.lastSyncTime
            )
            
            // Content
        when {
            uiState.isLoading -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Chargement...")
                }
            }
            uiState.error != null -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = uiState.error!!,
                        color = MaterialTheme.colorScheme.error
                    )
                }
            }
            uiState.tirages.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Aucun tirage actif")
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(uiState.tirages) { tirage ->
                        TirageCard(
                            nom = tirage.nom,
                            type = tirage.type,
                            heureOuverture = tirage.heureOuverture,
                            heureFermeture = tirage.heureFermeture,
                            etat = tirage.etat,
                            onClick = { onTirageSelected(tirage.id, tirage.nom) }
                        )
                    }
                }
            }
        }
        }
    }
}

@Composable
fun StatusBar(
    isOnline: Boolean,
    lastSyncTime: String?
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = if (isOnline) Color(0xFF10B981).copy(alpha = 0.1f) else Color(0xFFEF4444).copy(alpha = 0.1f)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (isOnline) Icons.Default.Wifi else Icons.Default.WifiOff,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = if (isOnline) Color(0xFF10B981) else Color(0xFFEF4444)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (isOnline) "En ligne" else "Hors ligne",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    color = if (isOnline) Color(0xFF10B981) else Color(0xFFEF4444)
                )
            }
            if (lastSyncTime != null) {
                Text(
                    text = "Sync: $lastSyncTime",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TirageCard(
    nom: String,
    type: String,
    heureOuverture: String,
    heureFermeture: String,
    etat: String,
    onClick: () -> Unit
) {
    val isOpen = etat == "OUVERT"

    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isOpen) 
                MaterialTheme.colorScheme.surface 
            else 
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f)
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = nom,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (isOpen) 
                        MaterialTheme.colorScheme.onSurface 
                    else 
                        MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
                Text(
                    text = "$heureOuverture - $heureFermeture",
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
                if (!isOpen) {
                    Text(
                        text = "Voir tickets vendus",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.8f)
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.Circle,
                    contentDescription = null,
                    modifier = Modifier.size(12.dp),
                    tint = if (isOpen) Color(0xFF10B981) else Color(0xFF9CA3AF)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (isOpen) "Ouvert" else "Fermé",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    color = if (isOpen) Color(0xFF10B981) else Color(0xFF9CA3AF)
                )
            }
        }
    }
}
