package com.gaboom.agent.util

/**
 * Helpers pour génération automatique de combinaisons
 * - Mariage: nC2 (combinaisons)
 * - Loto4: nP2 (permutations ordonnées)
 */
object GameGenerators {

    /**
     * Génère toutes les combinaisons de mariage (nC2) à partir d'une liste de boules
     * Ex: [34, 67, 87] => ["34x67", "34x87", "67x87"]
     */
    fun generateMariages(boules: List<String>): List<String> {
        if (boules.size < 2) return emptyList()
        
        val uniqueBoules = boules.distinct().filter { it.length == 2 && it.all { c -> c.isDigit() } }
        val result = mutableListOf<String>()
        
        for (i in uniqueBoules.indices) {
            for (j in i + 1 until uniqueBoules.size) {
                result.add("${uniqueBoules[i]}x${uniqueBoules[j]}")
            }
        }
        
        return result
    }

    /**
     * Génère toutes les permutations ordonnées de Loto4 (nP2) à partir d'une liste de boules
     * Ex: [34, 67, 87] => ["3467", "6734", "3487", "8734", "6787", "8767"]
     */
    fun generateLoto4Permutations(boules: List<String>): List<String> {
        if (boules.size < 2) return emptyList()
        
        val uniqueBoules = boules.distinct().filter { it.length == 2 && it.all { c -> c.isDigit() } }
        val result = mutableListOf<String>()
        
        for (i in uniqueBoules.indices) {
            for (j in uniqueBoules.indices) {
                if (i != j) {
                    result.add("${uniqueBoules[i]}${uniqueBoules[j]}")
                }
            }
        }
        
        return result
    }

    /**
     * Extrait toutes les boules (2 chiffres) d'une liste de lignes de ticket
     * Supporte: boule direct, mariage (AAxBB), loto3 (extrait les 2 derniers), etc.
     */
    fun extractBoulesFromLines(lines: List<Pair<String, String>>): List<String> {
        val boules = mutableSetOf<String>()
        
        for ((jeu, valeur) in lines) {
            when (jeu.lowercase()) {
                "boule" -> {
                    if (valeur.length == 2 && valeur.all { it.isDigit() }) {
                        boules.add(valeur)
                    }
                }
                "mariage" -> {
                    val parts = valeur.split("x", "X")
                    parts.forEach { part ->
                        if (part.length == 2 && part.all { it.isDigit() }) {
                            boules.add(part)
                        }
                    }
                }
                "loto3" -> {
                    if (valeur.length == 3 && valeur.all { it.isDigit() }) {
                        boules.add(valeur.takeLast(2))
                    }
                }
                "loto4" -> {
                    if (valeur.length == 4 && valeur.all { it.isDigit() }) {
                        boules.add(valeur.take(2))
                        boules.add(valeur.takeLast(2))
                    }
                }
                "loto5" -> {
                    if (valeur.length == 5 && valeur.all { it.isDigit() }) {
                        boules.add(valeur.substring(1, 3))
                        boules.add(valeur.takeLast(2))
                    }
                }
            }
        }
        
        return boules.toList()
    }

    /**
     * Génère les mariages automatiques en filtrant les doublons existants
     */
    fun generateAutoMariages(
        existingLines: List<Pair<String, String>>,
        defaultMise: Double
    ): List<Triple<String, String, Double>> {
        val boules = extractBoulesFromLines(existingLines)
        val existingMariages = existingLines
            .filter { it.first.lowercase() == "mariage" }
            .map { normalizeMarriage(it.second) }
            .toSet()
        
        return generateMariages(boules)
            .filter { normalizeMarriage(it) !in existingMariages }
            .map { Triple("mariage", it, defaultMise) }
    }

    /**
     * Génère les loto4 automatiques en filtrant les doublons existants
     */
    fun generateAutoLoto4(
        existingLines: List<Pair<String, String>>,
        defaultMise: Double
    ): List<Triple<String, String, Double>> {
        val boules = extractBoulesFromLines(existingLines)
        val existingLoto4 = existingLines
            .filter { it.first.lowercase() == "loto4" }
            .map { it.second }
            .toSet()
        
        return generateLoto4Permutations(boules)
            .filter { it !in existingLoto4 }
            .map { Triple("loto4", it, defaultMise) }
    }

    /**
     * Normalise un mariage pour comparaison (ordre alphabétique)
     */
    private fun normalizeMarriage(mariage: String): String {
        val parts = mariage.split("x", "X")
        return if (parts.size == 2) {
            val sorted = parts.sorted()
            "${sorted[0]}x${sorted[1]}"
        } else mariage
    }
}
