package com.gaboom.agent.ui.screens.vente

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
import com.gaboom.agent.data.model.Tirage

/**
 * Écran de sélection du tirage - Point d'entrée fusionné Vente/Multi-Tirage
 * L'utilisateur choisit d'abord un tirage par défaut, puis va à l'écran de création
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TirageSelectionScreen(
    onTirageSelected: (tirageId: Int, tirageNom: String) -> Unit,
    onBack: () -> Unit,
    viewModel: TirageSelectionViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadOpenTirages()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Nouveau Ticket") },
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
                .padding(16.dp)
        ) {
            // Header
            Text(
                "Sélectionner un tirage",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold
            )
            Text(
                "Choisissez le tirage principal pour votre ticket",
                fontSize = 14.sp,
                color = Color.Gray,
                modifier = Modifier.padding(top = 4.dp, bottom = 16.dp)
            )

            // Loading
            if (uiState.isLoading) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            } else if (uiState.tirages.isEmpty()) {
                // Empty state
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
                    )
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(
                            Icons.Default.EventBusy,
                            contentDescription = null,
                            modifier = Modifier.size(48.dp),
                            tint = MaterialTheme.colorScheme.error
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            "Aucun tirage ouvert",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.error
                        )
                        Text(
                            "Aucun tirage n'est disponible pour la vente actuellement",
                            fontSize = 12.sp,
                            color = Color.Gray,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                }
            } else {
                // Liste des tirages
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(uiState.tirages) { tirage ->
                        TirageCard(
                            tirage = tirage,
                            onClick = { onTirageSelected(tirage.id, tirage.nom) }
                        )
                    }
                }
            }

            // Error message
            if (uiState.error != null) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    fontSize = 14.sp
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TirageCard(
    tirage: Tirage,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = when (tirage.etat) {
                "OUVERT" -> MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                else -> MaterialTheme.colorScheme.surfaceVariant
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Icon based on state
            Icon(
                imageVector = if (tirage.etat == "OUVERT") 
                    Icons.Default.CheckCircle 
                else 
                    Icons.Default.Lock,
                contentDescription = null,
                tint = if (tirage.etat == "OUVERT")
                    MaterialTheme.colorScheme.primary
                else
                    Color.Gray,
                modifier = Modifier.size(32.dp)
            )

            Spacer(modifier = Modifier.width(16.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = tirage.nom,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(top = 4.dp)
                ) {
                    Icon(
                        Icons.Default.Schedule,
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = Color.Gray
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = tirage.heureTirage,
                        fontSize = 13.sp,
                        color = Color.Gray
                    )
                }
            }

            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                tint = Color.Gray
            )
        }
    }
}
