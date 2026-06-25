package com.gaboom.agent.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.gaboom.agent.ui.screens.auth.LoginScreen
import com.gaboom.agent.ui.screens.home.HomeScreen
import com.gaboom.agent.ui.screens.vente.VenteScreen
import com.gaboom.agent.ui.screens.historique.HistoriqueScreen
import com.gaboom.agent.ui.screens.resultats.ResultatsScreen
import com.gaboom.agent.ui.screens.stats.StatsScreen
import com.gaboom.agent.ui.screens.search.SearchTicketScreen
import com.gaboom.agent.ui.screens.settings.SettingsScreen
import com.gaboom.agent.ui.screens.sync.SyncScreen
import com.gaboom.agent.ui.screens.tickets.TicketManagementScreen

/**
 * Routes de navigation
 */
object Routes {
    const val LOGIN = "login"
    const val HOME = "home"
    const val TIRAGES = "tirages"
    const val TIRAGE_DETAIL = "tirage/{tirageId}/{tirageNom}/{tirageEtat}"
    const val TIRAGE_SELECTION = "tirage-selection"
    const val VENTE = "vente?tirageId={tirageId}&tirageNom={tirageNom}&blueprintTicketId={blueprintTicketId}"
    const val HISTORIQUE = "historique"
    const val RESULTATS = "resultats"
    const val STATS = "stats"
    const val SEARCH_TICKET = "search-ticket"
    const val TICKET_MANAGEMENT = "ticket-management"
    const val SETTINGS = "settings"
    const val SYNC = "sync"

    fun vente(tirageId: Int? = null, tirageNom: String? = null, blueprintTicketId: String? = null): String {
        val params = mutableListOf<String>()
        if (tirageId != null) params.add("tirageId=$tirageId")
        if (tirageNom != null) params.add("tirageNom=${java.net.URLEncoder.encode(tirageNom, "UTF-8")}")
        if (blueprintTicketId != null) params.add("blueprintTicketId=$blueprintTicketId")
        val query = params.joinToString("&")
        return if (query.isEmpty()) "vente" else "vente?$query"
    }
    
    fun tirageDetail(tirageId: Int, tirageNom: String, tirageEtat: String) = 
        "tirage/$tirageId/${java.net.URLEncoder.encode(tirageNom, "UTF-8")}/$tirageEtat"
}

/**
 * Navigation principale de l'application
 */
@Composable
fun AppNavigation(navController: NavHostController) {
    NavHost(
        navController = navController,
        startDestination = Routes.LOGIN
    ) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.HOME) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                },
                onNavigateToSettings = {
                    navController.navigate(Routes.SETTINGS)
                }
            )
        }

        composable(Routes.HOME) {
            HomeScreen(
                onNavigateToVente = { navController.navigate(Routes.vente()) },
                onNavigateToHistorique = { navController.navigate(Routes.HISTORIQUE) },
                onNavigateToResultats = { navController.navigate(Routes.RESULTATS) },
                onNavigateToStats = { navController.navigate(Routes.STATS) },
                onNavigateToSearch = { navController.navigate(Routes.SEARCH_TICKET) },
                onNavigateToTicketManagement = { navController.navigate(Routes.TICKET_MANAGEMENT) },
                onNavigateToSettings = { navController.navigate(Routes.SETTINGS) },
                onNavigateToSync = { navController.navigate(Routes.SYNC) },
                onLogout = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.HOME) { inclusive = true }
                    }
                }
            )
        }

        composable(
            route = Routes.VENTE,
            arguments = listOf(
                navArgument("tirageId") { 
                    type = NavType.IntType
                    defaultValue = -1 
                },
                navArgument("tirageNom") { 
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null 
                },
                navArgument("blueprintTicketId") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                }
            )
        ) { backStackEntry ->
            val tirageId = backStackEntry.arguments?.getInt("tirageId")?.takeIf { it != -1 }
            val tirageNom = backStackEntry.arguments?.getString("tirageNom")
            val blueprintTicketId = backStackEntry.arguments?.getString("blueprintTicketId")
            
            VenteScreen(
                tirageId = tirageId,
                defaultTirageNom = tirageNom,
                blueprintTicketId = blueprintTicketId,
                onBack = { navController.popBackStack() },
                onTicketCreated = { navController.popBackStack() }
            )
        }

        composable(Routes.SEARCH_TICKET) {
            SearchTicketScreen(
                onBack = { navController.popBackStack() },
                onRefaire = { ticketResult ->
                    navController.navigate(Routes.vente(blueprintTicketId = ticketResult.id))
                }
            )
        }

        composable(Routes.HISTORIQUE) {
            HistoriqueScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.RESULTATS) {
            ResultatsScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.STATS) {
            StatsScreen(
                onBack = { navController.popBackStack() }
            )
        }


        composable(Routes.SETTINGS) {
            SettingsScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.SYNC) {
            SyncScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.TICKET_MANAGEMENT) {
            TicketManagementScreen(
                onNavigateBack = { navController.popBackStack() },
                onRefaire = { blueprintTicketId ->
                    navController.navigate(Routes.vente(blueprintTicketId = blueprintTicketId))
                }
            )
        }
    }
}
