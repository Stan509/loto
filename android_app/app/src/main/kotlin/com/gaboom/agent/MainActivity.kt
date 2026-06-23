package com.gaboom.agent

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.rememberNavController
import com.gaboom.agent.data.HeartbeatManager
import com.gaboom.agent.data.config.AppConfigDataStore
import com.gaboom.agent.ui.navigation.AppNavigation
import com.gaboom.agent.ui.theme.GaboomAgentTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var heartbeatManager: HeartbeatManager
    
    @Inject
    lateinit var appConfigDataStore: AppConfigDataStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Read crash log if exists
        val logFile = java.io.File(filesDir, "crash_log.txt")
        val crashLogContent = if (logFile.exists()) {
            try {
                logFile.readText()
            } catch (e: Exception) {
                null
            }
        } else {
            null
        }

        setContent {
            val themeMode by appConfigDataStore.themeModeFlow.collectAsState(initial = AppConfigDataStore.THEME_DEFAULT)
            
            var currentCrashLog by remember { mutableStateOf(crashLogContent) }
            
            GaboomAgentTheme(themeMode = themeMode) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    AppNavigation(navController = navController)
                    
                    currentCrashLog?.let { logText ->
                        AlertDialog(
                            onDismissRequest = { /* Don't dismiss by clicking outside */ },
                            title = { Text("Rapport de Crash Détecté") },
                            text = {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(300.dp)
                                        .verticalScroll(rememberScrollState())
                                ) {
                                    Text(
                                        text = logText,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                            },
                            confirmButton = {
                                TextButton(
                                    onClick = {
                                        // Share the log text
                                        try {
                                            val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                                                type = "text/plain"
                                                putExtra(android.content.Intent.EXTRA_TEXT, logText)
                                            }
                                            startActivity(android.content.Intent.createChooser(intent, "Partager le crash"))
                                        } catch (e: Exception) {
                                            // ignore
                                        }
                                    }
                                ) {
                                    Text("Partager")
                                }
                            },
                            dismissButton = {
                                TextButton(
                                    onClick = {
                                        // Delete the log file and dismiss
                                        try {
                                            if (logFile.exists()) {
                                                logFile.delete()
                                            }
                                        } catch (e: Exception) {
                                            // ignore
                                        }
                                        currentCrashLog = null
                                    }
                                ) {
                                    Text("Effacer & Fermer")
                                }
                            }
                        )
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        heartbeatManager.start()
    }

    override fun onPause() {
        super.onPause()
        heartbeatManager.stop()
    }
}
