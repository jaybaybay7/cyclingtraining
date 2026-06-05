"""Readiness scoring (R4).

Turns daily wellness (HRV, sleep, Body Battery) into a green/amber/red signal with a
plain reason and an advisory recommendation. HRV is only meaningful against the athlete's
own rolling baseline, so we compare a recent 7-day HRV average to a ~60-day baseline and
flag deviations. Advisory only: it recommends, it never rewrites the plan.

Needs >= 14 days of HRV history before it scores; otherwise it says "baseline building".
"""
from __future__ import annotations

import statistics as st
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Wellness:
    date: date
    hrv: float | None = None           # ms, overnight average
    sleep_score: float | None = None   # 0-100
    body_battery: int | None = None    # morning "charged" value 0-100
    resting_hr: int | None = None


@dataclass
class Readiness:
    date: date
    score: str                  # green | amber | red | baseline_building
    rationale: str
    recommendation: str
    details: dict = field(default_factory=dict)


def _avg(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def score(records: list[Wellness], target: date | None = None) -> Readiness:
    """Score the target date (default: the latest record) from preceding history."""
    records = sorted(records, key=lambda w: w.date)
    if not records:
        return Readiness(target or date.today(), "baseline_building",
                         "No wellness data yet.", "Connect Garmin / sync more days.")
    target = target or records[-1].date
    today = next((w for w in records if w.date == target), records[-1])
    hist = [w for w in records if w.date <= target]

    hrv_series = [w.hrv for w in hist if w.hrv is not None]
    if len(hrv_series) < 14:
        return Readiness(target, "baseline_building",
                         f"Only {len(hrv_series)} days of HRV; need ~14 for a baseline.",
                         "Keep syncing. Until then, go by feel and sleep.",
                         {"hrv_days": len(hrv_series)})

    recent = [w.hrv for w in hist[-7:] if w.hrv is not None]
    base = hrv_series[-60:]
    hrv_7 = _avg(recent)
    base_mean = st.mean(base)
    base_sd = st.pstdev(base) if len(base) > 1 else 0.0
    z = (hrv_7 - base_mean) / base_sd if base_sd else 0.0

    flags: list[str] = []
    amber = red = 0
    if z <= -1.0:
        red += 1; flags.append(f"HRV well below baseline (z={z:.1f})")
    elif z <= -0.5:
        amber += 1; flags.append(f"HRV trending below baseline (z={z:.1f})")
    else:
        flags.append(f"HRV at/above baseline (z={z:+.1f})")

    if today.sleep_score is not None:
        if today.sleep_score < 50:
            red += 1; flags.append(f"poor sleep ({today.sleep_score:.0f})")
        elif today.sleep_score < 65:
            amber += 1; flags.append(f"sub-par sleep ({today.sleep_score:.0f})")
        else:
            flags.append(f"good sleep ({today.sleep_score:.0f})")

    if today.body_battery is not None:
        if today.body_battery < 35:
            amber += 1; flags.append(f"low Body Battery ({today.body_battery})")
        elif today.body_battery >= 70:
            flags.append(f"Body Battery charged ({today.body_battery})")

    if red >= 1 or amber >= 2:
        s = "red"
        rec = "Back off: swap any quality session for easy Z2 or rest. Recovery first."
    elif amber == 1:
        s = "amber"
        rec = "Proceed with caution: keep intensity controlled, drop it if it feels off."
    else:
        s = "green"
        rec = "Cleared to train as planned."

    return Readiness(target, s, "; ".join(flags), rec,
                     {"hrv_7": round(hrv_7, 1), "hrv_baseline": round(base_mean, 1),
                      "z": round(z, 2), "sleep": today.sleep_score,
                      "body_battery": today.body_battery})


if __name__ == "__main__":
    import json
    from pathlib import Path
    store = Path(__file__).resolve().parents[2] / "data" / "wellness.json"
    if not store.exists():
        print("No data/wellness.json yet. Run: python -m src.garmin_source --days 90")
    else:
        rows = json.loads(store.read_text())
        recs = [Wellness(date.fromisoformat(r["date"]), r.get("hrv"), r.get("sleep_score"),
                         r.get("body_battery"), r.get("resting_hr")) for r in rows]
        r = score(recs)
        print(f"{r.date}  {r.score.upper()}\n  {r.rationale}\n  -> {r.recommendation}\n  {r.details}")
