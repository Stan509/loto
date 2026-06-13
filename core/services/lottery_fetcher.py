from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any
import logging

import requests

from accounts.models import LotteryAPIConfig


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchedLotteryResult:
    code: str
    numbers: list[int]
    loto3: str | None
    date: date


def fetch_results() -> list[FetchedLotteryResult]:
    """Récupère les résultats depuis une API externe.

    Configurée par SuperAdmin via LotteryAPIConfig (globale).
    Si la config est absente ou inactive: retourne [].
    """
    config = LotteryAPIConfig.objects.first()
    if not config or not config.is_active:
        return []

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {config.api_key}",
    }

    logger.info("Lottery API fetch start url=%s", config.api_url)
    resp = requests.get(config.api_url, headers=headers, timeout=10)
    logger.info("Lottery API fetch done status=%s", resp.status_code)
    resp.raise_for_status()

    raw = resp.text

    payload: Any = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Invalid payload: expected list")

    out: list[FetchedLotteryResult] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        nums = item.get("numbers")
        loto3_api = item.get("loto3")
        dt = item.get("date")
        if not code:
            continue
        if not isinstance(nums, list) or len(nums) != 3:
            continue
        try:
            numbers = [int(n) for n in nums]
        except Exception:
            continue
        try:
            d = date.fromisoformat(str(dt))
        except Exception:
            continue

        loto3_str = None
        if loto3_api is not None and str(loto3_api).strip() != "":
            loto3_str = str(loto3_api).strip()

        out.append(FetchedLotteryResult(code=code, numbers=numbers, loto3=loto3_str, date=d))

    return out
