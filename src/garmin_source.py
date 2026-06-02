"""Garmin wellness ingest via GarminDB (R2) - STUB for Phase 1.

Intervals.icu does NOT carry this athlete's HRV, sleep, resting HR, or Body Battery,
so GarminDB is the source of truth for readiness inputs.

Plan:
  - Use GarminDB to sync Garmin Connect into local SQLite (handles MFA on first login).
  - Read HRV, sleep score + stages, resting HR, Body Battery, stress into a normalized table.
  - Missing days are stored as null, never fabricated (R2 acceptance criterion).

Setup (run once):
    pip install garmindb
    garmindb_cli.py --all --download --import --analyze
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Wellness:
    date: str
    hrv: float | None
    sleep_score: float | None
    resting_hr: int | None
    body_battery: int | None


def load_wellness(oldest: str, newest: str) -> list[Wellness]:
    raise NotImplementedError("GarminDB ingest lands in Phase 1 (R2).")
