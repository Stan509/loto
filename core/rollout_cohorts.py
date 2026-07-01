# rollout_cohorts.py – Cohort selection utilities for phased rollouts
"""
Utility module that provides deterministic device‑cohort assignment used by the
feature‑flag system. It does **not** modify any existing flag evaluation logic.
The functions are pure and safe to import from any service (Django, Go, Android).
"""
import logging

logger = logging.getLogger(__name__)


def _device_hash(device_id: str) -> int:
    """Return a deterministic integer hash for a device identifier.

    The implementation mirrors the hashing used elsewhere in the codebase
    (int.from_bytes of the UTF‑8 representation) to guarantee stable bucket
    assignment across services and runs.
    """
    try:
        return int.from_bytes(device_id.encode("utf-8"), "big")
    except Exception as exc:  # pragma: no cover – defensive fallback
        logger.warning(f"Device hash fallback for {device_id}: {exc}")
        return hash(device_id)


def is_canary_device(device_id: str) -> bool:
    """Return ``True`` if the device belongs to the 5 % canary cohort.

    Deterministic bucket: ``hash % 100 < 5``.
    """
    return _device_hash(device_id) % 100 < 5


def is_phase3_device(device_id: str) -> bool:
    """Return ``True`` if the device belongs to the 25 % Phase‑3 cohort.

    This includes the canary bucket (5 %); callers can further differentiate
    via ``get_device_cohort``.
    """
    return _device_hash(device_id) % 100 < 25


def get_device_cohort(device_id: str) -> str:
    """Resolve the cohort identifier for a given device.

    Returns one of ``"CANARY"``, ``"PHASE3"`` or ``"CONTROL"``.
    The order guarantees that a canary device is never reported as Phase 3.
    """
    if is_canary_device(device_id):
        return "CANARY"
    if is_phase3_device(device_id):
        return "PHASE3"
    return "CONTROL"
