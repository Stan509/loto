#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Smoke Test — Gaboom Central Multi-Service Stack
# Vérifie que Django, Gateway Go et Validator Rust communiquent correctement.
# ═══════════════════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DJANGO_URL="${DJANGO_URL:-http://localhost:8000}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
VALIDATOR_ADDR="${VALIDATOR_ADDR:-localhost:50051}"

echo "═══════════════════════════════════════════════════════════════════"
echo "  Gaboom Central — Smoke Test"
echo "═══════════════════════════════════════════════════════════════════"
echo "  Django:   $DJANGO_URL"
echo "  Gateway:  $GATEWAY_URL"
echo "  Validator (gRPC): $VALIDATOR_ADDR"
echo "═══════════════════════════════════════════════════════════════════"
echo

PASS=0
FAIL=0

# ─── Helper ───────────────────────────────────────────────────────────────
_check() {
    local name="$1"
    local cmd="$2"
    echo -n "  [TEST] $name ... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((PASS++))
    else
        echo -e "${RED}FAIL${NC}"
        ((FAIL++))
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# 1. Django
# ═══════════════════════════════════════════════════════════════════════════
echo "--- Django ($DJANGO_URL) ---"
_check "Django répond sur /admin/login/" \
    "curl -s -o /dev/null -w '%{http_code}' $DJANGO_URL/admin/login/ | grep -qE '200|302|403'"
_check "Django API /api/agent/ (CORS/auth check)" \
    "curl -s -o /dev/null -w '%{http_code}' $DJANGO_URL/api/agent/ | grep -qE '200|401|403'"

# ═══════════════════════════════════════════════════════════════════════════
# 2. Gateway Go
# ═══════════════════════════════════════════════════════════════════════════
echo
echo "--- Gateway Go ($GATEWAY_URL) ---"
_check "Gateway health check" \
    "curl -s -o /dev/null -w '%{http_code}' $GATEWAY_URL/health | grep -q '200'"
_check "Gateway WebSocket endpoint reachable" \
    "curl -s -o /dev/null -w '%{http_code}' -N -H 'Upgrade: websocket' -H 'Connection: Upgrade' $GATEWAY_URL/ws/agent | grep -qE '400|426|101'"
_check "Gateway HTTP fallback /api/agent/ticket/create_multi (OPTIONS/POST)" \
    "curl -s -o /dev/null -w '%{http_code}' -X OPTIONS $GATEWAY_URL/api/agent/ticket/create_multi | grep -qE '200|405'"

# ═══════════════════════════════════════════════════════════════════════════
# 3. Validator Rust (via Gateway proxy gRPC → ou grpcurl direct)
# ═══════════════════════════════════════════════════════════════════════════
echo
echo "--- Validator Rust ($VALIDATOR_ADDR) ---"

# Si grpcurl est disponible, tester directement
if command -v grpcurl >/dev/null 2>&1; then
    _check "Validator gRPC HealthCheck (direct)" \
        "grpcurl -plaintext -d '{}' $VALIDATOR_ADDR validator.Validator/HealthCheck | grep -q 'ok'"
    _check "Validator gRPC SignTicket (direct)" \
        "grpcurl -plaintext -d '{\"payload\":{\"ticket_uuid\":\"test\",\"agent_id\":\"a1\",\"borlette_id\":\"b1\",\"total_mise\":10.0,\"timestamp\":$(date +%s)}}' $VALIDATOR_ADDR validator.Validator/SignTicket | grep -q 'signature'"
else
    echo -e "  ${YELLOW}SKIP${NC} grpcurl non installé — test via Gateway health instead"
    _check "Validator reachable via Gateway health" \
        "curl -s $GATEWAY_URL/health | grep -q 'validator'"
fi

# ═══════════════════════════════════════════════════════════════════════════
# 4. Redis (via les services)
# ═══════════════════════════════════════════════════════════════════════════
echo
echo "--- Redis ---"
if command -v redis-cli >/dev/null 2>&1; then
    _check "Redis ping local" \
        "redis-cli ping | grep -q 'PONG'"
else
    echo -e "  ${YELLOW}SKIP${NC} redis-cli non installé — Redis testé indirectement par Django/Gateway"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Résumé
# ═══════════════════════════════════════════════════════════════════════════
echo
echo "═══════════════════════════════════════════════════════════════════"
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}✓ TOUS LES TESTS PASSENT ($PASS/$((PASS+FAIL)))${NC}"
    echo "═══════════════════════════════════════════════════════════════════"
    exit 0
else
    echo -e "  ${RED}✗ $FAIL ÉCHEC(S) / $PASS PASS${NC}"
    echo "═══════════════════════════════════════════════════════════════════"
    exit 1
fi
