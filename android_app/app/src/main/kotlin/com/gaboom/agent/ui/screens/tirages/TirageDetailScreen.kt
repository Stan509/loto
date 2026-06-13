package com.gaboom.agent.ui.screens.tirages

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.local.LocalTicketCache
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TirageDetailScreen(
    tirageId: Int,
    tirageNom: String,
    tirageEtat: String,
    onNewTicket: () -> Unit,
    onBack: () -> Unit,
    viewModel: TirageDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val isOpen = tirageEtat == "OUVERT"

    LaunchedEffect(tirageId) {
        viewModel.loadTicketsForTirage(tirageId)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Column {
                        Text(tirageNom)
                        Text(
                            text = if (isOpen) "Tirage ouvert" else "Tirage fermé",
                            fontSize = 12.sp,
                            color = if (isOpen) Color(0xFF10B981) else Color(0xFF9CA3AF)
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadTicketsForTirage(tirageId) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Rafraîchir")
                    }
                }
            )
        },
        floatingActionButton = {
            if (isOpen) {
                ExtendedFloatingActionButton(
                    onClick = onNewTicket,
                    icon = { Icon(Icons.Default.Add, contentDescription = null) },
                    text = { Text("Nouveau Ticket") },
                    containerColor = MaterialTheme.colorScheme.primary
                )
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Message si tirage fermé
            if (!isOpen) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = Color(0xFFFEF3C7)
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Info,
                            contentDescription = null,
                            tint = Color(0xFFD97706),
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "Vente désactivée (tirage fermé). Vous pouvez consulter les tickets vendus.",
                            fontSize = 13.sp,
                            color = Color(0xFF92400E)
                        )
                    }
                }
            }

            // Stats rapides
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    StatItem(
                        label = "Tickets",
                        value = uiState.tickets.size.toString()
                    )
                    StatItem(
                        label = "Total Mises",
                        value = "${uiState.tickets.sumOf { it.totalMise }.toInt()} HTG"
                    )
                }
            }

            // Liste des tickets
            if (uiState.isLoading) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            } else if (uiState.tickets.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Default.Receipt,
                            contentDescription = null,
                            modifier = Modifier.size(48.dp),
                            tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Aucun ticket pour cette session",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                        )
                        if (isOpen) {
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(onClick = onNewTicket) {
                                Icon(Icons.Default.Add, contentDescription = null)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Créer un ticket")
                            }
                        }
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(uiState.tickets) { ticket ->
                        LocalTicketCard(ticket = ticket)
                    }
                }
            }
        }
    }
}

@Composable
private fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
        Text(
            text = label,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
        )
    }
}

@Composable
private fun LocalTicketCard(ticket: LocalTicketCache) {
    val dateFormat = SimpleDateFormat("HH:mm", Locale.getDefault())
    val timeStr = dateFormat.format(Date(ticket.createdAt))

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = ticket.ticketNo,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
                Text(
                    text = timeStr,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                )
            }
            Text(
                text = "${ticket.totalMise.toInt()} HTG",
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}
