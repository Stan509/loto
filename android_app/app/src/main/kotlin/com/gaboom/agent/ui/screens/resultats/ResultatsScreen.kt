package com.gaboom.agent.ui.screens.resultats

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.model.ResultatTirage

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultatsScreen(
    onBack: () -> Unit,
    viewModel: ResultatsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var selectedResultat by remember { mutableStateOf<ResultatTirage?>(null) }

    LaunchedEffect(Unit) {
        viewModel.loadResultats()
    }

    // Modal détail
    if (selectedResultat != null) {
        ResultatDetailDialog(
            resultat = selectedResultat!!,
            onDismiss = { selectedResultat = null }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Résultats Tirages") },
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
            uiState.resultats.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    contentAlignment = Alignment.Center
                ) { 
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Aucun résultat disponible", fontSize = 16.sp)
                        Text("Les résultats apparaîtront après les tirages", fontSize = 12.sp, color = Color.Gray)
                    }
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(uiState.resultats) { resultat ->
                        ResultatCard(
                            resultat = resultat,
                            onClick = { selectedResultat = resultat }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ResultatCard(
    resultat: ResultatTirage,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header: nom tirage + date
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    resultat.tirageNom,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
                Column(horizontalAlignment = Alignment.End) {
                    Text(resultat.date, fontSize = 12.sp, color = Color.Gray)
                    Text(resultat.heureTirage, fontSize = 11.sp, color = Color.Gray)
                }
            }
            
            Spacer(modifier = Modifier.height(12.dp))
            
            // Lots principaux: lot1, lot2, lot3
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                LotChip(label = "1er", value = resultat.lot1, color = Color(0xFFFFD700))
                LotChip(label = "2ème", value = resultat.lot2, color = Color(0xFFC0C0C0))
                LotChip(label = "3ème", value = resultat.lot3, color = Color(0xFFCD7F32))
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // Loto3 visible
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center
            ) {
                Text("Loto3: ", fontSize = 14.sp, color = Color.Gray)
                Text(
                    resultat.loto3,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            
            Spacer(modifier = Modifier.height(4.dp))
            
            // Indication cliquer pour détails
            Text(
                "Cliquer pour voir tous les résultats",
                fontSize = 11.sp,
                color = Color.Gray,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun LotChip(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, fontSize = 10.sp, color = Color.Gray)
        Surface(
            shape = RoundedCornerShape(8.dp),
            color = color.copy(alpha = 0.2f)
        ) {
            Text(
                value,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                fontWeight = FontWeight.Bold,
                fontSize = 24.sp,
                color = color.copy(alpha = 1f)
            )
        }
    }
}

@Composable
private fun ResultatDetailDialog(
    resultat: ResultatTirage,
    onDismiss: () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp)
        ) {
            Column(
                modifier = Modifier.padding(20.dp)
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            resultat.tirageNom,
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp
                        )
                        Text("${resultat.date} · ${resultat.heureTirage}", fontSize = 12.sp, color = Color.Gray)
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(Icons.Default.Close, contentDescription = "Fermer")
                    }
                }
                
                Divider(modifier = Modifier.padding(vertical = 12.dp))
                
                // BOULES (3 lots)
                Text("BOULES", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Color.Gray)
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    ResultatItem("1er Lot", resultat.lot1, Color(0xFFFFD700))
                    ResultatItem("2ème Lot", resultat.lot2, Color(0xFFC0C0C0))
                    ResultatItem("3ème Lot", resultat.lot3, Color(0xFFCD7F32))
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // LOTO3
                Text("LOTO 3", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Color.Gray)
                Spacer(modifier = Modifier.height(8.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                    ResultatItem("Loto3", resultat.loto3, MaterialTheme.colorScheme.primary)
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // LOTO4 (3 options)
                Text("LOTO 4", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Color.Gray)
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    ResultatItem("Option 1", resultat.loto4Opt1, Color(0xFF2196F3))
                    ResultatItem("Option 2", resultat.loto4Opt2, Color(0xFF2196F3))
                    ResultatItem("Option 3", resultat.loto4Opt3, Color(0xFF2196F3))
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // LOTO5 (3 options)
                Text("LOTO 5", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Color.Gray)
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    ResultatItem("Option 1", resultat.loto5Opt1, Color(0xFF9C27B0))
                    ResultatItem("Option 2", resultat.loto5Opt2, Color(0xFF9C27B0))
                    ResultatItem("Option 3", resultat.loto5Opt3, Color(0xFF9C27B0))
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // Bouton fermer
                Button(
                    onClick = onDismiss,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Fermer")
                }
            }
        }
    }
}

@Composable
private fun ResultatItem(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, fontSize = 10.sp, color = Color.Gray)
        Text(
            value,
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            color = color
        )
    }
}
