"""Configuration loaded from environment / .env.

Secrets live in .env (git-ignored). Use .env.example as the template.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv optional; env vars may be set another way
    pass


@dataclass(frozen=True)
class Config:
    intervals_api_key: str
    intervals_athlete_id: str
    garmin_email: str | None
    garmin_password: str | None
    athlete_weight_kg: float | None

    @classmethod
    def load(cls) -> "Config":
        key = os.environ.get("INTERVALS_API_KEY", "")
        athlete = os.environ.get("INTERVALS_ATHLETE_ID", "")
        if not key or not athlete:
            raise RuntimeError(
                "Missing INTERVALS_API_KEY or INTERVALS_ATHLETE_ID. "
                "Copy .env.example to .env and fill it in."
            )
        weight = os.environ.get("ATHLETE_WEIGHT_KG")
        return cls(
            intervals_api_key=key,
            intervals_athlete_id=athlete,
            garmin_email=os.environ.get("GARMIN_EMAIL") or None,
            garmin_password=os.environ.get("GARMIN_PASSWORD") or None,
            athlete_weight_kg=float(weight) if weight else None,
        )
