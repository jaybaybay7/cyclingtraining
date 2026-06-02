"""Readiness scoring (R4) - STUB for Phase 1.

Computes a daily green/amber/red readiness signal from HRV (vs rolling baseline),
sleep, Body Battery, and recent load. Advisory only: it recommends, it does not
auto-change the plan (PRD non-goal).

Plan:
  - HRV baseline: 7-day vs 60-day rolling mean; flag deviations beyond ~1 SD.
  - Require >= 14 days of history before scoring; otherwise return "baseline building".
  - Blend HRV deviation, sleep score, Body Battery, and TSB into one score + rationale.
Inputs come from garmin_source (HRV, sleep, Body Battery) and intervals_client (load/TSB).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Readiness:
    date: str
    score: str          # "green" | "amber" | "red" | "baseline_building"
    rationale: str


def score_day(*args, **kwargs) -> Readiness:  # noqa: ANN002, ANN003
    raise NotImplementedError("Readiness scoring lands in Phase 1 (R4).")
