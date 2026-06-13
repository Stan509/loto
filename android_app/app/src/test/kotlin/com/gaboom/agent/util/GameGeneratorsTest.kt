package com.gaboom.agent.util

import org.junit.Assert.*
import org.junit.Test

class GameGeneratorsTest {

    @Test
    fun `generateMariages with 3 boules returns 3 combinations`() {
        val boules = listOf("34", "67", "87")
        val result = GameGenerators.generateMariages(boules)
        
        assertEquals(3, result.size)
        assertTrue(result.contains("34x67"))
        assertTrue(result.contains("34x87"))
        assertTrue(result.contains("67x87"))
    }

    @Test
    fun `generateMariages with 2 boules returns 1 combination`() {
        val boules = listOf("12", "34")
        val result = GameGenerators.generateMariages(boules)
        
        assertEquals(1, result.size)
        assertEquals("12x34", result[0])
    }

    @Test
    fun `generateMariages with 1 boule returns empty`() {
        val boules = listOf("12")
        val result = GameGenerators.generateMariages(boules)
        
        assertTrue(result.isEmpty())
    }

    @Test
    fun `generateMariages with duplicates filters them`() {
        val boules = listOf("12", "34", "12", "34")
        val result = GameGenerators.generateMariages(boules)
        
        assertEquals(1, result.size)
        assertEquals("12x34", result[0])
    }

    @Test
    fun `generateLoto4Permutations with 3 boules returns 6 permutations`() {
        val boules = listOf("34", "67", "87")
        val result = GameGenerators.generateLoto4Permutations(boules)
        
        assertEquals(6, result.size)
        assertTrue(result.contains("3467"))
        assertTrue(result.contains("6734"))
        assertTrue(result.contains("3487"))
        assertTrue(result.contains("8734"))
        assertTrue(result.contains("6787"))
        assertTrue(result.contains("8767"))
    }

    @Test
    fun `generateLoto4Permutations with 2 boules returns 2 permutations`() {
        val boules = listOf("12", "34")
        val result = GameGenerators.generateLoto4Permutations(boules)
        
        assertEquals(2, result.size)
        assertTrue(result.contains("1234"))
        assertTrue(result.contains("3412"))
    }

    @Test
    fun `generateLoto4Permutations with 1 boule returns empty`() {
        val boules = listOf("12")
        val result = GameGenerators.generateLoto4Permutations(boules)
        
        assertTrue(result.isEmpty())
    }

    @Test
    fun `extractBoulesFromLines extracts boules correctly`() {
        val lines = listOf(
            Pair("boule", "34"),
            Pair("boule", "67"),
            Pair("mariage", "12x45"),
            Pair("loto3", "789"),
            Pair("loto4", "1234")
        )
        val result = GameGenerators.extractBoulesFromLines(lines)
        
        assertTrue(result.contains("34"))
        assertTrue(result.contains("67"))
        assertTrue(result.contains("12"))
        assertTrue(result.contains("45"))
        assertTrue(result.contains("89")) // last 2 of loto3
        assertTrue(result.contains("12")) // first 2 of loto4
        assertTrue(result.contains("34")) // last 2 of loto4
    }

    @Test
    fun `generateAutoMariages excludes existing mariages`() {
        val existingLines = listOf(
            Pair("boule", "34"),
            Pair("boule", "67"),
            Pair("boule", "87"),
            Pair("mariage", "34x67") // already exists
        )
        val result = GameGenerators.generateAutoMariages(existingLines, 50.0)
        
        assertEquals(2, result.size)
        assertTrue(result.any { it.second == "34x87" })
        assertTrue(result.any { it.second == "67x87" })
        assertFalse(result.any { it.second == "34x67" })
    }

    @Test
    fun `generateAutoLoto4 excludes existing loto4`() {
        val existingLines = listOf(
            Pair("boule", "12"),
            Pair("boule", "34"),
            Pair("loto4", "1234") // already exists
        )
        val result = GameGenerators.generateAutoLoto4(existingLines, 50.0)
        
        assertEquals(1, result.size)
        assertEquals("3412", result[0].second)
    }

    @Test
    fun `nC2 formula verification - 4 boules should give 6 combinations`() {
        val boules = listOf("11", "22", "33", "44")
        val result = GameGenerators.generateMariages(boules)
        
        // nC2 = n! / (2! * (n-2)!) = 4! / (2! * 2!) = 6
        assertEquals(6, result.size)
    }

    @Test
    fun `nP2 formula verification - 4 boules should give 12 permutations`() {
        val boules = listOf("11", "22", "33", "44")
        val result = GameGenerators.generateLoto4Permutations(boules)
        
        // nP2 = n! / (n-2)! = 4! / 2! = 12
        assertEquals(12, result.size)
    }
}
