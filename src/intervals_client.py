"""Intervals.icu REST client.

Implements R1 (ingest) and the R9 workout-push surface. Auth is HTTP Basic with
username literally "API_KEY" and the API key as the password.

Validated endpoints (2026-06-02):
  GET /athlete/{id}/profile
  GET /athlete/{id}/sport-settings
  GET /athlete/{id}/power-curves?curves=all&type=Ride
  GET /athlete/{id}/activities?oldest=&newest=
  GET /athlete/{id}/wellness?oldest=&newest=
"""
from __future__ import annotations

from typing import Any

import requests

from .config import Config

BASE = "https://intervals.icu/api/v1"

# Durations (seconds) we care about for the power profile.
KEY_DURATIONS = {
    "5s": 5, "15s": 15, "30s": 30, "1min": 60, "2min": 120,
    "5min": 300, "8min": 480, "10min": 600, "20min": 1200,
    "30min": 1800, "60min": 3600,
}


class IntervalsClient:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config.load()
        self._auth = ("API_KEY", self.cfg.intervals_api_key)
        self._aid = self.cfg.intervals_athlete_id

    def _get(self, path: str, **params: Any) -> Any:
        r = requests.get(
            f"{BASE}/athlete/{self._aid}{path}",
            auth=self._auth,
            params=params or None,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    # --- reads -------------------------------------------------------------
    def profile(self) -> dict:
        return self._get("/profile")

    def sport_settings(self) -> list[dict]:
        return self._get("/sport-settings")

    def ftp(self) -> int | None:
        for s in self.sport_settings():
            if "Ride" in (s.get("types") or []):
                return s.get("ftp")
        return None

    def power_curve(self, window: str = "all", sport: str = "Ride") -> dict:
        """Return {duration_label: watts} for the mean-max curve.

        window: 'all', '90d', '42d', etc. (Intervals.icu curve ids).
        """
        data = self._get("/power-curves", curves=window, type=sport)
        curve = data["list"][0]
        secs = curve["secs"]
        watts = curve.get("watts") or curve.get("values")
        out: dict[str, int] = {}
        for label, t in KEY_DURATIONS.items():
            if t in secs:
                out[label] = watts[secs.index(t)]
        return out

    def activities(self, oldest: str, newest: str) -> list[dict]:
        return self._get("/activities", oldest=oldest, newest=newest)

    def wellness(self, oldest: str, newest: str) -> list[dict]:
        return self._get("/wellness", oldest=oldest, newest=newest)

    def streams(self, activity_id: str,
                types: tuple[str, ...] = ("watts", "heartrate", "time")) -> dict[str, list]:
        """Return {stream_type: [samples]} for an activity. The streams endpoint
        lives under /activity/{id}, not /athlete/{id}, so we build the URL directly."""
        r = requests.get(
            f"{BASE}/activity/{activity_id}/streams",
            auth=self._auth,
            params={"types": ",".join(types)},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return {x["type"]: x["data"] for x in data}
        return data

    # --- writes (R9: push structured workouts) -----------------------------
    def create_event(self, event: dict) -> dict:
        """Create a calendar event. For a structured workout pass category
        'WORKOUT', start_date_local, type 'Ride', name, and a `description` in
        Intervals.icu's workout-text syntax. Intervals.icu parses it into a
        workout_doc and syncs it to the Garmin head unit."""
        r = requests.post(
            f"{BASE}/athlete/{self._aid}/events", auth=self._auth, json=event, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def update_event(self, event_id: int, fields: dict) -> dict:
        r = requests.put(
            f"{BASE}/athlete/{self._aid}/events/{event_id}",
            auth=self._auth, json=fields, timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def delete_event(self, event_id: int) -> None:
        r = requests.delete(
            f"{BASE}/athlete/{self._aid}/events/{event_id}", auth=self._auth, timeout=30
        )
        r.raise_for_status()

    def events(self, oldest: str, newest: str, category: str = "WORKOUT") -> list[dict]:
        return self._get("/events", oldest=oldest, newest=newest, category=category)


if __name__ == "__main__":
    c = IntervalsClient()
    p = c.profile()["athlete"]
    print(f"Athlete: {p['name']} ({p['id']}) - {p.get('city')}")
    print(f"FTP: {c.ftp()} W")
    print("All-time power curve:")
    for label, w in c.power_curve("all").items():
        print(f"  {label:>6}: {w} W")
