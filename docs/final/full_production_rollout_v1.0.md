# Full Production Rollout – Phase 4 (100 % GO LIVE)

## Goal
Activate the complete feature set for every POS device while keeping the ability to rollback instantly via environment‑flag toggles.

## Activation Matrix
| Feature Flag                     | Desired State |
|----------------------------------|:-------------:|
| `OFFLINE_ENGINE_ENABLED`         | **ON** |
| `SYNC_ENGINE_V2_ENABLED`         | **ON** |
| `DELTA_SYNC_ENABLED`             | **ON** |
| `BATCH_SYNC_ENABLED`             | **ON** |
| `CONFLICT_ENGINE_ENABLED`        | **ON** |
| `ADAPTIVE_QUEUE_ENABLED`         | **ON** |
| `CLOCK_AUTHORITY_SCORE_ENABLED` | **ON** |
| `CANARY_MODE_ENABLED`            | **ON** (segmentation only) |

## Safety Guarantees
- No schema changes or migrations.
- All flags are controlled via `FLAG_<NAME>` environment variables.
- Rollback is a matter of clearing those variables and restarting services.

## Verification Checklist
1. `pytest -q` (46/46 passed)
2. `go test ./...` (all packages pass)
3. `cargo build` (Rust validates without warnings)
4. Cohort validation (`python -m core.cohort_validation`)
5. Load‑test ≥ 10 000 concurrent POS, 50 000 tickets/min.
6. Observe Grafana dashboards – no metric exceeds thresholds.

## Post‑Activation Monitoring (first 30 min)
- Ticket success rate
- Sync backlog depth
- Crash rate (Android fleet)
- Redis queue depth
- Rust validation error count

If any threshold is breached, immediately disable the offending flag(s) via environment variables.
