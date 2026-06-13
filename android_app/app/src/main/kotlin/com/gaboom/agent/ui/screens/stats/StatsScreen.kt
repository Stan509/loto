package com.gaboom.agent.ui.screens.stats

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
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
fun StatsScreen(
    onBack: () -> Unit,
    viewModel: StatsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var showWithdrawDialog by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        viewModel.loadStats()
    }

    // Snackbar pour messages
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(uiState.error, uiState.successMessage) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessages()
        }
        uiState.successMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessages()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Statistiques") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        when {
            uiState.isLoading -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center
                ) { Text("Chargement...") }
            }
            else -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Agent Info
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Column(modifier = Modifier.padding(20.dp)) {
                            Text(
                                uiState.agentNom,
                                fontSize = 20.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                "Zone: ${uiState.agentZone}",
                                fontSize = 14.sp,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                            )
                        }
                    }

                    // ═══════════════════════════════════════════════════════════
                    // GAINS TOTAUX + SOLDE CAISSE (côte à côte)
                    // ═══════════════════════════════════════════════════════════
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        // Gains Totaux
                        Card(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = Color(0xFF10B981).copy(alpha = 0.15f)
                            )
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text("💰 Gains Totaux", fontSize = 12.sp, color = Color(0xFF10B981))
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    "${uiState.globalGainsTotaux.toInt()} HTG",
                                    fontSize = 22.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF10B981)
                                )
                                Text(
                                    "Mises - Commission - Gains payés",
                                    fontSize = 10.sp,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                                )
                            }
                        }
                        // Solde Caisse
                        Card(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = Color(0xFF3B82F6).copy(alpha = 0.15f)
                            )
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text("🏧 Solde Caisse", fontSize = 12.sp, color = Color(0xFF3B82F6))
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    "${uiState.soldeCaisse.toInt()} HTG",
                                    fontSize = 22.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF3B82F6)
                                )
                                Text(
                                    "Mises - Gains dus - Retraits",
                                    fontSize = 10.sp,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                                )
                            }
                        }
                    }

                    // ═══════════════════════════════════════════════════════════
                    // COMMISSION AVEC BOUTON RETRAIT
                    // ═══════════════════════════════════════════════════════════
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.1f)
                        )
                    ) {
                        Column(modifier = Modifier.padding(20.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text("Commission disponible", fontSize = 14.sp)
                                    Text(
                                        "${uiState.commissionBalance.toInt()} HTG",
                                        fontSize = 28.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                                Button(
                                    onClick = { showWithdrawDialog = true },
                                    enabled = uiState.commissionBalance > 0 && !uiState.isWithdrawing,
                                    colors = ButtonDefaults.buttonColors(
                                        containerColor = Color(0xFF10B981)
                                    )
                                ) {
                                    Text(if (uiState.isWithdrawing) "..." else "Retirer")
                                }
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Gagnées: ${uiState.commissionEarned.toInt()} HTG", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                                Text("Retirées: ${uiState.commissionWithdrawn.toInt()} HTG", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                            }
                        }
                    }

                    // ═══════════════════════════════════════════════════════════
                    // AUJOURD'HUI
                    // ═══════════════════════════════════════════════════════════
                    Text("Aujourd'hui", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Tickets",
                            value = uiState.todayTickets.toString()
                        )
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Mises",
                            value = "${uiState.todayMises.toInt()} HTG"
                        )
                    }
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Gains dus",
                            value = "${uiState.todayGainsDu.toInt()} HTG"
                        )
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Gain agent",
                            value = "${uiState.todayGainAgent.toInt()} HTG",
                            valueColor = Color(0xFF10B981)
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // ═══════════════════════════════════════════════════════════
                    // PÉRIODE SÉLECTIONNÉE
                    // ═══════════════════════════════════════════════════════════
                    Text("Période", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    
                    // Sélecteur de période
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        PeriodButton(
                            text = "1 sem",
                            selected = uiState.selectedPeriod == 7,
                            onClick = { viewModel.selectPeriod(7) },
                            modifier = Modifier.weight(1f)
                        )
                        PeriodButton(
                            text = "2 sem",
                            selected = uiState.selectedPeriod == 14,
                            onClick = { viewModel.selectPeriod(14) },
                            modifier = Modifier.weight(1f)
                        )
                        PeriodButton(
                            text = "1 mois",
                            selected = uiState.selectedPeriod == 30,
                            onClick = { viewModel.selectPeriod(30) },
                            modifier = Modifier.weight(1f)
                        )
                        PeriodButton(
                            text = "1 an",
                            selected = uiState.selectedPeriod == 365,
                            onClick = { viewModel.selectPeriod(365) },
                            modifier = Modifier.weight(1f)
                        )
                    }
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Tickets",
                            value = uiState.periodTickets.toString()
                        )
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Mises",
                            value = "${uiState.periodMises.toInt()} HTG"
                        )
                    }
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Gains dus",
                            value = "${uiState.periodGainsDu.toInt()} HTG"
                        )
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Commission",
                            value = "${uiState.periodCommission.toInt()} HTG"
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        StatCard(
                            modifier = Modifier.weight(1f),
                            title = "Gain agent",
                            value = "${uiState.periodGainAgent.toInt()} HTG",
                            valueColor = Color(0xFF10B981)
                        )
                    }
                }
            }
        }
    }

    // Dialog de confirmation retrait
    if (showWithdrawDialog) {
        AlertDialog(
            onDismissRequest = { showWithdrawDialog = false },
            title = { Text("Retirer ma commission") },
            text = { 
                Text("Voulez-vous retirer ${uiState.commissionBalance.toInt()} HTG de commission?")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showWithdrawDialog = false
                        viewModel.withdrawCommission()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
                ) {
                    Text("Confirmer")
                }
            },
            dismissButton = {
                TextButton(onClick = { showWithdrawDialog = false }) {
                    Text("Annuler")
                }
            }
        )
    }
}

@Composable
fun StatCard(
    modifier: Modifier = Modifier,
    title: String,
    value: String,
    valueColor: Color? = null
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(title, fontSize = 12.sp)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                value, 
                fontSize = 20.sp, 
                fontWeight = FontWeight.Bold,
                color = valueColor ?: Color.Unspecified
            )
        }
    }
}

@Composable
fun PeriodButton(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Button(
        onClick = onClick,
        modifier = modifier.height(40.dp),
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (selected) 
                MaterialTheme.colorScheme.primary 
            else 
                MaterialTheme.colorScheme.surfaceVariant,
            contentColor = if (selected) 
                MaterialTheme.colorScheme.onPrimary 
            else 
                MaterialTheme.colorScheme.onSurfaceVariant
        )
    ) {
        Text(text, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}
