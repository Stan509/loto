package com.gaboom.agent.util

import com.gaboom.agent.data.model.TicketLineWithOptions

/**
 * Helper utilities for Loto4/Loto5 options handling.
 * 
 * Business Rules:
 * - Each option (1, 2, 3) is a distinct bet
 * - FULL = options {1, 2, 3} = 3 bets
 * - Each bet has its own mise
 * - Total mise for a line = miseBase × options.size
 */
object LotoOptionsHelper {

    /**
     * Data class representing a single bet (expanded from a line with multiple options)
     */
    data class ExpandedBet(
        val game: String,
        val number: String,
        val option: Int,  // 1, 2, or 3
        val mise: Double,
        val gratuit: Boolean = false
    )

    /**
     * Expand a Loto4/Loto5 line into individual bets (one per option).
     * For non-Loto games, returns a single bet with option=0.
     * 
     * @param line The ticket line with options
     * @return List of individual bets
     */
    fun expandLineToBets(line: TicketLineWithOptions): List<ExpandedBet> {
        val game = line.jeu.lowercase()
        
        return if (game in listOf("loto4", "loto5")) {
            if (line.options.isEmpty()) {
                // No options selected - this shouldn't happen if validation is correct
                emptyList()
            } else {
                line.options.sorted().map { opt ->
                    ExpandedBet(
                        game = line.jeu,
                        number = line.valeur,
                        option = opt,
                        mise = line.miseBase,
                        gratuit = line.gratuit
                    )
                }
            }
        } else {
            // Non-Loto games: single bet
            listOf(
                ExpandedBet(
                    game = line.jeu,
                    number = line.valeur,
                    option = 0,  // Not applicable
                    mise = line.miseBase,
                    gratuit = line.gratuit
                )
            )
        }
    }

    /**
     * Format a Loto line for print/display.
     * 
     * Compact format (same mise for all options):
     * - "L4: 2346 FULL" if options = {1,2,3}
     * - "L4: 2346 opt1,2" if options = {1,2}
     * - "L4: 2346 opt1" if options = {1}
     * 
     * @param game Game type ("loto4" or "loto5")
     * @param number The number value
     * @param options Set of selected options
     * @param mise Base mise per option
     * @return Formatted string for display/print
     */
    fun formatLotoLineForPrint(
        game: String,
        number: String,
        options: Set<Int>,
        mise: Double
    ): String {
        val prefix = when (game.lowercase()) {
            "loto4" -> "L4"
            "loto5" -> "L5"
            else -> game.uppercase()
        }
        
        val optionsStr = when {
            options.isEmpty() -> "???"
            options.size == 3 && options.containsAll(setOf(1, 2, 3)) -> "FULL"
            else -> "opt" + options.sorted().joinToString(",")
        }
        
        val totalMise = mise * options.size
        
        return "$prefix: $number $optionsStr ${totalMise.toInt()}HTG"
    }

    /**
     * Format options for compact display.
     * 
     * @param options Set of selected options
     * @return Display string like "FULL", "1,2", "1", etc.
     */
    fun formatOptionsCompact(options: Set<Int>): String {
        return when {
            options.isEmpty() -> "-"
            options.size == 3 && options.containsAll(setOf(1, 2, 3)) -> "FULL"
            else -> options.sorted().joinToString(",")
        }
    }

    /**
     * Calculate total mise for a line based on options.
     * 
     * @param miseBase Base mise per option
     * @param options Selected options
     * @return Total mise (miseBase × options.count)
     */
    fun calculateTotalMise(miseBase: Double, options: Set<Int>): Double {
        return if (options.isEmpty()) 0.0 else miseBase * options.size
    }

    /**
     * Count total bets for a line.
     * For Loto4/Loto5: number of options selected
     * For other games: 1
     * 
     * @param line The ticket line
     * @return Number of bets
     */
    fun countBets(line: TicketLineWithOptions): Int {
        return if (line.jeu.lowercase() in listOf("loto4", "loto5")) {
            if (line.options.isEmpty()) 0 else line.options.size
        } else {
            1
        }
    }

    /**
     * Validate that a Loto4/Loto5 line has at least one option selected.
     * 
     * @param game Game type
     * @param options Selected options
     * @return Pair of (isValid, errorMessage)
     */
    fun validateLotoOptions(game: String, options: Set<Int>): Pair<Boolean, String?> {
        val gameLower = game.lowercase()
        return if (gameLower in listOf("loto4", "loto5") && options.isEmpty()) {
            Pair(false, "Choisissez au moins une option (1/2/3) pour $game")
        } else {
            Pair(true, null)
        }
    }

    /**
     * Get default options for a new Loto4/Loto5 line.
     * Default is option 1 to avoid empty options.
     */
    fun getDefaultOptions(): Set<Int> = setOf(1)
}
