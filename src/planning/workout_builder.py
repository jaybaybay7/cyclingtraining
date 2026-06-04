"""Structured workout builder + Intervals.icu push (R9).

Builds workouts in Intervals.icu's workout-text syntax (targets as % of FTP, so they
travel with your fitness) and pushes them to the calendar, where they sync to Garmin.

Library is keyed by workout name. Targets are %FTP ranges; Intervals.icu resolves them
to watts against your current FTP and builds the structured workout for the head unit.

Usage:
    python -m src.planning.workout_builder 2026-06-04 sweet_spot_2x15
    python -m src.planning.workout_builder --list
"""
from __future__ import annotations

import sys
from datetime import date

from ..config import Config
from ..intervals_client import IntervalsClient

# Short lap-press step inserted after each warmup so you can settle into position;
# "Press lap" sets until_lap_press=true, a minimum duration is required.
_LAP = "\n\nGet in position\n- 1m 55% Press lap"

# name -> (title, description in Intervals.icu workout-text syntax)
WORKOUTS: dict[str, tuple[str, str]] = {
    "sweet_spot_2x15": (
        "Sweet-Spot Threshold 2x15",
        f"Warmup\n- 15m ramp 50-75%{_LAP}\n\nSweet Spot 2x\n- 15m 88-95%\n- 5m 55%\n\nCooldown\n- 10m 50%",
    ),
    "threshold_2x15": (
        "Threshold 2x15",
        f"Warmup\n- 15m ramp 50-78%{_LAP}\n\nThreshold 2x\n- 15m 95-100%\n- 5m 55%\n\nCooldown\n- 10m 50%",
    ),
    "over_unders_3x9": (
        "Threshold Over-Unders 3x9",
        f"Warmup\n- 15m ramp 50-78%{_LAP}\n\nOver-Unders 3x\n- 2m 90%\n- 1m 106%\n- 2m 90%\n- 1m 106%\n"
        "- 2m 90%\n- 1m 106%\n- 4m 55%\n\nCooldown\n- 10m 50%",
    ),
    "vo2_5x3": (
        "VO2max 5x3",
        f"Warmup\n- 15m ramp 50-85%{_LAP}\n\nVO2 5x\n- 3m 108-115%\n- 3m 50%\n\nThreshold\n- 10m 92-98%\n"
        "\nCooldown\n- 8m 50%",
    ),
    "openers": (
        "Pre-Race Openers",
        f"Warmup\n- 12m ramp 45-70%{_LAP}\n\nOpeners 3x\n- 3m 92-98%\n- 3m 50%\n\nSprints 3x\n- 30s 150%\n"
        "- 2m 50%\n\nCooldown\n- 8m 45%",
    ),
    "endurance_90": (
        "Endurance Z2 90m",
        "- 5m ramp 45-60%\n- 80m 60-72%\n- 5m 50%",
    ),
}


def build_event(d: date, key: str) -> dict:
    if key not in WORKOUTS:
        raise KeyError(f"Unknown workout '{key}'. Options: {', '.join(WORKOUTS)}")
    title, desc = WORKOUTS[key]
    return {
        "category": "WORKOUT",
        "start_date_local": f"{d.isoformat()}T00:00:00",
        "type": "Ride",
        "name": title,
        "description": desc,
    }


def push(d: date, key: str, client: IntervalsClient | None = None) -> dict:
    client = client or IntervalsClient(Config.load())
    return client.create_event(build_event(d, key))


def main() -> None:
    if "--list" in sys.argv:
        for k, (title, _) in WORKOUTS.items():
            print(f"  {k:18} {title}")
        return
    if len(sys.argv) < 3:
        print("usage: python -m src.planning.workout_builder <YYYY-MM-DD> <workout_key>")
        print("       python -m src.planning.workout_builder --list")
        sys.exit(1)
    d = date.fromisoformat(sys.argv[1])
    key = sys.argv[2]
    ev = push(d, key)
    print(f"Created '{ev.get('name')}' (id {ev.get('id')}) on {d}. "
          f"Duration ~{round((ev.get('workout_doc') or {}).get('duration', 0) / 60)} min. "
          f"Syncs to Garmin from the Intervals.icu calendar.")


if __name__ == "__main__":
    main()
