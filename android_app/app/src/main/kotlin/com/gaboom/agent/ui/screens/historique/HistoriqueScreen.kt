package com.gaboom.agent.ui.screens.historique

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.model.TicketInfo

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoriqueScreen(
    onBack: () -> Unit,
    viewModel: HistoriqueViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadHistorique()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Historique") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                }
            )
        }
    ) { padding ->
        when {
            uiState.isLoading -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center
                ) { Text("Chargement...") }
            }
            uiState.tickets.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center
                ) { Text("Aucun ticket") }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(uiState.tickets) { ticket ->
                        TicketCard(ticket)
                    }
                }
            }
        }
    }
}

@Composable
fun TicketCard(ticket: TicketInfo) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(ticket.numero, fontWeight = FontWeight.Bold)
                Text(ticket.statut, fontSize = 12.sp)
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text("Tirages: ${ticket.tirages.joinToString(", ")}", fontSize = 12.sp)
            Text("Total: ${ticket.totalMise.toInt()} HTG", fontWeight = FontWeight.Bold)
        }
    }
}
