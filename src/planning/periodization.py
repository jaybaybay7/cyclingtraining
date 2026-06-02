"""Periodization + weekly builder (R5, R6) - STUB for Phase 2.

Works backward from A-race dates into base / build / peak / taper, then lays sessions
against available days and the weekly hour budget. Prioritizes the diagnosed limiters
(threshold, VO2max) and keeps the sprint on maintenance. Respects cross-training load
(hockey, climbing).

Blocked on: A-race dates, weekly hours + free days, ERG availability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class ARace:
    name: str
    date: date
    discipline: str   # "road" | "gravel"
    priority: str     # "A"


def build_macro(a_races: list[ARace], today: date) -> list[dict]:
    """Return a list of week dicts with phase + load target. Phase 2."""
    raise NotImplementedError("Periodization lands in Phase 2 (R5/R6).")
