"""Periodization + weekly builder (R5, R6).

Counts backward from an A-race into a phase sequence ending in taper, then lays
sessions onto the athlete's ride days. Session targets are computed from FTP, so
they update if FTP changes. For short runways (a few weeks) this produces a
specific-prep + taper block; longer runways add more build weeks up front.

Sessions are templated per phase and tuned to this athlete: aerobic durability and
threshold are the priority (his limiters), the sprint is left on maintenance, and
Thursday is the athlete-driven race-pace group ride (plus hockey at night), so the
plan does not prescribe its internals.

Usage:
    python -m src.planning.periodization            # uses config/races.json (first A-race)
    python -m src.planning.periodization --write     # also writes plans/<date>_<slug>.md
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"

DAY_IDX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


# ---- watt helper ---------------------------------------------------------
def watts(ftp: int, lo_pct: float, hi_pct: float) -> str:
    return f"{round(ftp * lo_pct)}-{round(ftp * hi_pct)} W"


# ---- data ----------------------------------------------------------------
@dataclass
class Session:
    day: str
    date: date
    name: str
    minutes: int
    intent: str
    kind: str = "other"   # threshold | vo2 | over_unders | endurance | openers | group_ride | race


@dataclass
class Week:
    label: str
    phase: str
    focus: str
    sessions: list[Session]

    @property
    def hours(self) -> float:
        return round(sum(s.minutes for s in self.sessions) / 60, 1)


# ---- per-phase session templates -----------------------------------------
def _sessions_for(phase: str, ftp: int, is_race_week: bool) -> dict[str, dict]:
    """Return {day: {name, minutes, intent}} for a phase. Thursday is the group ride."""
    thu = {
        "name": "Race-pace group ride + hockey (PM)",
        "minutes": 95,
        "kind": "group_ride",
        "intent": "Your race simulation. Cover surges and short climbs hard, ride the flats "
                  "smart in the bunch. Hockey at night, so keep Friday clear.",
    }
    if phase == "Specific prep":
        return {
            "Tue": {"name": "Threshold over-unders", "minutes": 75, "kind": "over_unders",
                    "intent": f"2 x 12 min as 2 min @ {watts(ftp,0.90,0.95)} / 1 min @ "
                              f"{watts(ftp,1.03,1.08)}. Lifts threshold and trains surge recovery."},
            "Thu": thu,
            "Sat": {"name": "Long gravel endurance", "minutes": 180, "kind": "endurance",
                    "intent": f"3 h mostly Z2 {watts(ftp,0.56,0.72)} on gravel. Practice "
                              f"fueling 60-80 g carbs/hr. Durability is the goal, not power."},
            "Sun": {"name": "Easy endurance spin", "minutes": 75, "kind": "endurance",
                    "intent": f"Z2 {watts(ftp,0.55,0.68)}, conversational. Aerobic volume, flush the legs."},
        }
    if phase == "Peak load":
        return {
            "Tue": {"name": "VO2 + threshold", "minutes": 80, "kind": "vo2",
                    "intent": f"5 x 3 min @ {watts(ftp,1.08,1.15)} (3 min easy between), then "
                              f"10 min @ {watts(ftp,0.92,0.98)}. Top-end for surges over a threshold base."},
            "Thu": {**thu, "minutes": 100},
            "Sat": {"name": "Long gravel - peak (race rehearsal)", "minutes": 225, "kind": "endurance",
                    "intent": f"3.75 h, longest ride of the block. Mostly Z2 with 3-4 climbs "
                              f"at race effort {watts(ftp,0.88,0.98)}. Full fueling rehearsal: "
                              f"food, bottles, what you'll wear and carry."},
            "Sun": {"name": "Easy endurance spin", "minutes": 75, "kind": "endurance",
                    "intent": f"Z2 {watts(ftp,0.55,0.68)} recovery-paced. Keep it gentle after the big Saturday."},
        }
    if phase == "Sharpen":
        return {
            "Tue": {"name": "Threshold / sweet spot", "minutes": 70, "kind": "threshold",
                    "intent": f"2 x 12 min @ {watts(ftp,0.92,1.00)}. Hold steady, smooth power. "
                              f"Building usable race-pace strength."},
            "Thu": {**thu, "minutes": 90},
            "Sat": {"name": "Race-effort gravel", "minutes": 150, "kind": "threshold",
                    "intent": f"2.5 h with 4 x 6 min at race intensity {watts(ftp,0.90,1.00)} "
                              f"on rolling/gravel terrain. Dial in pacing and gearing, not duration."},
            "Sun": {"name": "Easy endurance spin", "minutes": 60, "kind": "endurance",
                    "intent": f"Z2 {watts(ftp,0.55,0.68)} short and easy. Start shedding fatigue."},
        }
    # Taper & Race
    return {
        "Tue": {"name": "Openers", "minutes": 50, "kind": "openers",
                "intent": f"3 x 3 min @ {watts(ftp,0.92,0.98)} + 3 x 30 s fast, light spin "
                          f"between. Stay sharp, accumulate no fatigue."},
        "Thu": {"name": "Easy group ride or spin + hockey (PM)", "minutes": 60, "kind": "endurance",
                "intent": "Keep it social and easy this week, do NOT bury yourself on the group "
                          "ride. Hockey optional / light if you can. Freshness is the priority."},
        "Sat": {"name": "Pre-race openers", "minutes": 40, "kind": "openers",
                "intent": f"Easy Z1 with 3 x 1 min building to race pace {watts(ftp,0.90,1.00)} "
                          f"and 3 x 10 s sprints. Primes the legs for tomorrow. Check the bike, pack."},
        "Sun": {"name": "RACE: Truckee Gravel Medium (106 km)", "minutes": 270, "kind": "race",
                "intent": "Pace the first hour conservatively (altitude + long day). Fuel from the "
                          "gun, 60-90 g carbs/hr. Use your strength: stay efficient on flats, cover "
                          "moves on the climbs, save matches for the back third."},
    }


# ---- builder -------------------------------------------------------------
def phase_sequence(n_weeks: int) -> list[str]:
    """Last week tapers; the week before sharpens; earlier weeks build."""
    if n_weeks <= 1:
        return ["Taper & Race"]
    if n_weeks == 2:
        return ["Sharpen", "Taper & Race"]
    if n_weeks == 3:
        return ["Peak load", "Sharpen", "Taper & Race"]
    seq = ["Specific prep"] * (n_weeks - 3) + ["Peak load", "Sharpen", "Taper & Race"]
    return seq


PHASE_FOCUS = {
    "Specific prep": "Introduce race-specific load; build gravel durability.",
    "Peak load": "Biggest week. Longest gravel ride + top-end. Then we only subtract.",
    "Sharpen": "Race-pace work, easing volume. Convert fitness to race readiness.",
    "Taper & Race": "Shed fatigue, stay sharp, arrive fresh. Race day.",
}


def build_plan(profile: dict, race: dict, today: date,
               include_past: bool = False) -> list[Week]:
    ftp = int(profile["ftp"])
    ride_days = profile["ride_days"]
    race_date = date.fromisoformat(race["date"])

    # Monday of this week through the race week.
    monday0 = today - timedelta(days=today.weekday())
    race_monday = race_date - timedelta(days=race_date.weekday())
    n_weeks = (race_monday - monday0).days // 7 + 1
    phases = phase_sequence(n_weeks)

    weeks: list[Week] = []
    for w in range(n_weeks):
        wk_monday = monday0 + timedelta(weeks=w)
        phase = phases[w]
        is_race_week = w == n_weeks - 1
        templ = _sessions_for(phase, ftp, is_race_week)
        sessions: list[Session] = []
        for day in ride_days:
            d = wk_monday + timedelta(days=DAY_IDX[day])
            if (not include_past and d < today) or d > race_date:
                continue
            t = templ.get(day)
            if not t:
                continue
            sessions.append(
                Session(day, d, t["name"], t["minutes"], t["intent"], t.get("kind", "other"))
            )
        label = f"Week {w + 1} ({wk_monday:%b %d} - {wk_monday + timedelta(days=6):%b %d})"
        weeks.append(Week(label, phase, PHASE_FOCUS[phase], sessions))
    return weeks


def prescribed_for(target: date, profile: dict | None = None,
                   race: dict | None = None) -> Session | None:
    """Return the prescribed Session for a given date, or None.

    Note: reflects the A-race template; B/C-race overrides made directly in a plan
    doc are not yet modeled here.
    """
    profile = profile or _load("athlete_profile.json")
    if race is None:
        a = sorted([r for r in _load("races.json") if r.get("priority") == "A"],
                   key=lambda r: r["date"])
        if not a:
            return None
        race = a[0]
    for wk in build_plan(profile, race, date.today(), include_past=True):
        for s in wk.sessions:
            if s.date == target:
                return s
    return None


# ---- render --------------------------------------------------------------
def render_markdown(weeks: list[Week], profile: dict, race: dict) -> str:
    race_date = date.fromisoformat(race["date"])
    days_out = (race_date - date.today()).days
    out: list[str] = []
    out.append(f"# Training Plan: {race['name']}")
    out.append(f"\n_Race: {race_date:%A, %B %d, %Y} ({race['discipline']}, "
               f"{race.get('distance_km','?')} km, {race.get('ascent_m','?')} m climbing). "
               f"{days_out} days out as of {date.today():%b %d}._\n")
    out.append(f"**Athlete:** {profile['name']} - FTP {profile['ftp']} W, "
               f"{profile['rider_type']}.")
    out.append(f"**Block type:** {len(weeks)}-week specific-prep + taper. "
               f"Priority: aerobic durability and threshold (your limiters); sprint on maintenance.\n")
    out.append("**Race-specific notes**")
    out.append(f"- Course: {race.get('notes','')}")
    out.append(f"- Location: {race.get('location','')}. Altitude bites in long aerobic efforts; "
               f"arrive late or get there early, not the day-before-evening.")
    out.append("- Fueling is a trainable skill. Rehearse 60-90 g carbs/hr on the long Saturdays.\n")

    for wk in weeks:
        out.append(f"## {wk.label} - {wk.phase}  ·  ~{wk.hours} h")
        out.append(f"_{wk.focus}_\n")
        out.append("| Day | Date | Session | Time | Intent |")
        out.append("|-----|------|---------|------|--------|")
        for s in wk.sessions:
            out.append(f"| {s.day} | {s.date:%b %d} | {s.name} | {s.minutes} min | {s.intent} |")
        out.append("")
    out.append("---")
    out.append("_Rest days: Mon, Wed, Fri (Fri protects recovery after Thursday hockey). "
               "Readiness is advisory: if HRV/sleep tank, swap a quality day for easy Z2 or rest. "
               "Tell the coach about travel or missed days and the week re-flows._")
    return "\n".join(out)


def _load(name: str):
    return json.loads((CONFIG / name).read_text())


def main() -> None:
    profile = _load("athlete_profile.json")
    races = _load("races.json")
    a_races = [r for r in races if r.get("priority") == "A"]
    race = sorted(a_races, key=lambda r: r["date"])[0]
    weeks = build_plan(profile, race, date.today())
    md = render_markdown(weeks, profile, race)
    print(md)
    if "--write" in sys.argv:
        plans = ROOT / "plans"
        plans.mkdir(exist_ok=True)
        slug = race["name"].lower().replace(" ", "_").replace("-", "").replace("__", "_")
        path = plans / f"{race['date']}_{slug}.md"
        path.write_text(md)
        print(f"\n[written: {path.relative_to(ROOT)}]", file=sys.stderr)


if __name__ == "__main__":
    main()
