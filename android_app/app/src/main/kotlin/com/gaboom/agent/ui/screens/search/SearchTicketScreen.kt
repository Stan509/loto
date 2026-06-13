package com.gaboom.agent.ui.screens.search

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import kotlinx.coroutines.launch
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.model.TicketSearchResult

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchTicketScreen(
    onBack: () -> Unit,
    onRefaire: (TicketSearchResult) -> Unit = { }, // Disabled - kept for API compatibility
    viewModel: SearchTicketViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var searchQuery by remember { mutableStateOf("") }
    var selectedTicket by remember { mutableStateOf<TicketSearchResult?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Rechercher Fiche") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Search input
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Numéro ticket ou UUID") },
                placeholder = { Text("Ex: 240201-001 ou abc123...") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = ""; viewModel.clearResults() }) {
                            Icon(Icons.Default.Clear, contentDescription = "Effacer")
                        }
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = { viewModel.search(searchQuery) }
                )
            )

            Spacer(modifier = Modifier.height(12.dp))

            Button(
                onClick = { viewModel.search(searchQuery) },
                modifier = Modifier.fillMaxWidth(),
                enabled = searchQuery.length >= 3 && !uiState.isLoading
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp
                    )
                } else {
                    Icon(Icons.Default.Search, contentDescription = null)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text("Rechercher")
            }

            // Error message
            if (uiState.error != null) {
                Spacer(modifier = Modifier.height(12.dp))
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFEE2E2))
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Error, contentDescription = null, tint = Color(0xFFDC2626))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(uiState.error!!, color = Color(0xFF991B1B))
                    }
                }
            }

            // Success message
            if (uiState.successMessage != null) {
                Spacer(modifier = Modifier.height(12.dp))
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFD1FAE5))
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF059669))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(uiState.successMessage!!, color = Color(0xFF065F46))
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Results
            if (uiState.tickets.isEmpty() && !uiState.isLoading && uiState.hasSearched) {
                Box(
                    modifier = Modifier.fillMaxWidth().padding(32.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Aucun ticket trouvé",
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                    )
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(uiState.tickets) { ticket ->
                        TicketResultCard(
                            ticket = ticket,
                            isExpanded = selectedTicket?.id == ticket.id,
                            onToggleExpand = {
                                selectedTicket = if (selectedTicket?.id == ticket.id) null else ticket
                            },
                            onPrint = { viewModel.printTicket(ticket.id) },
                            onRefaire = {
                                scope.launch {
                                    snackbarHostState.showSnackbar(
                                        message = "Fonction désactivée temporairement",
                                        duration = SnackbarDuration.Short
                                    )
                                }
                            },
                            onPay = { viewModel.payTicket(ticket.id) },
                            onVoid = { viewModel.voidTicket(ticket.id) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TicketResultCard(
    ticket: TicketSearchResult,
    isExpanded: Boolean,
    onToggleExpand: () -> Unit,
    onPrint: () -> Unit,
    onRefaire: () -> Unit,
    onPay: () -> Unit,
    onVoid: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onToggleExpand() },
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = ticket.ticketNo,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp
                    )
                    Text(
                        text = ticket.tirageNom,
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    // Winner badge
                    if (ticket.isWinner) {
                        Surface(
                            color = if (ticket.isPaid) Color(0xFFD1FAE5) else Color(0xFFFEF3C7),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(
                                text = if (ticket.isPaid) "PAYÉ" else "GAGNANT",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (ticket.isPaid) Color(0xFF059669) else Color(0xFFD97706)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "${ticket.totalMise.toInt()} HTG",
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            // Expanded content
            if (isExpanded) {
                Spacer(modifier = Modifier.height(12.dp))
                Divider()
                Spacer(modifier = Modifier.height(12.dp))

                // Gain info
                if (ticket.isWinner) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Gain dû:", fontWeight = FontWeight.Medium)
                        Text(
                            text = "${ticket.totalGainDu.toInt()} HTG",
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF10B981)
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                }

                // Lines
                ticket.lines?.forEach { line ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 2.dp),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "${line.jeu.uppercase()} ${line.valeur}",
                            fontSize = 13.sp
                        )
                        Row {
                            Text(
                                text = "${line.mise.toInt()} HTG",
                                fontSize = 13.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                            )
                            if (line.isWinner) {
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "→ ${line.gainDu.toInt()} HTG",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF10B981)
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Action buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Print
                    OutlinedButton(
                        onClick = onPrint,
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.Print, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Imprimer", fontSize = 12.sp)
                    }

                    // Refaire
                    OutlinedButton(
                        onClick = onRefaire,
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Refaire", fontSize = 12.sp)
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Pay (if winner and not paid)
                    if (ticket.isWinner && !ticket.isPaid) {
                        Button(
                            onClick = onPay,
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
                        ) {
                            Icon(Icons.Default.Payments, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Payer", fontSize = 12.sp)
                        }
                    }

                    // Void (if can void)
                    if (ticket.canVoid) {
                        Button(
                            onClick = onVoid,
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFEF4444))
                        ) {
                            Icon(Icons.Default.Cancel, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Annuler", fontSize = 12.sp)
                        }
                    }
                }
            }
        }
    }
}
