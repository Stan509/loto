package com.gaboom.agent.ui.screens.vente

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.compose.foundation.Image
import coil.compose.AsyncImage
import com.gaboom.agent.util.QrCodeImage
import com.gaboom.agent.util.TicketShareUtil
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VenteScreen(
    tirageId: Int? = null,
    defaultTirageNom: String? = null,
    blueprintTicketId: String? = null,
    onBack: () -> Unit,
    onTicketCreated: () -> Unit,
    viewModel: VenteViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val sheetState = rememberModalBottomSheetState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    
    // State for bottom sheet and dropdowns
    var showTirageSheet by remember { mutableStateOf(false) }
    var showSettingsMenu by remember { mutableStateOf(false) }
    var showAutomationsMenu by remember { mutableStateOf(false) }
    var showLotoOptionsMenu by remember { mutableStateOf(false) }
    var showPrintPreview by remember { mutableStateOf(false) }
    var showShareDialog by remember { mutableStateOf(false) }

    // Init with default tirage pre-selected or blueprint if provided
    LaunchedEffect(Unit) {
        if (tirageId != null) {
            viewModel.setDefaultTirage(tirageId, defaultTirageNom ?: "")
        }
        if (blueprintTicketId != null) {
            viewModel.loadBlueprint(blueprintTicketId)
        }
    }

    var selectedJeu by remember { mutableStateOf("boule") }
    var numero by remember { mutableStateOf("") }
    var miseDefaut by remember { mutableStateOf("50") }
    var editingIndex by remember { mutableStateOf<Int?>(null) }
    var editingMise by remember { mutableStateOf("") }
    var editingOptionIndex by remember { mutableStateOf<Int?>(null) }
    var inputError by remember { mutableStateOf<String?>(null) }

    // Validation et formatage selon le type de jeu
    fun validateAndFormat(jeu: String, value: String): String? {
        val cleaned = value.uppercase().replace(" ", "")
        return when (jeu) {
            "boule" -> {
                val digits = cleaned.filter { it.isDigit() }.take(2)
                if (digits.length == 2) digits else null
            }
            "mariage" -> {
                val digits = cleaned.filter { it.isDigit() }
                if (digits.length == 4) {
                    "${digits.substring(0, 2)}x${digits.substring(2, 4)}"
                } else if (cleaned.contains("X") || cleaned.contains("-")) {
                    val parts = cleaned.split("X", "-")
                    if (parts.size == 2 && parts[0].length == 2 && parts[1].length == 2) {
                        "${parts[0]}x${parts[1]}"
                    } else null
                } else null
            }
            "loto3" -> {
                val digits = cleaned.filter { it.isDigit() }.take(3)
                if (digits.length == 3) digits else null
            }
            "loto4" -> {
                val digits = cleaned.filter { it.isDigit() }.take(4)
                if (digits.length == 4) digits else null
            }
            "loto5" -> {
                val digits = cleaned.filter { it.isDigit() }.take(5)
                if (digits.length == 5) digits else null
            }
            else -> null
        }
    }

    fun getMaxLength(jeu: String): Int = when (jeu) {
        "boule" -> 2
        "mariage" -> 5
        "loto3" -> 3
        "loto4" -> 4
        "loto5" -> 5
        else -> 10
    }

    fun getPlaceholder(jeu: String): String = when (jeu) {
        "boule" -> "33"
        "mariage" -> "44x35"
        "loto3" -> "547"
        "loto4" -> "7864"
        "loto5" -> "45675"
        else -> ""
    }

    LaunchedEffect(uiState.ticketCreated, uiState.ticketToShare) {
        // Ne pas naviguer si on attend le partage
        if (uiState.ticketCreated && uiState.ticketToShare == null) {
            onTicketCreated()
        }
    }

    // Bottom Sheet for Tirage Selection
    if (showTirageSheet) {
        ModalBottomSheet(
            onDismissRequest = { showTirageSheet = false },
            sheetState = sheetState
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Sélection des Tirages", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Row {
                        TextButton(onClick = { viewModel.selectAllTirages() }) {
                            Text("Tout", fontSize = 12.sp)
                        }
                        TextButton(onClick = { viewModel.clearAllTirages() }) {
                            Text("Aucun", fontSize = 12.sp, color = Color.Red)
                        }
                    }
                }
                
                Divider(modifier = Modifier.padding(vertical = 8.dp))
                
                if (uiState.isLoadingTirages) {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                        Text("Chargement...", color = Color.Gray)
                    }
                } else if (uiState.availableTirages.isEmpty()) {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                        Text("Aucun tirage disponible", color = Color.Gray)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.heightIn(max = 300.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        itemsIndexed(uiState.availableTirages) { _, tirage ->
                            val isOpen = tirage.etat == "OUVERT"
                            val isSelected = uiState.selectedTirageIds.contains(tirage.id)
                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable(enabled = isOpen) { viewModel.toggleTirageSelection(tirage.id) },
                                color = if (isSelected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f) 
                                       else Color.Transparent
                            ) {
                                Row(
                                    modifier = Modifier.padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Checkbox(
                                        checked = isSelected,
                                        onCheckedChange = { if (isOpen) viewModel.toggleTirageSelection(tirage.id) },
                                        enabled = isOpen,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Spacer(modifier = Modifier.width(12.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            tirage.nom,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                            color = if (isOpen) Color.Unspecified else Color.Gray.copy(alpha = 0.5f)
                                        )
                                        if (!isOpen) {
                                            Text("Fermé", fontSize = 11.sp, color = Color.Red.copy(alpha = 0.7f))
                                        }
                                    }
                                    Text(
                                        tirage.heureTirage,
                                        fontSize = 13.sp,
                                        color = if (isSelected) MaterialTheme.colorScheme.primary else Color.Gray
                                    )
                                }
                            }
                        }
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Button(
                    onClick = { 
                        scope.launch { sheetState.hide() }.invokeOnCompletion {
                            showTirageSheet = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Valider (${uiState.selectedTirageIds.size} sélectionné(s))")
                }
                
                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Vente Ticket") },
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
                .padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            // ═══════════════════════════════════════════════════════════
            // HEADER: Logo + Borlette Info
            // ═══════════════════════════════════════════════════════════
            if (uiState.borletteLogoUrl.isNotBlank() || uiState.borletteName.isNotBlank()) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    if (uiState.borletteLogoUrl.isNotBlank()) {
                        AsyncImage(
                            model = uiState.borletteLogoUrl,
                            contentDescription = "Logo",
                            modifier = Modifier
                                .size(40.dp)
                                .clip(RoundedCornerShape(8.dp))
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                    }
                    Column {
                        Text(
                            uiState.borletteName.ifEmpty { "GABOOM BORLETTE" },
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                        if (uiState.borletteSlogan.isNotBlank()) {
                            Text(
                                uiState.borletteSlogan,
                                fontSize = 10.sp,
                                color = Color.Gray
                            )
                        }
                    }
                }
                Divider(modifier = Modifier.padding(bottom = 6.dp))
            }
            
            // ═══════════════════════════════════════════════════════════
            // TOP BAR: Multi-Tirage Toggle + Mise Défaut
            // ═══════════════════════════════════════════════════════════
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        if (uiState.multiTirageMode) "Multi" else "Direct", 
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp,
                        color = if (uiState.multiTirageMode) MaterialTheme.colorScheme.primary else Color.Gray
                    )
                    Switch(
                        checked = uiState.multiTirageMode,
                        onCheckedChange = { viewModel.toggleMultiTirageMode(it) },
                        modifier = Modifier.scale(0.7f)
                    )
                }
                
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Mise:", fontSize = 11.sp, color = Color.Gray)
                    Spacer(modifier = Modifier.width(4.dp))
                    OutlinedTextField(
                        value = miseDefaut,
                        onValueChange = { if (it.all { c -> c.isDigit() }) miseDefaut = it },
                        modifier = Modifier.width(70.dp).height(48.dp),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        textStyle = LocalTextStyle.current.copy(fontSize = 14.sp, textAlign = TextAlign.Center)
                    )
                }
            }

            // ═══════════════════════════════════════════════════════════
            // MULTI-TIRAGE: Compact Summary + Modifier Button
            // ═══════════════════════════════════════════════════════════
            if (uiState.multiTirageMode) {
                Spacer(modifier = Modifier.height(6.dp))
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { showTirageSheet = true },
                    color = if (uiState.selectedTirageIds.isEmpty()) 
                            MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
                           else MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                ) {
                    Row(
                        modifier = Modifier.padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.DateRange, 
                            contentDescription = null, 
                            modifier = Modifier.size(18.dp),
                            tint = if (uiState.selectedTirageIds.isEmpty()) MaterialTheme.colorScheme.error 
                                   else MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            if (uiState.selectedTirageIds.isEmpty()) {
                                Text(
                                    "Sélectionnez au moins un tirage",
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.error
                                )
                            } else {
                                val selectedNames = uiState.availableTirages
                                    .filter { it.id in uiState.selectedTirageIds }
                                    .take(3)
                                    .joinToString(", ") { "${it.nom} ${it.heureTirage}" }
                                val suffix = if (uiState.selectedTirageIds.size > 3) "..." else ""
                                Text(
                                    "$selectedNames$suffix",
                                    fontSize = 11.sp,
                                    maxLines = 1,
                                    color = Color.Unspecified
                                )
                                Text(
                                    "${uiState.selectedTirageIds.size} tirage(s)",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                        Icon(
                            Icons.Default.Edit, 
                            contentDescription = "Modifier",
                            modifier = Modifier.size(16.dp),
                            tint = Color.Gray
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ═══════════════════════════════════════════════════════════
            // GAME TABS
            // ═══════════════════════════════════════════════════════════
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                listOf("boule", "mariage", "loto3", "loto4", "loto5").forEach { jeu ->
                    FilterChip(
                        selected = selectedJeu == jeu,
                        onClick = { 
                            selectedJeu = jeu
                            numero = ""
                            inputError = null
                        },
                        label = { Text(jeu.uppercase(), fontSize = 9.sp) },
                        modifier = Modifier.height(30.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ═══════════════════════════════════════════════════════════
            // INPUT: Number + Add Button
            // ═══════════════════════════════════════════════════════════
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = numero,
                    onValueChange = { newValue ->
                        val maxLen = getMaxLength(selectedJeu)
                        val filtered = if (selectedJeu == "mariage") {
                            newValue.filter { it.isDigit() || it == 'x' || it == 'X' }.take(maxLen)
                        } else {
                            newValue.filter { it.isDigit() }.take(maxLen)
                        }
                        numero = filtered
                        inputError = null
                    },
                    placeholder = { Text(getPlaceholder(selectedJeu), color = Color.Gray) },
                    modifier = Modifier.weight(1f).height(52.dp),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    isError = inputError != null,
                    textStyle = LocalTextStyle.current.copy(fontSize = 18.sp, fontWeight = FontWeight.Bold)
                )
                Button(
                    onClick = {
                        val validated = validateAndFormat(selectedJeu, numero)
                        if (validated != null) {
                            val mise = miseDefaut.toDoubleOrNull() ?: 50.0
                            val error = viewModel.addLine(selectedJeu, validated, mise)
                            if (error == null) {
                                numero = ""
                                inputError = null
                            } else {
                                inputError = error
                            }
                        } else {
                            inputError = "Format invalide"
                        }
                    },
                    enabled = numero.isNotBlank(),
                    modifier = Modifier.size(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    contentPadding = PaddingValues(0.dp)
                ) {
                    Icon(Icons.Default.Add, contentDescription = "Ajouter", modifier = Modifier.size(28.dp))
                }
            }

            if (inputError != null) {
                Text(inputError!!, color = Color.Red, fontSize = 11.sp)
            }

            Spacer(modifier = Modifier.height(6.dp))

            // ═══════════════════════════════════════════════════════════
            // SETTINGS BUTTON (Dropdowns for Automations + Loto Options)
            // ═══════════════════════════════════════════════════════════
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Automations Dropdown
                Box {
                    Surface(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .clickable { showAutomationsMenu = true },
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("Automations", fontSize = 11.sp)
                            // Show badge if any automation is active
                            val activeCount = listOf(
                                uiState.autoMariageEnabled,
                                uiState.autoLoto4Enabled,
                                uiState.freeMariageChecked
                            ).count { it }
                            if (activeCount > 0) {
                                Spacer(modifier = Modifier.width(4.dp))
                                Surface(
                                    shape = RoundedCornerShape(10.dp),
                                    color = MaterialTheme.colorScheme.primary
                                ) {
                                    Text(
                                        "$activeCount",
                                        fontSize = 9.sp,
                                        color = Color.White,
                                        modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp)
                                    )
                                }
                            }
                            Icon(Icons.Default.ArrowDropDown, contentDescription = null, modifier = Modifier.size(16.dp))
                        }
                    }
                    
                    DropdownMenu(
                        expanded = showAutomationsMenu,
                        onDismissRequest = { showAutomationsMenu = false }
                    ) {
                        DropdownMenuItem(
                            text = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Checkbox(
                                        checked = uiState.autoMariageEnabled,
                                        onCheckedChange = null,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Mariage auto (nC2)")
                                }
                            },
                            onClick = { 
                                viewModel.toggleAutoMariage(!uiState.autoMariageEnabled, miseDefaut.toDoubleOrNull() ?: 50.0)
                            }
                        )
                        DropdownMenuItem(
                            text = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Checkbox(
                                        checked = uiState.autoLoto4Enabled,
                                        onCheckedChange = null,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Loto4 auto (nP2)")
                                }
                            },
                            onClick = { 
                                viewModel.toggleAutoLoto4(!uiState.autoLoto4Enabled, miseDefaut.toDoubleOrNull() ?: 50.0)
                            }
                        )
                        if (uiState.freeMariageEnabled) {
                            Divider()
                            DropdownMenuItem(
                                text = {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Checkbox(
                                            checked = uiState.freeMariageChecked,
                                            onCheckedChange = null,
                                            modifier = Modifier.size(20.dp)
                                        )
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Column {
                                            Text("Mariage Gratuit", color = Color(0xFF10B981))
                                            Text("Mise = 0", fontSize = 10.sp, color = Color.Gray)
                                        }
                                    }
                                },
                                onClick = { viewModel.toggleFreeMariage(!uiState.freeMariageChecked) }
                            )
                        }
                    }
                }
                
                // Loto Options Dropdown
                Box {
                    Surface(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .clickable { showLotoOptionsMenu = true },
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("Options Loto", fontSize = 11.sp)
                            Spacer(modifier = Modifier.width(4.dp))
                            // Show current options summary
                            val l4Summary = if (uiState.globalLoto4Options.size == 3) "F" else uiState.globalLoto4Options.sorted().joinToString("")
                            val l5Summary = if (uiState.globalLoto5Options.size == 3) "F" else uiState.globalLoto5Options.sorted().joinToString("")
                            Text("L4:$l4Summary L5:$l5Summary", fontSize = 9.sp, color = MaterialTheme.colorScheme.primary)
                            Icon(Icons.Default.ArrowDropDown, contentDescription = null, modifier = Modifier.size(16.dp))
                        }
                    }
                    
                    DropdownMenu(
                        expanded = showLotoOptionsMenu,
                        onDismissRequest = { showLotoOptionsMenu = false },
                        modifier = Modifier.width(260.dp)
                    ) {
                        // Loto4 Section
                        Text("LOTO4 Options", fontWeight = FontWeight.Bold, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            FilterChip(
                                selected = uiState.globalLoto4Options.size == 3,
                                onClick = { viewModel.setLoto4Full(uiState.globalLoto4Options.size != 3) },
                                label = { Text("FULL", fontSize = 10.sp) },
                                modifier = Modifier.height(28.dp)
                            )
                            listOf(1, 2, 3).forEach { opt ->
                                FilterChip(
                                    selected = uiState.globalLoto4Options.contains(opt),
                                    onClick = { viewModel.toggleLoto4Option(opt) },
                                    label = { Text("$opt", fontSize = 10.sp) },
                                    modifier = Modifier.height(28.dp)
                                )
                            }
                        }
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Checkbox(
                                checked = uiState.applyGlobalToAllLoto4,
                                onCheckedChange = { viewModel.toggleApplyGlobalToAllLoto4(it) },
                                modifier = Modifier.size(18.dp)
                            )
                            Text("Appliquer à tous les Loto4", fontSize = 10.sp)
                        }
                        
                        Divider(modifier = Modifier.padding(vertical = 4.dp))
                        
                        // Loto5 Section
                        Text("LOTO5 Options", fontWeight = FontWeight.Bold, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            FilterChip(
                                selected = uiState.globalLoto5Options.size == 3,
                                onClick = { viewModel.setLoto5Full(uiState.globalLoto5Options.size != 3) },
                                label = { Text("FULL", fontSize = 10.sp) },
                                modifier = Modifier.height(28.dp)
                            )
                            listOf(1, 2, 3).forEach { opt ->
                                FilterChip(
                                    selected = uiState.globalLoto5Options.contains(opt),
                                    onClick = { viewModel.toggleLoto5Option(opt) },
                                    label = { Text("$opt", fontSize = 10.sp) },
                                    modifier = Modifier.height(28.dp)
                                )
                            }
                        }
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Checkbox(
                                checked = uiState.applyGlobalToAllLoto5,
                                onCheckedChange = { viewModel.toggleApplyGlobalToAllLoto5(it) },
                                modifier = Modifier.size(18.dp)
                            )
                            Text("Appliquer à tous les Loto5", fontSize = 10.sp)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ═══════════════════════════════════════════════════════════
            // LINES LIST (Compact)
            // ═══════════════════════════════════════════════════════════
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Lignes (${uiState.lines.size})", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                if (uiState.lines.isNotEmpty()) {
                    TextButton(
                        onClick = { /* Could add clear all */ },
                        contentPadding = PaddingValues(horizontal = 8.dp)
                    ) {
                        Text("Tap mise pour éditer", fontSize = 9.sp, color = Color.Gray)
                    }
                }
            }

            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                itemsIndexed(uiState.lines) { index, line ->
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(6.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 10.dp, vertical = 6.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // Left: Game type + value + options
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                // Game badge
                                Surface(
                                    shape = RoundedCornerShape(4.dp),
                                    color = when (line.jeu.lowercase()) {
                                        "boule" -> Color(0xFF3B82F6).copy(alpha = 0.2f)
                                        "mariage" -> Color(0xFFEC4899).copy(alpha = 0.2f)
                                        "loto3" -> Color(0xFF8B5CF6).copy(alpha = 0.2f)
                                        "loto4" -> Color(0xFFF59E0B).copy(alpha = 0.2f)
                                        "loto5" -> Color(0xFF10B981).copy(alpha = 0.2f)
                                        else -> Color.Gray.copy(alpha = 0.2f)
                                    }
                                ) {
                                    Text(
                                        line.jeu.uppercase().take(3),
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
                                        color = when (line.jeu.lowercase()) {
                                            "boule" -> Color(0xFF3B82F6)
                                            "mariage" -> Color(0xFFEC4899)
                                            "loto3" -> Color(0xFF8B5CF6)
                                            "loto4" -> Color(0xFFF59E0B)
                                            "loto5" -> Color(0xFF10B981)
                                            else -> Color.Gray
                                        }
                                    )
                                }
                                
                                // Show option badge for Loto4/Loto5 - clickable to change
                                val isLoto = line.jeu.lowercase() in listOf("loto4", "loto5")
                                if (isLoto && line.options.isNotEmpty()) {
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Box {
                                        Surface(
                                            shape = RoundedCornerShape(4.dp),
                                            color = Color(0xFF4CAF50),
                                            modifier = Modifier.clickable { editingOptionIndex = index }
                                        ) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                            ) {
                                                Text(
                                                    "Opt ${line.options.first()}",
                                                    fontSize = 10.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = Color.White
                                                )
                                                Icon(
                                                    Icons.Default.ArrowDropDown,
                                                    contentDescription = null,
                                                    tint = Color.White,
                                                    modifier = Modifier.size(14.dp)
                                                )
                                            }
                                        }
                                        
                                        // Dropdown menu to change or add option
                                        DropdownMenu(
                                            expanded = editingOptionIndex == index,
                                            onDismissRequest = { editingOptionIndex = null }
                                        ) {
                                            // Change current option
                                            Text(
                                                "Changer en:",
                                                fontSize = 12.sp,
                                                color = Color.Gray,
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                                            )
                                            listOf(1, 2, 3).forEach { opt ->
                                                DropdownMenuItem(
                                                    text = { 
                                                        Text(
                                                            "Option $opt",
                                                            fontWeight = if (line.options.first() == opt) FontWeight.Bold else FontWeight.Normal
                                                        )
                                                    },
                                                    onClick = {
                                                        viewModel.updateLineOptions(index, setOf(opt))
                                                        editingOptionIndex = null
                                                    },
                                                    leadingIcon = {
                                                        if (line.options.first() == opt) {
                                                            Icon(Icons.Default.Check, contentDescription = null, tint = Color(0xFF4CAF50))
                                                        }
                                                    }
                                                )
                                            }
                                            
                                            Divider()
                                            
                                            // Add new option line for same number
                                            Text(
                                                "Ajouter option:",
                                                fontSize = 12.sp,
                                                color = Color.Gray,
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                                            )
                                            val currentOpt = line.options.first()
                                            listOf(1, 2, 3).filter { it != currentOpt }.forEach { opt ->
                                                DropdownMenuItem(
                                                    text = { Text("+ Option $opt") },
                                                    onClick = {
                                                        viewModel.addOptionLine(line.jeu, line.valeur, line.miseBase, opt)
                                                        editingOptionIndex = null
                                                    },
                                                    leadingIcon = {
                                                        Icon(Icons.Default.Add, contentDescription = null, tint = Color(0xFF2196F3))
                                                    }
                                                )
                                            }
                                        }
                                    }
                                }
                                
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    line.valeur,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 15.sp
                                )
                            }
                            
                            // Right: Mise + Delete
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (editingIndex == index) {
                                    OutlinedTextField(
                                        value = editingMise,
                                        onValueChange = { if (it.all { c -> c.isDigit() }) editingMise = it },
                                        modifier = Modifier.width(60.dp).height(36.dp),
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                        singleLine = true,
                                        textStyle = LocalTextStyle.current.copy(fontSize = 12.sp)
                                    )
                                    IconButton(
                                        onClick = {
                                            val newMise = editingMise.toDoubleOrNull() ?: line.miseBase
                                            viewModel.updateLineMise(index, newMise)
                                            editingIndex = null
                                        },
                                        modifier = Modifier.size(28.dp)
                                    ) {
                                        Icon(Icons.Default.Check, contentDescription = "OK", tint = Color(0xFF4CAF50), modifier = Modifier.size(16.dp))
                                    }
                                } else {
                                    Surface(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(4.dp))
                                            .clickable {
                                                editingIndex = index
                                                editingMise = line.miseBase.toInt().toString()
                                            },
                                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.1f)
                                    ) {
                                        Text(
                                            "${line.effectiveMise.toInt()}",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.primary,
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                                        )
                                    }
                                }
                                IconButton(
                                    onClick = { viewModel.removeLine(index) },
                                    modifier = Modifier.size(28.dp)
                                ) {
                                    Icon(Icons.Default.Close, contentDescription = "Supprimer", tint = Color.Red.copy(alpha = 0.7f), modifier = Modifier.size(16.dp))
                                }
                            }
                        }
                    }
                }
            }

            // ═══════════════════════════════════════════════════════════
            // TOTAL + CONFIRM BUTTON
            // ═══════════════════════════════════════════════════════════
            Divider(modifier = Modifier.padding(vertical = 6.dp))

            val totalMise = uiState.lines.sumOf { it.effectiveMise }
            val totalBets = uiState.lines.sumOf { 
                if (it.options.isEmpty()) 1 else it.options.size 
            }
            val finalTotal = if (uiState.multiTirageMode) totalMise * uiState.selectedTirageIds.size else totalMise

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f),
                        RoundedCornerShape(10.dp)
                    )
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        "${finalTotal.toInt()} HTG",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("$totalBets paris", fontSize = 10.sp, color = Color.Gray)
                        if (uiState.multiTirageMode && uiState.selectedTirageIds.isNotEmpty()) {
                            Text(" × ${uiState.selectedTirageIds.size} tirages", fontSize = 10.sp, color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Error
            if (uiState.error != null) {
                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
            }

            // Multi-tirage progress
            if (uiState.creationProgress != null) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            uiState.creationProgress!!,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium
                        )
                        if (uiState.printError != null) {
                            Row {
                                IconButton(onClick = { viewModel.retryPrintMulti() }) {
                                    Icon(Icons.Default.Refresh, contentDescription = "Retry", modifier = Modifier.size(20.dp))
                                }
                                IconButton(onClick = { viewModel.skipPrintMulti() }) {
                                    Icon(Icons.Default.ArrowForward, contentDescription = "Skip", modifier = Modifier.size(20.dp))
                                }
                            }
                        }
                    }
                }
            }

            // Print error for multi-tirage
            if (uiState.printError != null && uiState.creationProgress == null) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 8.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            uiState.printError!!,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.error
                        )
                        Row {
                            TextButton(onClick = { viewModel.retryPrintMulti() }) {
                                Text("Réessayer", fontSize = 11.sp)
                            }
                            TextButton(onClick = { viewModel.skipPrintMulti() }) {
                                Text("Passer", fontSize = 11.sp)
                            }
                        }
                    }
                }
            }

            // Row 1: Preview + Share buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Preview Button
                OutlinedButton(
                    onClick = { showPrintPreview = true },
                    modifier = Modifier.weight(1f).height(44.dp),
                    enabled = uiState.lines.isNotEmpty() && !uiState.isLoading
                ) {
                    Icon(Icons.Default.Visibility, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Aperçu", fontSize = 12.sp)
                }
                
                // Save & Share Button
                OutlinedButton(
                    onClick = {
                        if (uiState.multiTirageMode) {
                            viewModel.createAndShareMultiTickets()
                        } else if (tirageId != null) {
                            viewModel.createAndShareTicket(tirageId)
                        }
                    },
                    modifier = Modifier.weight(1f).height(44.dp),
                    enabled = uiState.lines.isNotEmpty() 
                        && !uiState.isLoading
                        && (if (uiState.multiTirageMode) uiState.selectedTirageIds.isNotEmpty() else tirageId != null),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.secondary
                    )
                ) {
                    Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Enreg. & Partager", fontSize = 11.sp)
                }
            }
            
            Spacer(modifier = Modifier.height(6.dp))
            
            // Row 2: Create/Print Button
            Button(
                onClick = {
                    showPrintPreview = true
                },
                modifier = Modifier.fillMaxWidth().height(50.dp),
                enabled = uiState.lines.isNotEmpty() 
                    && !uiState.isLoading
                    && (if (uiState.multiTirageMode) uiState.selectedTirageIds.isNotEmpty() else tirageId != null)
            ) {
                Icon(Icons.Default.Print, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    when {
                        uiState.isLoading -> if (uiState.multiTirageMode) "Création..." else "Envoi..."
                        uiState.multiTirageMode -> "Créer ${uiState.selectedTirageIds.size} Ticket(s)"
                        else -> "Confirmer & Imprimer"
                    },
                    fontSize = 13.sp
                )
            }
        }
    }
    
    // Print Preview Dialog
    if (showPrintPreview) {
        val tiragesNames = if (uiState.multiTirageMode) {
            uiState.availableTirages.filter { it.id in uiState.selectedTirageIds }.map { it.nom }
        } else {
            listOfNotNull(defaultTirageNom ?: uiState.availableTirages.find { it.id == tirageId }?.nom)
        }
        
        AlertDialog(
            onDismissRequest = { showPrintPreview = false },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Visibility, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Aperçu Impression", fontWeight = FontWeight.Bold)
                }
            },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 350.dp)
                            .background(Color(0xFFFFFBE6), RoundedCornerShape(8.dp))
                            .verticalScroll(rememberScrollState())
                            .padding(12.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        // Logo
                        if (uiState.borletteLogoUrl.isNotBlank()) {
                            AsyncImage(
                                model = uiState.borletteLogoUrl,
                                contentDescription = "Logo",
                                modifier = Modifier
                                    .size(60.dp)
                                    .clip(RoundedCornerShape(8.dp))
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                        }
                        
                        // Header - Borlette Info
                        Text(
                            uiState.borletteName.ifEmpty { "GABOOM BORLETTE" },
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                        if (uiState.borletteSlogan.isNotBlank()) {
                            Text(
                                uiState.borletteSlogan,
                                fontSize = 11.sp,
                                modifier = Modifier.fillMaxWidth(),
                                textAlign = TextAlign.Center,
                                color = Color.Gray
                            )
                        }
                        if (uiState.borletteAdresse.isNotBlank()) {
                            Text(
                                uiState.borletteAdresse,
                                fontSize = 10.sp,
                                modifier = Modifier.fillMaxWidth(),
                                textAlign = TextAlign.Center
                            )
                        }
                        if (uiState.borletteTel.isNotBlank()) {
                            Text(
                                "Tel: ${uiState.borletteTel}",
                                fontSize = 11.sp,
                                modifier = Modifier.fillMaxWidth(),
                                textAlign = TextAlign.Center
                            )
                        }
                        
                        Spacer(modifier = Modifier.height(8.dp))
                        
                        // QR Code placeholder (group_id sera généré à la création)
                        val previewQrContent = remember { "GABOOM-PREVIEW-${System.currentTimeMillis()}" }
                        QrCodeImage(
                            content = previewQrContent,
                            size = 80.dp
                        )
                        Text(
                            "QR Code Groupe",
                            fontSize = 9.sp,
                            color = Color.Gray
                        )
                        
                        Spacer(modifier = Modifier.height(4.dp))
                        
                        Text(
                            "--------------------------------",
                            fontSize = 10.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        
                        // Ticket info
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Text("Ticket: #PREVIEW", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                            Text("Date: ${java.time.LocalDate.now()}  ${java.time.LocalTime.now().toString().take(5)}", fontSize = 11.sp)
                            if (uiState.agentName.isNotBlank()) {
                                Text("Agent: ${uiState.agentName}", fontSize = 11.sp)
                            }
                            Text("Tirage(s): ${tiragesNames.joinToString(", ")}", fontSize = 11.sp)
                        }
                        
                        Text(
                            "--------------------------------",
                            fontSize = 10.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                        )
                        
                        // Lines header
                        Text(
                            "JEU      NUMERO    MISE",
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                        )
                        
                        // Lines
                        uiState.lines.forEach { line ->
                            val isLoto = line.jeu.lowercase() in listOf("loto4", "loto5")
                            val optNum = if (isLoto && line.options.isNotEmpty()) line.options.first() else null
                            val jeuDisplay = if (optNum != null) "${line.jeu.uppercase()}-$optNum" else line.jeu.uppercase()
                            
                            Text(
                                String.format("%-8s %-9s %6.0f", jeuDisplay, line.valeur, line.miseBase),
                                fontSize = 11.sp,
                                fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                            )
                        }
                        
                        Text(
                            "--------------------------------",
                            fontSize = 10.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                        )
                        
                        // Total (mise × nombre de tirages)
                        val miseParTicket = uiState.lines.sumOf { it.miseBase }
                        val nbTirages = if (uiState.multiTirageMode) uiState.selectedTirageIds.size.coerceAtLeast(1) else 1
                        val totalGlobal = miseParTicket * nbTirages
                        
                        if (nbTirages > 1) {
                            Text(
                                "Mise/ticket: ${String.format("%.0f", miseParTicket)} HTG",
                                fontSize = 11.sp
                            )
                            Text(
                                "× $nbTirages tirages",
                                fontSize = 11.sp
                            )
                        }
                        Text(
                            "TOTAL: ${String.format("%.0f", totalGlobal)} HTG",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                        
                        Text(
                            "--------------------------------",
                            fontSize = 10.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
                        )
                        
                        // Footer
                        if (uiState.ticketFooterText.isNotBlank()) {
                            Text(
                                uiState.ticketFooterText,
                                fontSize = 9.sp,
                                color = Color.Gray,
                                modifier = Modifier.fillMaxWidth(),
                                textAlign = TextAlign.Center,
                                lineHeight = 12.sp
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                        }
                        Text(
                            "Gaboom Borlette OS  www.gaboombos.com",
                            fontSize = 10.sp,
                            color = Color.Gray,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                        Text(
                            "--------------------------------",
                            fontSize = 10.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                        Text(
                            "Bonne chance",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                        Text(
                            "Merci pour votre confiance",
                            fontSize = 11.sp,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (uiState.multiTirageMode) {
                            viewModel.createMultiTickets()
                        } else if (tirageId != null) {
                            viewModel.createTicket(tirageId)
                        }
                        showPrintPreview = false
                    }
                ) {
                    Text("Confirmer & Imprimer")
                }
            },
            dismissButton = {
                TextButton(onClick = { showPrintPreview = false }) {
                    Text("Annuler")
                }
            }
        )
    }
    
    // Ticket Preview Dialog after ticket creation
    uiState.ticketToShare?.let { ticketInfo ->
        val previewScope = rememberCoroutineScope()
        var isSharingImage by remember { mutableStateOf(false) }
        var isSharingPdf by remember { mutableStateOf(false) }
        
        fun buildShareLines() = ticketInfo.lines.map {
            val parts = it.first.split(":")
            val jeu = parts.getOrElse(0) { "" }
            val optStr = parts.getOrElse(2) { "1" }
            val opt = if ((jeu.equals("LOTO4", true) || jeu.equals("LOTO5", true)) && optStr != "1") "OPT$optStr" else null
            TicketShareUtil.TicketLineData(
                jeu = jeu,
                valeur = parts.getOrElse(1) { "" },
                mise = it.second,
                option = opt
            )
        }
        
        fun buildShareData(logoBitmap: android.graphics.Bitmap? = null) = TicketShareUtil.TicketShareData(
            ticketNo = ticketInfo.ticketNo,
            tirageNom = ticketInfo.tirageNom,
            date = "${ticketInfo.date}  ${ticketInfo.time}",
            lines = buildShareLines(),
            totalMise = ticketInfo.totalMise,
            borletteName = ticketInfo.borletteName,
            borletteSlogan = ticketInfo.borletteSlogan,
            borletteTel = ticketInfo.borletteTel,
            borletteAdresse = ticketInfo.borletteAdresse,
            agentName = ticketInfo.agentName,
            qrCode = ticketInfo.groupId,
            logoBitmap = logoBitmap,
            ticketFooterText = ticketInfo.ticketFooterText,
            mariageGratuitActif = ticketInfo.mariageGratuitActif,
            mariageGratuitMontant = ticketInfo.mariageGratuitMontant
        )
        
        AlertDialog(
            onDismissRequest = {
                viewModel.clearTicketToShare()
                onTicketCreated()
            },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF4CAF50))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Ticket enregistré!", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                }
            },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // Ticket Preview Card (Compose text, scrollable, max height restricted)
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 280.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color(0xFFFFFBE6))
                            .verticalScroll(androidx.compose.foundation.rememberScrollState())
                            .padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        // Logo
                        if (ticketInfo.borletteLogoUrl.isNotBlank()) {
                            AsyncImage(
                                model = ticketInfo.borletteLogoUrl,
                                contentDescription = "Logo",
                                modifier = Modifier.size(48.dp),
                                contentScale = androidx.compose.ui.layout.ContentScale.Fit
                            )
                        }
                        if (ticketInfo.borletteName.isNotBlank()) {
                            Text(ticketInfo.borletteName, fontSize = 15.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                        }
                        if (ticketInfo.borletteSlogan.isNotBlank()) {
                            Text(ticketInfo.borletteSlogan, fontSize = 10.sp, color = Color.Gray, textAlign = TextAlign.Center)
                        }
                        if (ticketInfo.borletteAdresse.isNotBlank()) {
                            Text(ticketInfo.borletteAdresse, fontSize = 9.sp, color = Color.Gray, textAlign = TextAlign.Center)
                        }
                        if (ticketInfo.borletteTel.isNotBlank()) {
                            Text("Tel: ${ticketInfo.borletteTel}", fontSize = 10.sp, color = Color.Gray, textAlign = TextAlign.Center)
                        }
                        
                        Divider(modifier = Modifier.padding(vertical = 6.dp), color = Color.LightGray)
                        
                        Text("Ticket: #${ticketInfo.ticketNo}", fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.fillMaxWidth())
                        Text("Date: ${ticketInfo.date} ${ticketInfo.time}", fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
                        if (ticketInfo.agentName.isNotBlank()) {
                            Text("Agent: ${ticketInfo.agentName}", fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
                        }
                        Text("Tirage(s): ${ticketInfo.tirageNom}", fontSize = 11.sp, modifier = Modifier.fillMaxWidth())
                        
                        Divider(modifier = Modifier.padding(vertical = 6.dp), color = Color.LightGray)
                        
                        Row(modifier = Modifier.fillMaxWidth()) {
                            Text("JEU", fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.35f))
                            Text("NUMERO", fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.35f))
                            Text("MISE", fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.3f), textAlign = TextAlign.End)
                        }
                        ticketInfo.lines.forEach { line ->
                            val parts = line.first.split(":")
                            val jeuRaw = parts.getOrElse(0) { "" }
                            val valeur = parts.getOrElse(1) { "" }
                            val optStr = parts.getOrElse(2) { "1" }
                            val jeu = if ((jeuRaw.equals("LOTO4", true) || jeuRaw.equals("LOTO5", true)) && optStr != "1")
                                "${jeuRaw.uppercase()}-OPT$optStr" else jeuRaw.uppercase()
                            Row(modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp)) {
                                Text(jeu, fontSize = 10.sp, modifier = Modifier.weight(0.35f), fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                                Text(valeur, fontSize = 10.sp, modifier = Modifier.weight(0.35f), fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                                Text("${line.second.toInt()}", fontSize = 10.sp, modifier = Modifier.weight(0.3f), textAlign = TextAlign.End, fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                            }
                        }
                        
                        Divider(modifier = Modifier.padding(vertical = 6.dp), color = Color.LightGray)
                        Text("TOTAL: ${ticketInfo.totalMise.toInt()} HTG", fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.fillMaxWidth())
                        
                        if (ticketInfo.mariageGratuitActif) {
                            Divider(modifier = Modifier.padding(vertical = 6.dp), color = Color.LightGray)
                            Text("Mariage Gratuit ${ticketInfo.mariageGratuitMontant} Gdes", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFF1976D2), textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                        }
                        
                        Divider(modifier = Modifier.padding(vertical = 6.dp), color = Color.LightGray)
                        if (ticketInfo.ticketFooterText.isNotBlank()) {
                            Text(ticketInfo.ticketFooterText, fontSize = 9.sp, color = Color.Gray, textAlign = TextAlign.Center, lineHeight = 12.sp, modifier = Modifier.fillMaxWidth())
                            Spacer(modifier = Modifier.height(4.dp))
                        }
                        Text("Gaboom Borlette OS  www.gaboombos.com", fontSize = 9.sp, color = Color.Gray, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                        Divider(modifier = Modifier.padding(vertical = 4.dp), color = Color.LightGray)
                        Text("Bonne chance", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = Color.Gray, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                        Text("Merci pour votre confiance", fontSize = 10.sp, color = Color.Gray, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                    }
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    // Action buttons row (outside the scrollable card, always visible)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            IconButton(onClick = { viewModel.printLastTicket() }) {
                                Icon(Icons.Default.Print, contentDescription = "Imprimer", tint = Color(0xFF1976D2))
                            }
                            Text("Imprimer", fontSize = 10.sp, color = Color(0xFF1976D2))
                        }
                        
                        // Share as Image (generate on demand)
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            if (isSharingImage) {
                                CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
                            } else {
                                IconButton(onClick = {
                                    previewScope.launch {
                                        isSharingImage = true
                                        try {
                                            val logoBitmap = withContext(Dispatchers.IO) {
                                                if (ticketInfo.borletteLogoUrl.isNotBlank())
                                                    TicketShareUtil.downloadLogo(context, ticketInfo.borletteLogoUrl)
                                                else null
                                            }
                                            val shareData = buildShareData(logoBitmap)
                                            val bitmap = withContext(Dispatchers.IO) {
                                                TicketShareUtil.generateTicketImage(context, shareData)
                                            }
                                            TicketShareUtil.shareBitmapAsImage(context, bitmap, ticketInfo.ticketNo)
                                        } catch (_: Throwable) {
                                            // Silently fail
                                        } finally {
                                            isSharingImage = false
                                        }
                                    }
                                }) {
                                    Icon(Icons.Default.Image, contentDescription = "Partager Image", tint = Color(0xFF388E3C))
                                }
                            }
                            Text("Image", fontSize = 10.sp, color = Color(0xFF388E3C))
                        }
                        
                        // Share as Text (immediate, no bitmap)
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            IconButton(onClick = {
                                TicketShareUtil.shareAsText(context, buildShareData())
                            }) {
                                Icon(Icons.Default.Message, contentDescription = "Partager Texte", tint = Color(0xFFF57C00))
                            }
                            Text("Texte", fontSize = 10.sp, color = Color(0xFFF57C00))
                        }
                        
                        // Download as PDF (generate on demand)
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            if (isSharingPdf) {
                                CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
                            } else {
                                IconButton(onClick = {
                                    previewScope.launch {
                                        isSharingPdf = true
                                        try {
                                            val logoBitmap = withContext(Dispatchers.IO) {
                                                if (ticketInfo.borletteLogoUrl.isNotBlank())
                                                    TicketShareUtil.downloadLogo(context, ticketInfo.borletteLogoUrl)
                                                else null
                                            }
                                            val shareData = buildShareData(logoBitmap)
                                            val bitmap = withContext(Dispatchers.IO) {
                                                TicketShareUtil.generateTicketImage(context, shareData)
                                            }
                                            TicketShareUtil.saveAsPdf(context, bitmap, ticketInfo.ticketNo)
                                        } catch (_: Throwable) {
                                            // Silently fail
                                        } finally {
                                            isSharingPdf = false
                                        }
                                    }
                                }) {
                                    Icon(Icons.Default.PictureAsPdf, contentDescription = "PDF", tint = Color(0xFFD32F2F))
                                }
                            }
                            Text("PDF", fontSize = 10.sp, color = Color(0xFFD32F2F))
                        }
                    }
                }
            },
            confirmButton = {},
            dismissButton = {
                TextButton(onClick = {
                    viewModel.clearTicketToShare()
                    onTicketCreated()
                }) {
                    Text("Fermer")
                }
            }
        )
    }
}
