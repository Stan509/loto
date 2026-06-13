import pytest
from django.utils import timezone

@pytest.fixture(autouse=True)
def freeze_time(monkeypatch):
    """Freeze time at 10:00 AM to prevent time-of-day flakes in tirage opening hours tests."""
    import zoneinfo
    tz = zoneinfo.ZoneInfo("America/Port-au-Prince")
    fixed_now = timezone.datetime(2026, 6, 12, 10, 0, 0, tzinfo=tz)
    monkeypatch.setattr("django.utils.timezone.now", lambda: fixed_now)
