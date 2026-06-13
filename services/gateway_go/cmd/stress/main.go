package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"sync"
	"syscall"
	"time"
)

// ─── Configuration CLI ─────────────────────────────────────────────────────
var (
	targetURL   = flag.String("url", "http://localhost:8080/api/agent/ticket/create_multi", "URL cible (Gateway ou Django)")
	workers     = flag.Int("workers", 500, "Nombre de workers concurrents (goroutines)")
	totalReqs   = flag.Int("n", 10000, "Nombre total de requêtes à envoyer")
	rampUp      = flag.Duration("ramp", 5*time.Second, "Temps de montée en charge (répartition des workers)")
	timeout     = flag.Duration("timeout", 10*time.Second, "Timeout HTTP par requête")
	jwtToken    = flag.String("token", "", "Bearer token JWT (optionnel)")
	verbose     = flag.Bool("v", false, "Mode verbeux (affiche chaque requête)")
)

// ─── Statistiques ──────────────────────────────────────────────────────────
type result struct {
	latency   time.Duration
	status    int
	err       error
	success   bool
}

func main() {
	flag.Parse()

	fmt.Println("╔════════════════════════════════════════════════════════════════╗")
	fmt.Println("║     Gaboom Central — Stress Test Generator                   ║")
	fmt.Println("╚════════════════════════════════════════════════════════════════╝")
	fmt.Printf("Target:  %s\n", *targetURL)
	fmt.Printf("Workers: %d | Total: %d | Ramp: %v | Timeout: %v\n", *workers, *totalReqs, *rampUp, *timeout)
	fmt.Println()

	// Contexte annulable (Ctrl+C)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
		<-sig
		fmt.Println("\n[STRESS] Arrêt demandé...")
		cancel()
	}()

	// HTTP client optimisé pour haute concurrence
	client := &http.Client{
		Timeout: *timeout,
		Transport: &http.Transport{
			MaxIdleConns:        *workers * 2,
			MaxIdleConnsPerHost: *workers * 2,
			IdleConnTimeout:     30 * time.Second,
			DisableCompression:  true,
		},
	}

	// Canal de résultats (bufferisé pour éviter le blocage)
	results := make(chan result, *totalReqs)

	// WaitGroup pour attendre tous les workers
	var wg sync.WaitGroup

	// Démarrer les workers avec ramp-up
	startTime := time.Now()
	reqPerWorker := *totalReqs / *workers
	remainder := *totalReqs % *workers

	for i := 0; i < *workers; i++ {
		count := reqPerWorker
		if i < remainder {
			count++
		}
		if count == 0 {
			continue
		}

		wg.Add(1)
		go worker(ctx, client, i, count, results, &wg)

		// Ramp-up : espacer le démarrage des workers
		if *rampUp > 0 && i < *workers-1 {
			time.Sleep(*rampUp / time.Duration(*workers))
		}
	}

	// Goroutine pour fermer le canal de résultats une fois tous les workers terminés
	go func() {
		wg.Wait()
		close(results)
	}()

	// Collecter et analyser les résultats
	stats := analyze(results)
	duration := time.Since(startTime)

	// ─── Affichage des résultats ─────────────────────────────────────────────
	fmt.Println()
	fmt.Println("═══════════════════════════════════════════════════════════════════")
	fmt.Println("                     RÉSULTATS DU STRESS TEST")
	fmt.Println("═══════════════════════════════════════════════════════════════════")
	fmt.Printf("  Durée totale:     %v\n", duration.Truncate(time.Millisecond))
	fmt.Printf("  Requêtes totales: %d\n", stats.total)
	fmt.Printf("  Succès (HTTP 2xx): %d (%.2f%%)\n", stats.success, percent(stats.success, stats.total))
	fmt.Printf("  Échecs:           %d (%.2f%%)\n", stats.failures, percent(stats.failures, stats.total))
	fmt.Printf("  Erreurs réseau:   %d\n", stats.networkErrors)
	fmt.Printf("  Throughput:       %.2f req/s\n", float64(stats.total)/duration.Seconds())
	fmt.Println()
	fmt.Println("  ─── Latence ───")
	fmt.Printf("    Minimum:  %v\n", stats.minLatency)
	fmt.Printf("    Moyenne:  %v\n", stats.avgLatency)
	fmt.Printf("    P50:      %v\n", stats.p50)
	fmt.Printf("    P95:      %v\n", stats.p95)
	fmt.Printf("    P99:      %v\n", stats.p99)
	fmt.Printf("    Maximum:  %v\n", stats.maxLatency)
	fmt.Println()
	fmt.Println("  ─── Répartition HTTP ───")
	for status, count := range stats.statusCodes {
		fmt.Printf("    HTTP %d: %d\n", status, count)
	}
	fmt.Println("═══════════════════════════════════════════════════════════════════")

	if stats.failures > 0 {
		fmt.Println("⚠️  Des échecs ont été détectés. Vérifiez les logs des services.")
		os.Exit(1)
	}
	fmt.Println("✅ Toutes les requêtes ont réussi.")
}

// ─── Worker ────────────────────────────────────────────────────────────────
func worker(ctx context.Context, client *http.Client, id, count int, results chan<- result, wg *sync.WaitGroup) {
	defer wg.Done()

	for i := 0; i < count; i++ {
		select {
		case <-ctx.Done():
			return
		default:
		}

		payload := generatePayload(id, i)
		body, _ := json.Marshal(payload)

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, *targetURL, bytes.NewReader(body))
		if err != nil {
			results <- result{err: err, success: false}
			continue
		}
		req.Header.Set("Content-Type", "application/json")
		if *jwtToken != "" {
			req.Header.Set("Authorization", "Bearer "+*jwtToken)
		}

		start := time.Now()
		resp, err := client.Do(req)
		latency := time.Since(start)

		if err != nil {
			results <- result{latency: latency, err: err, success: false}
			if *verbose {
				log.Printf("[W%d] ERR: %v", id, err)
			}
			continue
		}
		resp.Body.Close()

		success := resp.StatusCode >= 200 && resp.StatusCode < 300
		results <- result{latency: latency, status: resp.StatusCode, success: success}

		if *verbose {
			log.Printf("[W%d] HTTP %d | %v", id, resp.StatusCode, latency)
		}
	}
}

// ─── Génération de payload ─────────────────────────────────────────────────
func generatePayload(workerID, reqID int) map[string]any {
	// Payload réaliste pour api_ticket_create_multi
	return map[string]any{
		"tirage_ids": []string{"11111111-1111-1111-1111-111111111111"},
		"entries": []map[string]any{
			{"game": "boule", "number": fmt.Sprintf("%02d", (workerID+reqID)%100), "stake": 10.0},
			{"game": "mariage", "number": fmt.Sprintf("%02dx%02d", (workerID)%100, (workerID+1)%100), "stake": 5.0},
		},
		"session_key": "stress-test-session",
	}
}

// ─── Analyse statistique ───────────────────────────────────────────────────
type summary struct {
	total         int
	success       int
	failures      int
	networkErrors int
	minLatency    time.Duration
	maxLatency    time.Duration
	avgLatency    time.Duration
	p50           time.Duration
	p95           time.Duration
	p99           time.Duration
	statusCodes   map[int]int
}

func analyze(results <-chan result) summary {
	var latencies []time.Duration
	s := summary{
		minLatency:  math.MaxInt64,
		statusCodes: make(map[int]int),
	}

	for r := range results {
		s.total++
		if r.success {
			s.success++
		} else {
			s.failures++
		}
		if r.err != nil {
			s.networkErrors++
		}
		if r.status > 0 {
			s.statusCodes[r.status]++
		}
		if r.latency > 0 {
			latencies = append(latencies, r.latency)
			if r.latency < s.minLatency {
				s.minLatency = r.latency
			}
			if r.latency > s.maxLatency {
				s.maxLatency = r.latency
			}
		}
	}

	if len(latencies) == 0 {
		s.minLatency = 0
		return s
	}

	sort.Slice(latencies, func(i, j int) bool { return latencies[i] < latencies[j] })

	var sum time.Duration
	for _, d := range latencies {
		sum += d
	}
	s.avgLatency = sum / time.Duration(len(latencies))
	s.p50 = percentile(latencies, 0.50)
	s.p95 = percentile(latencies, 0.95)
	s.p99 = percentile(latencies, 0.99)

	return s
}

func percentile(sorted []time.Duration, p float64) time.Duration {
	if len(sorted) == 0 {
		return 0
	}
	idx := int(math.Ceil(p*float64(len(sorted)))) - 1
	if idx < 0 {
		idx = 0
	}
	if idx >= len(sorted) {
		idx = len(sorted) - 1
	}
	return sorted[idx]
}

func percent(part, total int) float64 {
	if total == 0 {
		return 0
	}
	return float64(part) * 100.0 / float64(total)
}
