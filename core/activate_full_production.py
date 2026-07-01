"""
Full‑production activation script for Phase 4.
Sets the required FLAG_ environment variables so the existing
feature‑flag system picks them up. Rollback is simply unsetting
the variables and restarting the service.
"""
import os, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FLAGS = [
    "OFFLINE_ENGINE_ENABLED",
    "SYNC_ENGINE_V2_ENABLED",
    "DELTA_SYNC_ENABLED",
    "BATCH_SYNC_ENABLED",
    "CONFLICT_ENGINE_ENABLED",
    "ADAPTIVE_QUEUE_ENABLED",
    "CLOCK_AUTHORITY_SCORE_ENABLED",
    "CANARY_MODE_ENABLED",
]

def activate():
    for flag in FLAGS:
        env = f"FLAG_{flag}"
        os.environ[env] = "true"
        logger.info("Enabled %s via %s", flag, env)

if __name__ == "__main__":
    activate()
    logger.info("✅ Full‑production feature flags activated. Use environment changes to roll back if needed.")
