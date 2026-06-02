"""Power-profile diagnosis (R3).

Classifies rider type and ranks weaknesses from the mean-max power curve, scored
in W/kg against rough category bands for the four anchor durations that matter for
road and gravel: 5s (neuromuscular), 1min (anaerobic), 5min (VO2max), FTP/20min
(threshold). Threshold and VO2max are weighted as the limiters for endurance racing.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from ..intervals_client import IntervalsClient

# Approx W/kg band ceilings, loosely after Coggan power-profile tables.
# Maps a W/kg value to a 0-5 "level" (5 = world class, 1 = untrained).
BANDS = {
    "5s":   [9.0, 10.6, 12.1, 14.2, 16.0],   # neuromuscular
    "1min": [6.4, 7.6, 8.8, 10.5, 11.5],     # anaerobic (uses 1min watts/kg vs ~higher table)
    "5min": [3.4, 4.4, 5.4, 6.4, 7.0],       # VO2max
    "FTP":  [2.9, 3.6, 4.3, 5.0, 5.6],       # threshold
}
# Weights: limiters for road/gravel get more say in the overall read.
WEIGHTS = {"5s": 0.5, "1min": 0.8, "5min": 1.3, "FTP": 1.4}


def level_for(metric: str, wkg: float) -> float:
    """Interpolated 0-5 level for a W/kg figure on a metric's band."""
    bands = BANDS[metric]
    if wkg <= bands[0]:
        return 1.0 * (wkg / bands[0]) if bands[0] else 1.0
    for i in range(len(bands) - 1):
        if bands[i] <= wkg < bands[i + 1]:
            frac = (wkg - bands[i]) / (bands[i + 1] - bands[i])
            return 1 + i + frac
    return 5.0


@dataclass
class Diagnosis:
    weight_kg: float
    points: dict[str, dict]      # metric -> {watts, wkg, level}
    weaknesses: list[str]        # metrics ranked weakest-first (by level)
    rider_type: str
    summary: str


def diagnose(curve: dict[str, int], ftp: int, weight_kg: float) -> Diagnosis:
    raw = {
        "5s": curve.get("5s"),
        "1min": curve.get("1min"),
        "5min": curve.get("5min"),
        "FTP": ftp,
    }
    points: dict[str, dict] = {}
    for m, w in raw.items():
        if not w:
            continue
        wkg = w / weight_kg
        points[m] = {"watts": w, "wkg": round(wkg, 2), "level": round(level_for(m, wkg), 2)}

    ranked = sorted(points, key=lambda m: points[m]["level"])
    weak = [m for m in ranked if WEIGHTS.get(m, 1) >= 1.0]  # focus on limiters

    sprint = points.get("5s", {}).get("level", 0)
    thresh = points.get("FTP", {}).get("level", 0)
    if sprint - thresh >= 1.0:
        rider_type = "Explosive sprinter on an under-developed aerobic engine"
    elif thresh - sprint >= 1.0:
        rider_type = "Diesel / time-trial type, sprint is the relative gap"
    else:
        rider_type = "Balanced all-rounder"

    worst = ranked[0] if ranked else "?"
    summary = (
        f"{rider_type}. Weakest area: {worst} "
        f"({points.get(worst, {}).get('wkg', '?')} W/kg). "
        f"Priority for road/gravel: build {', '.join(weak[:2])}."
    )
    return Diagnosis(weight_kg, points, ranked, rider_type, summary)


if __name__ == "__main__":
    cfg = Config.load()
    c = IntervalsClient(cfg)
    weight = cfg.athlete_weight_kg or c.profile().get("athlete", {}).get("weight") or 74.0
    d = diagnose(c.power_curve("all"), c.ftp(), float(weight))
    print(d.summary)
    print("\nProfile (weakest first):")
    for m in d.weaknesses:
        p = d.points[m]
        print(f"  {m:>5}: {p['watts']:>4} W  {p['wkg']:>5} W/kg  level {p['level']}/5")
