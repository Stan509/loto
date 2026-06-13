package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gateway_go/internal/django"
	"gateway_go/internal/validator"
	"gateway_go/internal/ws"
)

func main() {
	// Configuration via environnement
	addr := getEnv("GATEWAY_ADDR", ":8080")
	redisURL := getEnv("REDIS_URL", "redis://localhost:6379/0")
	validatorAddr := getEnv("VALIDATOR_ADDR", "localhost:50051")
	djangoAPI := getEnv("DJANGO_API_URL", "http://localhost:8000")

	log.Printf("[Gateway] Starting on %s", addr)
	log.Printf("[Gateway] Redis: %s | Validator: %s | Django: %s", redisURL, validatorAddr, djangoAPI)

	// Connexion au Validator Rust (gRPC lazy — reconnexion automatique)
	valClient, err := validator.NewClient(validatorAddr)
	if err != nil {
		log.Printf("[Gateway] WARN — Validator client init failed (will retry lazily): %v", err)
		// On ne log.Fatalf plus : le client gRPC tentera de se reconnecter
	} else {
		log.Printf("[Gateway] Validator client initialized (lazy connect)")
	}
	defer func() {
		if valClient != nil {
			valClient.Close()
		}
	}()

	// Connexion à Django
	djClient := django.NewClient(djangoAPI)

	// Routeur HTTP + WebSocket
	mux := http.NewServeMux()

	// Health check enrichi : vérifie aussi les downstreams
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()

		status := map[string]any{
			"gateway": "ok",
			"redis":   "unknown",
		}

		// Vérifier Validator (gRPC HealthCheck)
		if valClient != nil {
			if _, err := valClient.HealthCheck(ctx); err != nil {
				status["validator"] = fmt.Sprintf("unreachable: %v", err)
				log.Printf("[Gateway] Health — Validator unreachable: %v", err)
			} else {
				status["validator"] = "ok"
			}
		} else {
			status["validator"] = "not_initialized"
		}

		// Vérifier Django (ping léger sur /health/ ou tout endpoint qui répond)
		if djClient != nil {
			if _, statusCode, err := djClient.ForwardTicketBatch(ctx, "/api/agent/ticket/list/", []byte("{}"), nil); err != nil {
				status["django"] = fmt.Sprintf("unreachable: %v", err)
			} else {
				status["django"] = fmt.Sprintf("ok (HTTP %d)", statusCode)
			}
		} else {
			status["django"] = "not_initialized"
		}

		// Déterminer le statut global
		httpStatus := http.StatusOK
		if status["validator"] != "ok" || status["django"] == "not_initialized" {
			httpStatus = http.StatusServiceUnavailable
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(httpStatus)
		json.NewEncoder(w).Encode(status)
	})

	// WebSocket endpoint pour les APK
	wsHub := ws.NewHub(valClient, djClient, redisURL)
	go wsHub.Run()
	mux.HandleFunc("/ws/agent", wsHub.HandleAgentConnection)

	// HTTP fallback pour les tickets (si APK ne supporte pas WS)
	mux.HandleFunc("/api/agent/ticket/create_multi", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		wsHub.HandleHTTPFallback(w, r)
	})

	server := &http.Server{
		Addr:         addr,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
	}

	// Graceful shutdown
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[Gateway] Listen error: %v", err)
		}
	}()
	log.Printf("[Gateway] Listening on %s", addr)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("[Gateway] Shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("[Gateway] Shutdown error: %v", err)
	}
	log.Println("[Gateway] Exited")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
