# Gaboom Central — Guide Stress Test

## ⚠️ Prérequis

Cette machine de développement **Windows n'a pas Docker Desktop installé**.  
Les commandes ci-dessous doivent être exécutées sur une machine/serveur avec **Docker Engine** et **Docker Compose**.

---

## 🚀 Phase 1 : Mise en service

```bash
cd /chemin/vers/Gaboom\ Central

# 1. Lancer la stack complète
docker compose up --build -d

# 2. Attendre 15 secondes que les services se stabilisent
sleep 15

# 3. Vérifier les healthchecks
docker compose ps

# 4. Rendre exécutable et lancer le smoke test
chmod +x smoke_test.sh
./smoke_test.sh

# 5. Si le smoke test passe, vérifier les logs
docker compose logs --tail=20 gateway
docker compose logs --tail=20 validator
```

---

## 📈 Phase 2 : Stress Test (10 000 requêtes)

### A. Compiler le générateur de charge

```bash
cd services/gateway_go

go build -o stress cmd/stress/main.go
```

### B. Lancer le test (mode Gateway)

```bash
# Test via la Gateway Go (flux complet : Gateway → Validator → Django)
./stress \
  -url http://localhost:8080/api/agent/ticket/create_multi \
  -workers 500 \
  -n 10000 \
  -ramp 5s \
  -timeout 10s \
  -token "YOUR_JWT_TOKEN"
```

### C. Lancer le test (mode Direct Django — baseline)

```bash
# Test direct sur Django (sans passer par Gateway/Validator)
./stress \
  -url http://localhost:8000/api/agent/ticket/create_multi \
  -workers 500 \
  -n 10000 \
  -ramp 5s \
  -timeout 10s \
  -token "YOUR_JWT_TOKEN"
```

### D. Options du générateur

| Flag | Défaut | Description |
|------|--------|-------------|
| `-url` | `http://localhost:8080/api/agent/ticket/create_multi` | URL cible |
| `-workers` | `500` | Goroutines concurrentes |
| `-n` | `10000` | Nombre total de requêtes |
| `-ramp` | `5s` | Temps de montée en charge |
| `-timeout` | `10s` | Timeout HTTP |
| `-token` | `""` | Bearer JWT |
| `-v` | `false` | Mode verbeux |

---

## 🔍 Ce qu'on observe

| Service | Métrique | Outil |
|---------|----------|-------|
| **Gateway Go** | Rejets de connexion ? | Logs + résultats stress test |
| **Validator Rust** | CPU saturation HMAC ? | `docker stats gaboom_validator` |
| **PostgreSQL** | Écritures empilées ? | `docker compose logs --tail=50 db` |
| **Redis** | File d'attente pleine ? | `redis-cli info stats` |

---

## 📊 Interprétation des résultats

```
Durée totale:     12.45s
Requêtes totales: 10000
Succès (HTTP 2xx): 10000 (100.00%)
Throughput:       802.41 req/s

Latence:
  P50:  45ms
  P95:  120ms
  P99:  250ms
```

- **P99 < 500ms** → ✅ Performance acceptable
- **P99 > 1s** → ⚠️ Vérifier PostgreSQL (index, locks)
- **Erreurs réseau > 0** → ⚠️ Augmenter workers ou vérifier Gateway
