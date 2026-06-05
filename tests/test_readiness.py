"""Tests for readiness scoring (R4). Synthetic wellness, no network.

Run: python -m tests.test_readiness
"""
from __future__ import annotations

from datetime import date, timedelta

from src.analysis.readiness import Wellness, score


def _series(hrv: list[float], sleep: float, bb: int) -> list[Wellness]:
    n = len(hrv)
    start = date(2026, 1, 1)
    return [Wellness(start + timedelta(days=i), hrv[i], sleep, bb) for i in range(n)]


def test_baseline_building() -> None:
    recs = _series([50, 49] * 5, sleep=85, bb=80)  # 10 days
    assert score(recs).score == "baseline_building"


def test_green() -> None:
    recs = _series([49, 51] * 30, sleep=85, bb=80)  # steady HRV, good sleep/BB
    r = score(recs)
    assert r.score == "green", r.rationale


def test_red_on_suppressed_hrv_and_poor_sleep() -> None:
    hrv = [49 if i % 2 else 51 for i in range(53)] + [40] * 7  # last week well below
    recs = _series(hrv, sleep=45, bb=30)  # poor sleep + low body battery too
    r = score(recs)
    assert r.score == "red", (r.score, r.rationale, r.details)


def test_amber_single_signal() -> None:
    hrv = [49 if i % 2 else 51 for i in range(54)] + [45] * 6  # mild HRV dip only
    recs = _series(hrv, sleep=80, bb=75)
    r = score(recs)
    assert r.score in {"amber", "red"}, (r.score, r.rationale)


if __name__ == "__main__":
    test_baseline_building(); print("baseline_building: OK")
    test_green(); print("green: OK")
    test_red_on_suppressed_hrv_and_poor_sleep(); print("red: OK")
    test_amber_single_signal(); print("amber: OK")
    print("All readiness tests passed.")
