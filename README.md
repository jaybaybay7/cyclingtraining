# cyclingtraining

A virtual cycling coach and training-plan builder for a time-constrained road and gravel racer.
It reads power data (Intervals.icu) and health metrics (Garmin via GarminDB), diagnoses
weaknesses, builds a periodized plan toward target races, and adapts from readiness and
per-ride feedback. The coach recommends; the athlete decides.

See `PLAN.md` for the architecture and `PRD.md` for requirements.

## Status

- Phase 0 (connect & diagnose): Intervals.icu client and power-profile diagnostic working.
- Phases 1-4: in progress. See `PLAN.md`.

## Layout

```
config/
  athlete_profile.json # constraints, schedule, FTP, diagnosis
src/
  config.py            # loads credentials from .env
  intervals_client.py  # Intervals.icu REST client (power, fitness, wellness, workout push)
  garmin_source.py     # GarminDB ingest for HRV, sleep, Body Battery (stub)
  analysis/
    power_profile.py   # rider-type diagnosis and weakness ranking (R3)
    course.py          # FIT/GPX route ingest + course-demand analysis (R15)
    readiness.py       # HRV baseline + readiness score (R4) (stub)
  planning/
    periodization.py   # base/build/peak/taper from A-races (R5) (stub)
  coach.py             # orchestration entry point (stub)
tests/
  test_course.py       # smoke test for the course analyzer
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

Never commit `.env`. The repo ignores it.

## Quick start

```bash
python -m src.intervals_client       # prints your current profile + power curve
python -m src.analysis.power_profile # prints the weakness diagnosis
python -m src.analysis.course route.gpx  # analyzes a race route (FIT or GPX)
python -m tests.test_course          # runs the course-analyzer smoke test
```

## The conversational coach

For v1 the coach runs in chat: you talk to it, the modules above do the work, outputs are a
review doc plus structured workouts pushed to Intervals.icu. A standalone web app is v2 and
reuses these exact modules as its backend.
