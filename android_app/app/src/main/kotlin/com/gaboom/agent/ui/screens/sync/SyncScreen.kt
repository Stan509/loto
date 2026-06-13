package com.gaboom.agent.ui.screens.sync

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.local.PendingTicketEntity
import com.gaboom.agent.data.local.SyncStatus
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SyncScreen(
    onBack: () -> Unit,
    viewModel: SyncViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // Show messages
    LaunchedEffect(uiState.successMessage, uiState.errorMessage) {
        uiState.successMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessages()
        }
        uiState.errorMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessages()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Synchronisation") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                },
                actions = {
                    // Network status indicator
                    Box(
                        modifier = Modifier
                            .padding(end = 16.dp)
                            .size(12.dp)
                            .clip(CircleShape)
                            .background(if (uiState.isOnline) Color(0xFF10B981) else Color(0xFFEF4444))
                    )
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Status Card
            StatusCard(
                isOnline = uiState.isOnline,
                isSyncing = uiState.isSyncing,
                pendingCount = uiState.pendingCount,
                failedCount = uiState.failedCount,
                onSyncNow = { viewModel.syncNow() }
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Pending Batches List
            if (uiState.batches.isEmpty()) {
                EmptyState()
            } else {
                Text(
                    text = "Lots en attente",
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
                
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(uiState.batches, key = { it.batchId }) { batch ->
                        TicketBatchCard(
                            batch = batch,
                            onSyncBatch = { viewModel.syncBatch(batch.batchId) },
                            onDeleteBatch = { viewModel.deleteBatch(batch.batchId) },
                            onRetryTicket = { ticketId -> viewModel.retryTicket(ticketId) },
                            onDeleteTicket = { ticketId -> viewModel.deleteTicket(ticketId) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun StatusCard(
    isOnline: Boolean,
    isSyncing: Boolean,
    pendingCount: Int,
    failedCount: Int,
    onSyncNow: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            // Connection Status
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    imageVector = if (isOnline) Icons.Default.Wifi else Icons.Default.WifiOff,
                    contentDescription = null,
                    tint = if (isOnline) Color(0xFF10B981) else Color(0xFFEF4444),
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = if (isOnline) "Connecté" else "Hors ligne",
                        fontWeight = FontWeight.Bold,
                        color = if (isOnline) Color(0xFF10B981) else Color(0xFFEF4444)
                    )
                    Text(
                        text = if (isOnline) "Synchronisation automatique active" else "Les tickets seront synchronisés à la reconnexion",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Stats Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatItem(
                    label = "En attente",
                    value = pendingCount.toString(),
                    color = Color(0xFF3AA0FF)
                )
                StatItem(
                    label = "Échoués",
                    value = failedCount.toString(),
                    color = if (failedCount > 0) Color(0xFFEF4444) else Color(0xFF6B7280)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Sync Button
            Button(
                onClick = onSyncNow,
                enabled = isOnline && !isSyncing && (pendingCount > 0 || failedCount > 0),
                modifier = Modifier.fillMaxWidth()
            ) {
                if (isSyncing) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Synchronisation...")
                } else {
                    Icon(Icons.Default.Sync, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Synchroniser maintenant")
                }
            }
        }
    }
}

@Composable
fun StatItem(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = color
        )
        Text(
            text = label,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
        )
    }
}

@Composable
fun PendingTicketCard(
    ticket: PendingTicketEntity,
    onRetry: () -> Unit,
    onDelete: () -> Unit
) {
    val dateFormat = remember { SimpleDateFormat("dd/MM HH:mm", Locale.getDefault()) }
    
    val statusColor = when (ticket.syncStatus) {
        SyncStatus.PENDING -> Color(0xFF3AA0FF)
        SyncStatus.SYNCING -> Color(0xFFF59E0B)
        SyncStatus.SYNCED -> Color(0xFF10B981)
        SyncStatus.FAILED -> Color(0xFFEF4444)
    }
    
    val statusText = when (ticket.syncStatus) {
        SyncStatus.PENDING -> "En attente"
        SyncStatus.SYNCING -> "Synchronisation..."
        SyncStatus.SYNCED -> "Synchronisé"
        SyncStatus.FAILED -> "Échec"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier.padding(12.dp)
        ) {
            // Header row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Ticket local ID
                Text(
                    text = "HL-${ticket.id.take(8).uppercase()}",
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp
                )
                
                // Status badge
                Surface(
                    color = statusColor.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        text = statusText,
                        color = statusColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Tirage & Amount
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Tirage #${ticket.tirageId}",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
                Text(
                    text = "${ticket.totalMise} HTG",
                    fontWeight = FontWeight.Medium,
                    fontSize = 13.sp
                )
            }

            // Lines summary
            Text(
                text = ticket.linesSummary,
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 4.dp)
            )

            // Date and retry info
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = dateFormat.format(Date(ticket.createdAt)),
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
                if (ticket.retryCount > 0) {
                    Text(
                        text = "Essais: ${ticket.retryCount}",
                        fontSize = 11.sp,
                        color = Color(0xFFF59E0B)
                    )
                }
            }

            // Error message if failed
            if (ticket.syncStatus == SyncStatus.FAILED && ticket.errorMessage != null) {
                Text(
                    text = "⚠️ ${ticket.errorMessage}",
                    fontSize = 11.sp,
                    color = Color(0xFFEF4444),
                    modifier = Modifier.padding(top = 4.dp)
                )
            }

            // Action buttons for failed tickets
            if (ticket.syncStatus == SyncStatus.FAILED) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    TextButton(
                        onClick = onDelete,
                        colors = ButtonDefaults.textButtonColors(
                            contentColor = Color(0xFFEF4444)
                        )
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Supprimer", fontSize = 12.sp)
                    }
                    
                    Spacer(modifier = Modifier.width(8.dp))
                    
                    Button(
                        onClick = onRetry,
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Réessayer", fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@Composable
fun TicketBatchCard(
    batch: TicketBatchUi,
    onSyncBatch: () -> Unit,
    onDeleteBatch: () -> Unit,
    onRetryTicket: (String) -> Unit,
    onDeleteTicket: (String) -> Unit
) {
    val dateFormat = remember { SimpleDateFormat("dd/MM HH:mm", Locale.getDefault()) }
    var expanded by remember { mutableStateOf(false) }
    
    val statusColor = when (batch.overallStatus) {
        BatchOverallStatus.PENDING -> Color(0xFF3AA0FF)
        BatchOverallStatus.SYNCING -> Color(0xFFF59E0B)
        BatchOverallStatus.SYNCED -> Color(0xFF10B981)
        BatchOverallStatus.PARTIAL -> Color(0xFFF59E0B)
        BatchOverallStatus.FAILED -> Color(0xFFEF4444)
    }
    
    val statusText = when (batch.overallStatus) {
        BatchOverallStatus.PENDING -> "En attente"
        BatchOverallStatus.SYNCING -> "Synchronisation..."
        BatchOverallStatus.SYNCED -> "Synchronisé"
        BatchOverallStatus.PARTIAL -> "Partiel"
        BatchOverallStatus.FAILED -> "Échec"
    }
    
    val statusIcon = when (batch.overallStatus) {
        BatchOverallStatus.PENDING -> Icons.Default.Schedule
        BatchOverallStatus.SYNCING -> Icons.Default.Sync
        BatchOverallStatus.SYNCED -> Icons.Default.CheckCircle
        BatchOverallStatus.PARTIAL -> Icons.Default.Warning
        BatchOverallStatus.FAILED -> Icons.Default.Error
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(12.dp)
        ) {
            // Header row with batch label and status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        imageVector = statusIcon,
                        contentDescription = null,
                        tint = statusColor,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = batch.batchLabel,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                
                // Status badge
                Surface(
                    color = statusColor.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        text = statusText,
                        color = statusColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // Stats row: tickets count, amount, date
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "${batch.tickets.size} ticket(s)",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                )
                Text(
                    text = "${batch.totalAmount} HTG",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    text = dateFormat.format(Date(batch.createdAt)),
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
            }
            
            // Progress indicator for partial/syncing states
            if (batch.overallStatus == BatchOverallStatus.PARTIAL || 
                batch.overallStatus == BatchOverallStatus.SYNCING) {
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = batch.successCount.toFloat() / batch.tickets.size,
                    modifier = Modifier.fillMaxWidth(),
                    color = statusColor
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "${batch.successCount} OK",
                        fontSize = 11.sp,
                        color = Color(0xFF10B981)
                    )
                    if (batch.failedCount > 0) {
                        Text(
                            text = "${batch.failedCount} échec(s)",
                            fontSize = 11.sp,
                            color = Color(0xFFEF4444)
                        )
                    }
                }
            }
            
            // Batch action buttons
            if (batch.overallStatus != BatchOverallStatus.SYNCED) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    TextButton(
                        onClick = onDeleteBatch,
                        colors = ButtonDefaults.textButtonColors(
                            contentColor = Color(0xFFEF4444)
                        )
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Tout supprimer", fontSize = 12.sp)
                    }
                    
                    if (batch.overallStatus == BatchOverallStatus.FAILED || 
                        batch.overallStatus == BatchOverallStatus.PARTIAL) {
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = onSyncBatch,
                            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp)
                        ) {
                            Icon(Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Synchroniser", fontSize = 12.sp)
                        }
                    }
                }
            }
            
            // Expandable ticket details
            if (batch.tickets.size > 1 || batch.overallStatus == BatchOverallStatus.PARTIAL) {
                Spacer(modifier = Modifier.height(4.dp))
                TextButton(
                    onClick = { expanded = !expanded },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = if (expanded) "Masquer les détails" else "Voir les détails",
                        fontSize = 12.sp
                    )
                    Icon(
                        imageVector = if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                }
                
                if (expanded) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Column(
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        batch.tickets.forEach { ticket ->
                            MiniTicketItem(
                                ticket = ticket,
                                onRetry = { onRetryTicket(ticket.id) },
                                onDelete = { onDeleteTicket(ticket.id) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MiniTicketItem(
    ticket: PendingTicketEntity,
    onRetry: () -> Unit,
    onDelete: () -> Unit
) {
    val statusColor = when (ticket.syncStatus) {
        SyncStatus.PENDING -> Color(0xFF3AA0FF)
        SyncStatus.SYNCING -> Color(0xFFF59E0B)
        SyncStatus.SYNCED -> Color(0xFF10B981)
        SyncStatus.FAILED -> Color(0xFFEF4444)
    }
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(statusColor)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Tirage #${ticket.tirageId}",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
                Text(
                    text = "${ticket.totalMise} HTG · ${ticket.linesSummary.take(30)}...",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (ticket.syncStatus == SyncStatus.FAILED && ticket.errorMessage != null) {
                    Text(
                        text = ticket.errorMessage,
                        fontSize = 10.sp,
                        color = Color(0xFFEF4444),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            
            if (ticket.syncStatus == SyncStatus.FAILED) {
                Row {
                    IconButton(
                        onClick = onDelete,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            Icons.Default.Delete,
                            contentDescription = "Supprimer",
                            tint = Color(0xFFEF4444),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                    IconButton(
                        onClick = onRetry,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            Icons.Default.Refresh,
                            contentDescription = "Réessayer",
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun EmptyState() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = Color(0xFF10B981)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Tout est synchronisé !",
                fontWeight = FontWeight.Bold,
                fontSize = 18.sp
            )
            Text(
                text = "Aucun ticket en attente",
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                fontSize = 14.sp
            )
        }
    }
}
