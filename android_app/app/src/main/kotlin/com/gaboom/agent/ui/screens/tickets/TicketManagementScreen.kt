package com.gaboom.agent.ui.screens.tickets

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gaboom.agent.data.model.TicketListItem
import com.gaboom.agent.data.model.TicketGroupItem
import com.gaboom.agent.ui.components.QrCodeScannerDialog
import com.gaboom.agent.util.TicketShareUtil
import kotlinx.coroutines.launch
import androidx.compose.ui.platform.LocalContext
import android.Manifest
import android.content.Intent
import android.widget.Toast
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TicketManagementScreen(
    onNavigateBack: () -> Unit,
    onScanQrCode: (() -> Unit)? = null,
    onRefaire: (String) -> Unit = { },
    viewModel: TicketManagementViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    val context = LocalContext.current
    
    var showDatePicker by remember { mutableStateOf(false) }
    var showShareDialog by remember { mutableStateOf<TicketListItem?>(null) }
    var isSharingLoading by remember { mutableStateOf(false) }
    var showTirageDropdown by remember { mutableStateOf(false) }
    var showStatusDropdown by remember { mutableStateOf(false) }
    var confirmPayTicket by remember { mutableStateOf<TicketListItem?>(null) }
    var confirmVoidTicket by remember { mutableStateOf<TicketListItem?>(null) }
    var showQrScanner by remember { mutableStateOf(false) }
    var showGroupResults by remember { mutableStateOf(false) }
    
    // Camera permission
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            showQrScanner = true
        } else {
            scope.launch {
                snackbarHostState.showSnackbar("Permission caméra refusée")
            }
        }
    }
    
    fun openQrScanner() {
        when {
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED -> {
                showQrScanner = true
            }
            else -> {
                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    // Show error/success messages
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }
    
    LaunchedEffect(uiState.successMessage) {
        uiState.successMessage?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearSuccessMessage()
        }
    }

    // Load more when reaching end of list
    LaunchedEffect(listState) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index }
            .collect { lastIndex ->
                if (lastIndex != null && lastIndex >= uiState.tickets.size - 5 && uiState.hasMore) {
                    viewModel.loadMore()
                }
            }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Gestion Tickets", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Retour")
                    }
                },
                actions = {
                    IconButton(onClick = { openQrScanner() }) {
                        Icon(Icons.Default.QrCodeScanner, contentDescription = "Scanner QR")
                    }
                    IconButton(onClick = { viewModel.loadTickets(refresh = true) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Actualiser")
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
        ) {
            // ═══════════════════════════════════════════════════════════════
            // SEARCH BAR
            // ═══════════════════════════════════════════════════════════════
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = uiState.searchQuery,
                    onValueChange = { viewModel.setSearchQuery(it) },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Rechercher par numéro ou ID", fontSize = 13.sp) },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, modifier = Modifier.size(20.dp)) },
                    trailingIcon = {
                        if (uiState.searchQuery.isNotEmpty()) {
                            IconButton(onClick = { 
                                viewModel.setSearchQuery("")
                                viewModel.loadTickets(refresh = true)
                            }) {
                                Icon(Icons.Default.Clear, contentDescription = "Effacer")
                            }
                        }
                    },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { viewModel.searchByQuery() }),
                    singleLine = true,
                    textStyle = LocalTextStyle.current.copy(fontSize = 14.sp)
                )
                
                Spacer(modifier = Modifier.width(8.dp))
                
                // QR Code scan button
                if (onScanQrCode != null) {
                    IconButton(
                        onClick = onScanQrCode,
                        modifier = Modifier
                            .size(48.dp)
                            .background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(8.dp))
                    ) {
                        Icon(
                            Icons.Default.QrCodeScanner,
                            contentDescription = "Scanner QR",
                            tint = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    }
                }
            }

            // ═══════════════════════════════════════════════════════════════
            // FILTERS ROW
            // ═══════════════════════════════════════════════════════════════
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Date filter
                Box {
                    FilterChip(
                        selected = uiState.selectedDate != null,
                        onClick = { showDatePicker = true },
                        label = {
                            Text(
                                uiState.selectedDate?.format(DateTimeFormatter.ofPattern("dd/MM")) ?: "Date",
                                fontSize = 11.sp
                            )
                        },
                        leadingIcon = {
                            Icon(Icons.Default.DateRange, contentDescription = null, modifier = Modifier.size(16.dp))
                        },
                        trailingIcon = if (uiState.selectedDate != null) {
                            {
                                Icon(
                                    Icons.Default.Clear,
                                    contentDescription = "Effacer",
                                    modifier = Modifier
                                        .size(16.dp)
                                        .clickable { viewModel.setDateFilter(null) }
                                )
                            }
                        } else null
                    )
                }

                // Tirage filter
                Box {
                    FilterChip(
                        selected = uiState.selectedTirageId != null,
                        onClick = { showTirageDropdown = true },
                        label = {
                            val tirageName = uiState.availableTirages.find { it.id == uiState.selectedTirageId }?.nom ?: "Tirage"
                            Text(tirageName.take(10), fontSize = 11.sp)
                        },
                        leadingIcon = {
                            Icon(Icons.Default.Casino, contentDescription = null, modifier = Modifier.size(16.dp))
                        }
                    )
                    
                    DropdownMenu(
                        expanded = showTirageDropdown,
                        onDismissRequest = { showTirageDropdown = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("Tous les tirages") },
                            onClick = {
                                viewModel.setTirageFilter(null)
                                showTirageDropdown = false
                            }
                        )
                        uiState.availableTirages.forEach { tirage ->
                            DropdownMenuItem(
                                text = { Text(tirage.nom) },
                                onClick = {
                                    viewModel.setTirageFilter(tirage.id)
                                    showTirageDropdown = false
                                }
                            )
                        }
                    }
                }

                // Status filter
                Box {
                    FilterChip(
                        selected = uiState.statusFilter != TicketStatusFilter.ALL,
                        onClick = { showStatusDropdown = true },
                        label = { Text(uiState.statusFilter.display, fontSize = 11.sp) },
                        leadingIcon = {
                            Icon(Icons.Default.FilterList, contentDescription = null, modifier = Modifier.size(16.dp))
                        }
                    )
                    
                    DropdownMenu(
                        expanded = showStatusDropdown,
                        onDismissRequest = { showStatusDropdown = false }
                    ) {
                        TicketStatusFilter.values().forEach { filter ->
                            DropdownMenuItem(
                                text = { Text(filter.display) },
                                onClick = {
                                    viewModel.setStatusFilter(filter)
                                    showStatusDropdown = false
                                }
                            )
                        }
                    }
                }
            }

            // ═══════════════════════════════════════════════════════════════
            // STATS SUMMARY
            // ═══════════════════════════════════════════════════════════════
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(8.dp)
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("${uiState.totalTickets}", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Text("Tickets", fontSize = 10.sp, color = Color.Gray)
                    }
                    val totalMise = uiState.tickets.sumOf { it.totalMise }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("${totalMise.toInt()} G", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Text("Total Misé", fontSize = 10.sp, color = Color.Gray)
                    }
                    val totalGains = uiState.tickets.filter { it.status == "won" || it.status == "paid" }.sumOf { it.totalGainDu }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("${totalGains.toInt()} G", fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Color(0xFF10B981))
                        Text("Gains", fontSize = 10.sp, color = Color.Gray)
                    }
                }
            }

            Divider(modifier = Modifier.padding(vertical = 4.dp))

            // ═══════════════════════════════════════════════════════════════
            // TICKETS LIST
            // ═══════════════════════════════════════════════════════════════
            if (uiState.isLoading && uiState.tickets.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Chargement...", fontSize = 14.sp, color = Color.Gray)
                }
            } else if (uiState.tickets.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Default.Receipt,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp),
                            tint = Color.Gray
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("Aucun ticket trouvé", color = Color.Gray)
                    }
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(uiState.tickets, key = { it.id }) { ticket ->
                        TicketCard(
                            ticket = ticket,
                            isPaying = uiState.payingTicketId == ticket.id,
                            isVoiding = uiState.voidingTicketId == ticket.id,
                            isReprinting = uiState.reprintingTicketId == ticket.id,
                            onPay = { confirmPayTicket = ticket },
                            onVoid = { confirmVoidTicket = ticket },
                            onReprint = { viewModel.reprintTicket(ticket.id) },
                            onShare = { showShareDialog = ticket },
                            onRefaire = { onRefaire(ticket.id) },
                            onModifier = {
                                scope.launch {
                                    val success = viewModel.voidTicketSync(ticket.id)
                                    if (success) {
                                        onRefaire(ticket.id)
                                    } else {
                                        snackbarHostState.showSnackbar("Échec de l'annulation du ticket pour modification")
                                    }
                                }
                            },
                            onViewPdf = {
                                scope.launch {
                                    val printData = viewModel.getTicketPrintData(ticket.id)
                                    if (printData != null) {
                                        val shareData = TicketShareUtil.fromPrintData(
                                            printData = printData,
                                            logoBitmap = null,
                                            totalGainDu = ticket.totalGainDu,
                                            isWinner = ticket.isWinner
                                        )
                                        TicketShareUtil.openTicketPdf(context, shareData)
                                    } else {
                                        snackbarHostState.showSnackbar("Erreur de récupération des données")
                                    }
                                }
                            }
                        )
                    }
                    
                    if (uiState.isLoading && uiState.tickets.isNotEmpty()) {
                        item {
                            Box(modifier = Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                                Text("Chargement...", fontSize = 12.sp, color = Color.Gray)
                            }
                        }
                    }
                }
            }
        }
    }

    // Date Picker Dialog
    if (showDatePicker) {
        val datePickerState = rememberDatePickerState(
            initialSelectedDateMillis = uiState.selectedDate?.toEpochDay()?.times(86400000)
        )
        DatePickerDialog(
            onDismissRequest = { showDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    datePickerState.selectedDateMillis?.let { millis ->
                        val date = LocalDate.ofEpochDay(millis / 86400000)
                        viewModel.setDateFilter(date)
                    }
                    showDatePicker = false
                }) {
                    Text("OK")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDatePicker = false }) {
                    Text("Annuler")
                }
            }
        ) {
            DatePicker(state = datePickerState)
        }
    }

    // Confirm Pay Dialog
    confirmPayTicket?.let { ticket ->
        AlertDialog(
            onDismissRequest = { confirmPayTicket = null },
            title = { Text("Confirmer paiement") },
            text = {
                Column {
                    Text("Ticket: ${ticket.numero}")
                    Text("Gain à payer: ${ticket.totalGainDu.toInt()} G", fontWeight = FontWeight.Bold, color = Color(0xFF10B981))
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.payTicket(ticket.id)
                        confirmPayTicket = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
                ) {
                    Text("Payer")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmPayTicket = null }) {
                    Text("Annuler")
                }
            }
        )
    }

    // Confirm Void Dialog
    confirmVoidTicket?.let { ticket ->
        AlertDialog(
            onDismissRequest = { confirmVoidTicket = null },
            title = { Text("Confirmer annulation") },
            text = {
                Column {
                    Text("Ticket: ${ticket.numero}")
                    Text("Cette action est irréversible.", color = Color.Red)
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.voidTicket(ticket.id)
                        confirmVoidTicket = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                ) {
                    Text("Annuler ticket")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmVoidTicket = null }) {
                    Text("Retour")
                }
            }
        )
    }

    // Share Dialog
    showShareDialog?.let { ticket ->
        AlertDialog(
            onDismissRequest = {
                if (!isSharingLoading) {
                    showShareDialog = null
                }
            },
            title = { Text("Partager le ticket") },
            text = {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (isSharingLoading) {
                        CircularProgressIndicator(modifier = Modifier.padding(16.dp))
                        Text("Récupération des détails...", fontSize = 14.sp, color = Color.Gray)
                    } else {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Text("Ticket: ${ticket.numero}")
                            Text("Tirage: ${ticket.tirageNom}")
                            Text("Mise: ${ticket.totalMise.toInt()} HTG")
                            if (ticket.isWinner) {
                                Text("Gain: ${ticket.totalGainDu.toInt()} HTG", color = Color(0xFF10B981))
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    // Option 1: Share as Text
                    TextButton(
                        enabled = !isSharingLoading,
                        onClick = {
                            scope.launch {
                                isSharingLoading = true
                                try {
                                    val printData = viewModel.getTicketPrintData(ticket.id)
                                    if (printData != null) {
                                        val shareData = TicketShareUtil.fromPrintData(
                                            printData = printData,
                                            logoBitmap = null,
                                            totalGainDu = ticket.totalGainDu,
                                            isWinner = ticket.isWinner
                                        )
                                        TicketShareUtil.shareAsText(context, shareData)
                                        showShareDialog = null
                                    } else {
                                        snackbarHostState.showSnackbar("Erreur de récupération des données")
                                    }
                                } catch (e: Throwable) {
                                    snackbarHostState.showSnackbar("Erreur partage texte: ${e.message}")
                                } finally {
                                    isSharingLoading = false
                                }
                            }
                        }
                    ) {
                        Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Texte")
                    }

                    // Option 2: Share as Image
                    TextButton(
                        enabled = !isSharingLoading,
                        onClick = {
                            scope.launch {
                                isSharingLoading = true
                                try {
                                    val printData = viewModel.getTicketPrintData(ticket.id)
                                    if (printData != null) {
                                        val logoBitmap = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                                            try {
                                                if (!printData.borletteLogoUrl.isNullOrBlank())
                                                    TicketShareUtil.downloadLogo(context, printData.borletteLogoUrl)
                                                else null
                                            } catch (_: Throwable) { null }
                                        }
                                        val shareData = TicketShareUtil.fromPrintData(
                                            printData = printData,
                                            logoBitmap = logoBitmap,
                                            totalGainDu = ticket.totalGainDu,
                                            isWinner = ticket.isWinner
                                        )
                                        TicketShareUtil.shareAsImage(context, shareData)
                                        showShareDialog = null
                                    } else {
                                        snackbarHostState.showSnackbar("Erreur de récupération des données")
                                    }
                                } catch (e: Throwable) {
                                    snackbarHostState.showSnackbar("Erreur partage image: ${e.message}")
                                } finally {
                                    isSharingLoading = false
                                }
                            }
                        }
                    ) {
                        Icon(Icons.Default.Image, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Image")
                    }

                    // Option 3: Share as PDF
                    TextButton(
                        enabled = !isSharingLoading,
                        onClick = {
                            scope.launch {
                                isSharingLoading = true
                                try {
                                    val printData = viewModel.getTicketPrintData(ticket.id)
                                    if (printData != null) {
                                        val logoBitmap = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                                            try {
                                                if (!printData.borletteLogoUrl.isNullOrBlank())
                                                    TicketShareUtil.downloadLogo(context, printData.borletteLogoUrl)
                                                else null
                                            } catch (_: Throwable) { null }
                                        }
                                        val shareData = TicketShareUtil.fromPrintData(
                                            printData = printData,
                                            logoBitmap = logoBitmap,
                                            totalGainDu = ticket.totalGainDu,
                                            isWinner = ticket.isWinner
                                        )
                                        val bitmap = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                                            TicketShareUtil.generateTicketImage(context, shareData)
                                        }
                                        TicketShareUtil.saveAsPdf(context, bitmap, ticket.numero)
                                        showShareDialog = null
                                    } else {
                                        snackbarHostState.showSnackbar("Erreur de récupération des données")
                                    }
                                } catch (e: Throwable) {
                                    snackbarHostState.showSnackbar("Erreur partage PDF: ${e.message}")
                                } finally {
                                    isSharingLoading = false
                                }
                            }
                        }
                    ) {
                        Icon(Icons.Default.PictureAsPdf, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("PDF")
                    }
                }
            },
            dismissButton = {
                TextButton(
                    enabled = !isSharingLoading,
                    onClick = { showShareDialog = null }
                ) {
                    Text("Annuler")
                }
            }
        )
    }

    // QR Code Scanner Dialog
    if (showQrScanner) {
        QrCodeScannerDialog(
            onDismiss = { showQrScanner = false },
            onQrCodeScanned = { groupId ->
                showQrScanner = false
                viewModel.searchByGroupId(groupId)
                showGroupResults = true
            }
        )
    }

    // Group Results Dialog
    if (showGroupResults && uiState.groupTickets.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { 
                showGroupResults = false
                viewModel.clearGroupResults()
            },
            title = { 
                Text("Groupe de tickets (${uiState.groupTickets.size})")
            },
            text = {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 400.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(uiState.groupTickets) { ticket ->
                        GroupTicketCard(
                            ticket = ticket,
                            onPay = {
                                viewModel.payTicket(ticket.id)
                            }
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { 
                    showGroupResults = false
                    viewModel.clearGroupResults()
                }) {
                    Text("Fermer")
                }
            }
        )
    }
}

@Composable
private fun GroupTicketCard(
    ticket: TicketGroupItem,
    onPay: () -> Unit
) {
    val statusColor = Color(ticket.getStatusColor())
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(ticket.numero, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    Text(ticket.tirageNom, fontSize = 11.sp, color = Color.Gray)
                }
                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = statusColor.copy(alpha = 0.15f)
                ) {
                    Text(
                        ticket.getStatusDisplay(),
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        fontSize = 10.sp,
                        color = statusColor,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(6.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("Mise: ${ticket.totalMise.toInt()} HTG", fontSize = 11.sp)
                if (ticket.isWinner) {
                    Text(
                        "Gain: ${ticket.totalGainDu.toInt()} HTG",
                        fontSize = 11.sp,
                        color = Color(0xFF10B981),
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            
            if (ticket.canPay) {
                Spacer(modifier = Modifier.height(6.dp))
                Button(
                    onClick = onPay,
                    modifier = Modifier.fillMaxWidth().height(32.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981)),
                    contentPadding = PaddingValues(horizontal = 8.dp)
                ) {
                    Icon(Icons.Default.Payment, contentDescription = null, modifier = Modifier.size(14.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Payer", fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun TicketCard(
    ticket: TicketListItem,
    isPaying: Boolean,
    isVoiding: Boolean,
    isReprinting: Boolean,
    onPay: () -> Unit,
    onVoid: () -> Unit,
    onReprint: () -> Unit,
    onShare: () -> Unit,
    onRefaire: () -> Unit,
    onModifier: () -> Unit,
    onViewPdf: () -> Unit
) {
    val statusColor = Color(ticket.getStatusColor())
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            // Header: Ticket number + Status badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        ticket.numero,
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp
                    )
                    Text(
                        ticket.tirageNom,
                        fontSize = 11.sp,
                        color = Color.Gray
                    )
                }
                
                Surface(
                    color = statusColor.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Text(
                        ticket.getStatusDisplay(),
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                        color = statusColor,
                        fontWeight = FontWeight.Bold,
                        fontSize = 11.sp
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // Info row: Bets, Mise, Gain
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("${ticket.numBets} paris", fontSize = 11.sp, color = Color.Gray)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("Mise: ${ticket.totalMise.toInt()} G", fontSize = 11.sp)
                    if (ticket.isWinner || ticket.status == "paid") {
                        Text(
                            "Gain: ${ticket.totalGainDu.toInt()} G",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF10B981)
                        )
                    }
                    if (ticket.status == "paid") {
                        Text(
                            "Payé: ${ticket.totalGainPaye.toInt()} G",
                            fontSize = 11.sp,
                            color = Color(0xFF3B82F6)
                        )
                    }
                }
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // Time info
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "Il y a ${ticket.ageMinutes.toInt()} min",
                    fontSize = 10.sp,
                    color = Color.Gray
                )
                
                // Action buttons
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    // Refaire button (available anytime)
                    OutlinedButton(
                        onClick = onRefaire,
                        modifier = Modifier.height(32.dp),
                        contentPadding = PaddingValues(horizontal = 6.dp)
                    ) {
                        Icon(Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(2.dp))
                        Text("Refaire", fontSize = 10.sp)
                    }

                    // Void & Modify buttons (< 60s)
                    if (ticket.canVoid) {
                        OutlinedButton(
                            onClick = onVoid,
                            enabled = !isVoiding,
                            modifier = Modifier.height(32.dp),
                            contentPadding = PaddingValues(horizontal = 6.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.Red)
                        ) {
                            Icon(Icons.Default.Cancel, contentDescription = null, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(2.dp))
                            Text("Annuler", fontSize = 10.sp)
                        }

                        OutlinedButton(
                            onClick = onModifier,
                            enabled = !isVoiding,
                            modifier = Modifier.height(32.dp),
                            contentPadding = PaddingValues(horizontal = 6.dp)
                        ) {
                            Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(2.dp))
                            Text("Modifier", fontSize = 10.sp)
                        }
                    } else {
                        // Show "Voir le ticket" (PDF viewer) if not cancelled
                        if (ticket.status != "cancelled") {
                            OutlinedButton(
                                onClick = onViewPdf,
                                modifier = Modifier.height(32.dp),
                                contentPadding = PaddingValues(horizontal = 6.dp)
                            ) {
                                Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(14.dp))
                                Spacer(modifier = Modifier.width(2.dp))
                                Text("Voir", fontSize = 10.sp)
                            }
                        }
                    }
                    
                    // Share button
                    OutlinedButton(
                        onClick = onShare,
                        modifier = Modifier.height(32.dp),
                        contentPadding = PaddingValues(horizontal = 4.dp)
                    ) {
                        Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(14.dp))
                    }
                    
                    // Reprint button
                    if (ticket.canReprint) {
                        OutlinedButton(
                            onClick = onReprint,
                            enabled = !isReprinting,
                            modifier = Modifier.height(32.dp),
                            contentPadding = PaddingValues(horizontal = 6.dp)
                        ) {
                            Icon(Icons.Default.Print, contentDescription = null, modifier = Modifier.size(14.dp))
                        }
                    }
                    
                    // Pay button (only for won tickets)
                    if (ticket.canPay) {
                        Button(
                            onClick = onPay,
                            enabled = !isPaying,
                            modifier = Modifier.height(32.dp),
                            contentPadding = PaddingValues(horizontal = 6.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
                        ) {
                            if (isPaying) {
                                Text("...", fontSize = 10.sp, color = Color.White)
                            } else {
                                Icon(Icons.Default.Payments, contentDescription = null, modifier = Modifier.size(14.dp))
                                Spacer(modifier = Modifier.width(2.dp))
                                Text("Payer", fontSize = 10.sp)
                            }
                        }
                    }
                }
            }
        }
    }
}
