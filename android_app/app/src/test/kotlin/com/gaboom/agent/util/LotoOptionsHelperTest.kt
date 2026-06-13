package com.gaboom.agent.util

import com.gaboom.agent.data.model.TicketLineWithOptions
import org.junit.Assert.*
import org.junit.Test

class LotoOptionsHelperTest {

    // ═══════════════════════════════════════════════════════════════════════════
    // expandLineToBets Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `Loto4 FULL creates 3 bets`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "2346",
            miseBase = 50.0,
            options = setOf(1, 2, 3)
        )
        
        val bets = LotoOptionsHelper.expandLineToBets(line)
        
        assertEquals(3, bets.size)
        assertTrue(bets.all { it.game == "loto4" })
        assertTrue(bets.all { it.number == "2346" })
        assertTrue(bets.all { it.mise == 50.0 })
        assertEquals(setOf(1, 2, 3), bets.map { it.option }.toSet())
    }

    @Test
    fun `Loto4 opt2 only creates 1 bet`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "1234",
            miseBase = 25.0,
            options = setOf(2)
        )
        
        val bets = LotoOptionsHelper.expandLineToBets(line)
        
        assertEquals(1, bets.size)
        assertEquals(2, bets[0].option)
        assertEquals(25.0, bets[0].mise, 0.001)
    }

    @Test
    fun `Loto5 opt1+opt3 creates 2 bets`() {
        val line = TicketLineWithOptions(
            jeu = "loto5",
            valeur = "12345",
            miseBase = 25.0,
            options = setOf(1, 3)
        )
        
        val bets = LotoOptionsHelper.expandLineToBets(line)
        
        assertEquals(2, bets.size)
        assertEquals(setOf(1, 3), bets.map { it.option }.toSet())
    }

    @Test
    fun `Loto4 empty options returns empty list`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "2346",
            miseBase = 50.0,
            options = emptySet()
        )
        
        val bets = LotoOptionsHelper.expandLineToBets(line)
        
        assertTrue(bets.isEmpty())
    }

    @Test
    fun `Boule creates single bet with option 0`() {
        val line = TicketLineWithOptions(
            jeu = "boule",
            valeur = "34",
            miseBase = 100.0,
            options = emptySet()
        )
        
        val bets = LotoOptionsHelper.expandLineToBets(line)
        
        assertEquals(1, bets.size)
        assertEquals(0, bets[0].option)
        assertEquals("34", bets[0].number)
    }

    @Test
    fun `Mariage creates single bet`() {
        val line = TicketLineWithOptions(
            jeu = "mariage",
            valeur = "34x56",
            miseBase = 50.0,
            options = emptySet()
        )
        
        val bets = LotoOptionsHelper.expandLineToBets(line)
        
        assertEquals(1, bets.size)
        assertEquals("mariage", bets[0].game)
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // calculateTotalMise Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `Loto4 FULL mise 50 equals total 150`() {
        val total = LotoOptionsHelper.calculateTotalMise(50.0, setOf(1, 2, 3))
        assertEquals(150.0, total, 0.001)
    }

    @Test
    fun `Loto4 2 options mise 50 equals total 100`() {
        val total = LotoOptionsHelper.calculateTotalMise(50.0, setOf(1, 2))
        assertEquals(100.0, total, 0.001)
    }

    @Test
    fun `Empty options equals total 0`() {
        val total = LotoOptionsHelper.calculateTotalMise(50.0, emptySet())
        assertEquals(0.0, total, 0.001)
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // countBets Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `Loto4 FULL counts 3 bets`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "2346",
            miseBase = 50.0,
            options = setOf(1, 2, 3)
        )
        
        assertEquals(3, LotoOptionsHelper.countBets(line))
    }

    @Test
    fun `Loto5 opt1+opt2 counts 2 bets`() {
        val line = TicketLineWithOptions(
            jeu = "loto5",
            valeur = "12345",
            miseBase = 25.0,
            options = setOf(1, 2)
        )
        
        assertEquals(2, LotoOptionsHelper.countBets(line))
    }

    @Test
    fun `Boule counts 1 bet`() {
        val line = TicketLineWithOptions(
            jeu = "boule",
            valeur = "34",
            miseBase = 100.0,
            options = emptySet()
        )
        
        assertEquals(1, LotoOptionsHelper.countBets(line))
    }

    @Test
    fun `Loto4 empty options counts 0 bets`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "2346",
            miseBase = 50.0,
            options = emptySet()
        )
        
        assertEquals(0, LotoOptionsHelper.countBets(line))
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // validateLotoOptions Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `Loto4 with options is valid`() {
        val (isValid, error) = LotoOptionsHelper.validateLotoOptions("loto4", setOf(1))
        assertTrue(isValid)
        assertNull(error)
    }

    @Test
    fun `Loto5 with options is valid`() {
        val (isValid, error) = LotoOptionsHelper.validateLotoOptions("loto5", setOf(1, 2, 3))
        assertTrue(isValid)
        assertNull(error)
    }

    @Test
    fun `Loto4 empty options is invalid`() {
        val (isValid, error) = LotoOptionsHelper.validateLotoOptions("loto4", emptySet())
        assertFalse(isValid)
        assertNotNull(error)
        assertTrue(error!!.contains("option"))
    }

    @Test
    fun `Loto5 empty options is invalid`() {
        val (isValid, error) = LotoOptionsHelper.validateLotoOptions("loto5", emptySet())
        assertFalse(isValid)
        assertNotNull(error)
    }

    @Test
    fun `Boule empty options is valid`() {
        val (isValid, error) = LotoOptionsHelper.validateLotoOptions("boule", emptySet())
        assertTrue(isValid)
        assertNull(error)
    }

    @Test
    fun `Mariage empty options is valid`() {
        val (isValid, error) = LotoOptionsHelper.validateLotoOptions("mariage", emptySet())
        assertTrue(isValid)
        assertNull(error)
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // formatLotoLineForPrint Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `Format Loto4 FULL`() {
        val formatted = LotoOptionsHelper.formatLotoLineForPrint("loto4", "2346", setOf(1, 2, 3), 50.0)
        assertTrue(formatted.contains("L4"))
        assertTrue(formatted.contains("2346"))
        assertTrue(formatted.contains("FULL"))
        assertTrue(formatted.contains("150"))
    }

    @Test
    fun `Format Loto5 opt1+opt2`() {
        val formatted = LotoOptionsHelper.formatLotoLineForPrint("loto5", "12345", setOf(1, 2), 25.0)
        assertTrue(formatted.contains("L5"))
        assertTrue(formatted.contains("12345"))
        assertTrue(formatted.contains("opt1,2"))
        assertTrue(formatted.contains("50"))
    }

    @Test
    fun `Format Loto4 single option`() {
        val formatted = LotoOptionsHelper.formatLotoLineForPrint("loto4", "1234", setOf(1), 100.0)
        assertTrue(formatted.contains("opt1"))
        assertTrue(formatted.contains("100"))
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // formatOptionsCompact Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `Format FULL options compact`() {
        val formatted = LotoOptionsHelper.formatOptionsCompact(setOf(1, 2, 3))
        assertEquals("FULL", formatted)
    }

    @Test
    fun `Format partial options compact`() {
        val formatted = LotoOptionsHelper.formatOptionsCompact(setOf(1, 3))
        assertEquals("1,3", formatted)
    }

    @Test
    fun `Format single option compact`() {
        val formatted = LotoOptionsHelper.formatOptionsCompact(setOf(2))
        assertEquals("2", formatted)
    }

    @Test
    fun `Format empty options compact`() {
        val formatted = LotoOptionsHelper.formatOptionsCompact(emptySet())
        assertEquals("-", formatted)
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // TicketLineWithOptions.effectiveMise Tests
    // ═══════════════════════════════════════════════════════════════════════════

    @Test
    fun `EffectiveMise Loto4 FULL equals mise times 3`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "2346",
            miseBase = 50.0,
            options = setOf(1, 2, 3)
        )
        assertEquals(150.0, line.effectiveMise, 0.001)
    }

    @Test
    fun `EffectiveMise Loto5 2 options equals mise times 2`() {
        val line = TicketLineWithOptions(
            jeu = "loto5",
            valeur = "12345",
            miseBase = 25.0,
            options = setOf(1, 2)
        )
        assertEquals(50.0, line.effectiveMise, 0.001)
    }

    @Test
    fun `EffectiveMise Boule equals miseBase`() {
        val line = TicketLineWithOptions(
            jeu = "boule",
            valeur = "34",
            miseBase = 100.0,
            options = emptySet()
        )
        assertEquals(100.0, line.effectiveMise, 0.001)
    }

    @Test
    fun `EffectiveMise Loto4 empty options equals 0`() {
        val line = TicketLineWithOptions(
            jeu = "loto4",
            valeur = "2346",
            miseBase = 50.0,
            options = emptySet()
        )
        assertEquals(0.0, line.effectiveMise, 0.001)
    }
}
