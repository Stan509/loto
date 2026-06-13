package com.gaboom.agent.ui.screens.home

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onNavigateToVente: () -> Unit,
    onNavigateToHistorique: () -> Unit,
    onNavigateToResultats: () -> Unit,
    onNavigateToStats: () -> Unit,
    onNavigateToSearch: () -> Unit,
    onNavigateToTicketManagement: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToSync: () -> Unit,
    onLogout: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadQuickStats()
        viewModel.startConnectivityCheck()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Gaboom Agent") },
                actions = {
                    // Sync button with badge
                    Box {
                        IconButton(onClick = onNavigateToSync) {
                            Icon(Icons.Default.Sync, contentDescription = "Synchronisation")
                        }
                        if (uiState.pendingSyncCount > 0) {
                            Badge(
                                modifier = Modifier
                                    .align(Alignment.TopEnd)
                                    .offset(x = (-4).dp, y = 4.dp)
                            ) {
                                Text(
                                    text = uiState.pendingSyncCount.toString(),
                                    fontSize = 10.sp
                                )
                            }
                        }
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Paramètres")
                    }
                    IconButton(onClick = { viewModel.logout { onLogout() } }) {
                        Icon(Icons.Default.Logout, contentDescription = "Déconnexion")
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
            // Status bar: Online/Offline + Last sync + Pending count
            HomeStatusBar(
                isOnline = uiState.isOnline,
                lastSyncTime = uiState.lastSyncTime,
                pendingSyncCount = uiState.pendingSyncCount,
                onSyncClick = onNavigateToSync
            )

            // Barre rapide : Gains Totaux + Solde Caisse
            if (uiState.statsLoaded) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    // Gains Totaux
                    Card(
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = Color(0xFF10B981).copy(alpha = 0.15f)
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text("💰 Gains Totaux", fontSize = 11.sp, color = Color(0xFF10B981))
                            Text(
                                "${uiState.gainsTotaux.toInt()} HTG",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF10B981)
                            )
                        }
                    }
                    // Solde Caisse
                    Card(
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = Color(0xFF3B82F6).copy(alpha = 0.15f)
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text("🏧 Solde Caisse", fontSize = 11.sp, color = Color(0xFF3B82F6))
                            Text(
                                "${uiState.soldeCaisse.toInt()} HTG",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF3B82F6)
                            )
                        }
                    }
                }
            }

            // Animated Logo Header
            AnimatedLogoHeader(
                logoUrl = uiState.borletteLogoUrl,
                borletteName = uiState.borletteName,
                borletteSlogan = uiState.borletteSlogan
            )

            // Menu Grid
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                item {
                    MenuCard(
                        icon = Icons.Default.PointOfSale,
                        title = "Vente",
                        subtitle = "Nouveau ticket",
                        onClick = onNavigateToVente,
                        highlight = true
                    )
                }
                item {
                    MenuCard(
                        icon = Icons.Default.Receipt,
                        title = "Gestion Tickets",
                        subtitle = "Paiements",
                        onClick = onNavigateToTicketManagement
                    )
                }
                item {
                    MenuCard(
                        icon = Icons.Default.EmojiEvents,
                        title = "Résultats",
                        subtitle = "Tirages",
                        onClick = onNavigateToResultats
                    )
                }
                item {
                    MenuCard(
                        icon = Icons.Default.BarChart,
                        title = "Stats",
                        subtitle = "Performance",
                        onClick = onNavigateToStats
                    )
                }
            }
        }
    }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeStatusBar(
    isOnline: Boolean,
    lastSyncTime: String?,
    pendingSyncCount: Int,
    onSyncClick: () -> Unit
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
            
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Pending sync indicator
                if (pendingSyncCount > 0) {
                    Surface(
                        onClick = onSyncClick,
                        color = Color(0xFFF59E0B).copy(alpha = 0.15f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.CloudUpload,
                                contentDescription = null,
                                modifier = Modifier.size(14.dp),
                                tint = Color(0xFFF59E0B)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "$pendingSyncCount en attente",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                color = Color(0xFFF59E0B)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(8.dp))
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
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MenuCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit,
    highlight: Boolean = false
) {
    Card(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFF5B21B6)  // Violet sombre
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = title,
                modifier = Modifier.size(40.dp),
                tint = Color.White
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = title,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            Text(
                text = subtitle,
                fontSize = 12.sp,
                color = Color.White.copy(alpha = 0.7f)
            )
        }
    }
}

@Composable
fun AnimatedLogoHeader(
    logoUrl: String,
    borletteName: String,
    borletteSlogan: String
) {
    // Pulse animation for the logo
    val infiniteTransition = rememberInfiniteTransition(label = "logo_pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = EaseInOutCubic),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )
    
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = EaseInOutCubic),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alpha"
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Animated Logo
        if (logoUrl.isNotBlank()) {
            Box(
                modifier = Modifier
                    .size(100.dp)
                    .graphicsLayer {
                        scaleX = scale
                        scaleY = scale
                        this.alpha = alpha
                    }
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)),
                contentAlignment = Alignment.Center
            ) {
                AsyncImage(
                    model = logoUrl,
                    contentDescription = "Logo Borlette",
                    modifier = Modifier
                        .size(80.dp)
                        .clip(CircleShape)
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
        }
        
        // Borlette Name with glow effect
        Text(
            text = borletteName.ifEmpty { "GABOOM BORLETTE" },
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
        
        // Slogan
        if (borletteSlogan.isNotBlank()) {
            Text(
                text = borletteSlogan,
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 32.dp)
            )
        }
    }
}
