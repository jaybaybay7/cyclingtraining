"""Stream-based compliance check (R11).

Reads an activity's power stream, classifies what kind of session it actually was
from the *shape* of the file (not the summary), and compares that to what the plan
prescribed for that date. This exists because summary numbers (NP, TSS) can look like
a completed workout when the ride was really a crit: same load, wrong stimulus.

Usage:
    python -m src.analysis.compliance              # last 10 days vs the plan
    python -m src.analysis.compliance --days 21
"""
from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass
from datetime import date

from ..config import Config
from ..intervals_client import IntervalsClient
from ..planning import periodization as period


# ---- metrics -------------------------------------------------------------
@dataclass
class RideMetrics:
    seconds: int
    avg: float
    np: float
    vi: float          # NP / avg -- how stochastic the ride was
    if_: float         # NP / FTP
    max_w: int
    zone_min: dict[str, float]
    surges_per_hr: float
    neuro_frac: float  # fraction of time > 150% FTP


ZONES = [
    ("recovery", 0.0, 0.56), ("endurance", 0.56, 0.75), ("tempo", 0.75, 0.90),
    ("threshold", 0.90, 1.05), ("vo2", 1.05, 1.20), ("anaerobic", 1.20, 1.50),
    ("neuro", 1.50, 99.0),
]


def metrics(watts: list[float], ftp: int) -> RideMetrics:
    n = len(watts)
    avg = sum(watts) / n
    roll: deque = deque(maxlen=30)
    p4 = []
    for x in watts:
        roll.append(x)
        if len(roll) == 30:
            p4.append((sum(roll) / 30) ** 4)
    np = (sum(p4) / len(p4)) ** 0.25 if p4 else avg
    zsec = {z[0]: 0 for z in ZONES}
    for x in watts:
        r = x / ftp
        for name, lo, hi in ZONES:
            if lo <= r < hi:
                zsec[name] += 1
                break
    # distinct surges above 1.25*FTP lasting >= 3 s
    thr = 1.25 * ftp
    surges = run = 0
    for x in watts:
        if x > thr:
            run += 1
        else:
            if run >= 3:
                surges += 1
            run = 0
    if run >= 3:
        surges += 1
    hours = n / 3600
    return RideMetrics(
        seconds=n, avg=avg, np=np, vi=np / avg, if_=np / ftp, max_w=int(max(watts)),
        zone_min={k: round(v / 60, 1) for k, v in zsec.items()},
        surges_per_hr=round(surges / hours, 1) if hours else 0,
        neuro_frac=zsec["neuro"] / n,
    )


# ---- classification ------------------------------------------------------
def classify(m: RideMetrics) -> tuple[str, str]:
    """Return (label, reason). Order matters: check the distinctive shapes first."""
    z = m.zone_min
    thr_plus = z["threshold"] + z["vo2"]
    if m.if_ < 0.60 and m.vi < 1.25 and m.neuro_frac < 0.02:
        return "recovery", f"low intensity (IF {m.if_:.2f}), steady (VI {m.vi:.2f})"
    if m.vi >= 1.35 or (m.surges_per_hr >= 12 and m.neuro_frac >= 0.015):
        return "group_ride_crit", (
            f"stochastic: VI {m.vi:.2f}, {m.surges_per_hr}/hr hard surges, "
            f"{z['neuro']} min neuromuscular")
    if z["vo2"] >= 9 and m.vi < 1.30:
        return "vo2", f"{z['vo2']} min in VO2 zone with controlled variability"
    if z["threshold"] >= 12 and m.vi < 1.25:
        return "threshold", f"{z['threshold']} min sustained at threshold, VI {m.vi:.2f}"
    if m.if_ <= 0.80 and m.vi < 1.35 and thr_plus < 12:
        return "endurance", f"aerobic (IF {m.if_:.2f}), little supra-threshold time"
    return "mixed", f"no single dominant pattern (IF {m.if_:.2f}, VI {m.vi:.2f})"


# Which actual labels satisfy a prescribed kind.
ACCEPT = {
    "threshold": {"threshold"},
    "over_unders": {"threshold", "vo2"},
    "vo2": {"vo2", "threshold"},
    "endurance": {"endurance", "recovery"},
    "openers": {"openers", "endurance", "recovery", "mixed"},
    "group_ride": {"group_ride_crit", "vo2", "mixed"},
    "race": {"group_ride_crit", "threshold", "endurance", "mixed"},
    "other": set(),
}

_MISS_ADVICE = {
    "over_unders": "Intended sustained-threshold stimulus not delivered. This trained your "
                   "punch (already a strength), not your limiter. Get a real threshold session in.",
    "threshold": "Threshold stimulus missed. Schedule a solo structured session so you can "
                 "actually hold the targets.",
    "vo2": "VO2 stimulus missed. The repeated 3-5 min efforts are the point; a group ride "
           "won't reliably deliver them.",
    "endurance": "Was meant to be easy. If it ran hard, it adds fatigue without the aerobic "
                 "benefit and eats into recovery.",
}


@dataclass
class Verdict:
    date: date
    name: str
    prescribed: str
    actual: str
    matched: bool
    reason: str
    note: str


def check(activity: dict, ftp: int, client: IntervalsClient) -> Verdict | None:
    if "Ride" not in (activity.get("type") or ""):
        return None
    d = date.fromisoformat(activity["start_date_local"][:10])
    streams = client.streams(activity["id"], types=("watts",))
    watts = streams.get("watts") or []
    if len(watts) < 60:
        return None
    m = metrics(watts, ftp)
    actual, reason = classify(m)
    presc = period.prescribed_for(d)
    pkind = presc.kind if presc else "other"
    matched = actual in ACCEPT.get(pkind, set()) if pkind != "other" else True
    note = ""
    if pkind == "other":
        note = "No prescribed session on this date (extra ride)."
    elif not matched:
        note = _MISS_ADVICE.get(pkind, f"Prescribed {pkind}, actual looked like {actual}.")
    return Verdict(d, activity.get("name", "")[:40], pkind, actual, matched, reason, note)


def main() -> None:
    days = 10
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    cfg = Config.load()
    c = IntervalsClient(cfg)
    ftp = c.ftp()
    from datetime import timedelta
    today = date.today()
    acts = c.activities((today - timedelta(days=days)).isoformat(), today.isoformat())
    print(f"Compliance check (FTP {ftp} W), last {days} days:\n")
    for a in sorted(acts, key=lambda x: x.get("start_date_local", "")):
        v = check(a, ftp, c)
        if not v:
            continue
        flag = "OK  " if v.matched else "FLAG"
        print(f"[{flag}] {v.date}  prescribed: {v.prescribed:11} actual: {v.actual}")
        print(f"        {v.reason}")
        if v.note:
            print(f"        -> {v.note}")


if __name__ == "__main__":
    main()
