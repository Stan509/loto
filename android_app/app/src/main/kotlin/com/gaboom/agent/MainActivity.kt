package com.gaboom.agent

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
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
        setContent {
            val themeMode by appConfigDataStore.themeModeFlow.collectAsState(initial = AppConfigDataStore.THEME_DEFAULT)
            
            GaboomAgentTheme(themeMode = themeMode) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    AppNavigation(navController = navController)
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
