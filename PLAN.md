# Virtual Cycling Coach — System Plan

_Last updated: 2026-06-02_

## What we're building

A training-plan builder that acts as a virtual cycling coach. It reads the athlete's
power data and health metrics, diagnoses weaknesses, and produces a periodized,
auto-adjusting training plan aimed at a set of target ("A") races. The coach reasons
over the data; it does not silently overwrite the athlete's decisions. Readiness signals
are surfaced as recommendations, and the athlete makes the final call.

This document sketches the architecture, the data flow, and (importantly) exactly which
inputs are taken in at setup versus as we go. The companion `PRD.md` defines requirements,
user stories, and success metrics.

## Athlete snapshot (pulled live from Intervals.icu, 2026-06-02)

- FTP 272 W (~3.68 W/kg at ~74 kg), LTHR 180, max HR 200, eFTP ~277, w' ~23.7 kJ, pMax ~1036 W
- CTL ~64 / ATL ~55, ramp rate slightly negative (freshening)
- Power profile: near-elite sprint (5s 13.4 W/kg), strong anaerobic (1min 6.0 W/kg),
  modest threshold and VO2max (5min 4.5, FTP 3.68 W/kg)
- Diagnosis: explosive sprinter on an under-developed aerobic engine; threshold and VO2max
  are the limiters, and sustained power has slipped over the last 90 days
- Note: Garmin wellness (HRV, sleep, resting HR, Body Battery) is NOT syncing into
  Intervals.icu, so GarminDB is required for readiness data

## Architecture

Five layers, orchestrated by the coach (Claude reasoning over the assembled context).

### 1. Data layer
- **Intervals.icu client** — REST API (API key auth). Pulls power curve, power PRs, FTP and
  zones, eFTP/w'/pMax, activities, and fitness (CTL/ATL/TSB). Also used to push structured
  workouts back to the calendar.
- **GarminDB client** — local SQLite populated by GarminDB. Supplies the metrics Intervals.icu
  lacks: HRV, sleep score and sleep stages, resting HR, Body Battery, stress.
- Both normalize into a single local store (SQLite or parquet) so analysis reads one schema.

### 2. Analysis layer
- **Power profile diagnostics** — mean-max curve across durations, rider-type classification,
  weakness ranking relative to road/gravel demands, trend (current vs all-time).
- **Fitness model** — CTL/ATL/TSB (form), ramp rate, monotony and strain.
- **HRV baseline engine** — rolling 7-day vs 60-day baseline with deviation flags; needs a
  warm-up window of history before it is trustworthy.
- **Readiness score** — combines HRV deviation, sleep, Body Battery, and recent load into a
  green/amber/red signal with a short explanation.

### 3. Planning layer
- **Periodization engine** — works backward from A-race dates: base, build, peak, taper.
- **Weekly builder** — lays out sessions against available days and weekly hours, respecting
  cross-training load (hockey, climbing) and recovery.
- **Workout library** — parameterized sessions targeting the diagnosed weaknesses
  (threshold, VO2max, aerobic durability) plus maintenance for the sprint.
- **Advisory adjuster** — overlays readiness on each day, recommends downgrade/swap/rest, but
  does not auto-apply (athlete decides; this is the chosen behavior).
- **Disruption handler** — travel and schedule changes; redistributes load while protecting
  key sessions and weekly targets.

### 4. Output layer
- **Review doc generator** — a weekly plan the athlete reads and sanity-checks (markdown/doc).
- **Intervals.icu pusher** — writes structured workouts to the calendar, which sync to the
  Garmin head unit.

### 5. Orchestration (the conversational coach)
- The coach assembles the analyzed context and reasons about what to prescribe, explains the
  "why," and adapts week to week from completed-workout and RPE feedback.
- **Interactive scenario planning**: the athlete chats with the coach in plain language
  ("I skipped today's intervals," "I'm traveling Thu-Sun"). The coach runs the scenario,
  returns one or two concrete re-flow options with tradeoffs, and applies the chosen one on
  confirmation. It never changes the plan silently.
- **Per-ride RPE loop**: after each ride the athlete logs RPE plus quick notes; the coach
  reconciles felt effort against actual load and adjusts the next sessions.

## Data flow

```
Garmin Connect ──(GarminDB)──> local SQLite ─┐
                                             ├─> normalize ─> analysis ─> coach ─> plan ─┬─> review doc
Intervals.icu API ───────────────────────────┘   (power,      (readiness,  (reasoning)   └─> push to Intervals.icu ─> Garmin device
                                                  fitness,      diagnosis,
                                                  wellness)     periodization)
                                                                     ^
completed workouts + subjective feedback + travel changes ──────────┘  (weekly feedback loop)
```

## Inputs — the part you asked about

### A. Setup inputs (collected once, editable later)
Athlete profile and credentials:
- Intervals.icu API key + athlete ID  ✅ provided
- Garmin Connect login (for GarminDB; MFA handled live)  ⏳ pending
- GitHub token for the repo  ✅ provided (rotate after setup)
- FTP, LTHR, max HR, weight, zones  ✅ pulled from Intervals.icu

Goals and constraints:
- A-race calendar: dates, discipline (road/gravel), distance/duration, priority  ⏳ pending
- Secondary races (B/C) to "train through," not taper for
- Weekly time budget: total hours, which days are reliably available  ⏳ pending
- Equipment: smart trainer + ERG? outdoor options?  ⏳ pending
- Cross-training to keep on the calendar (hockey, climbing) and rough load
- Stated weak areas / goals, and any injury history or hard constraints
- Auto-regulation preference  ✅ chosen: informational only (advisory)

### B. Ongoing inputs (pulled or entered as we go)
- Daily Garmin wellness: HRV, sleep score/stages, resting HR, Body Battery, stress
- Completed activities + actual vs prescribed (compliance, actual TSS, power achieved)
- Updated power curve and PRs as new data lands
- Subjective feedback: RPE, legs/soreness, motivation, illness flag
- Schedule disruptions: travel, missed days, life events
- Race results as they happen

### C. Derived inputs (computed, not entered)
- HRV rolling baseline and daily deviation
- CTL / ATL / TSB, ramp rate, monotony, strain
- Readiness score (green/amber/red) + rationale
- Rider-type classification and ranked weaknesses
- Weekly load targets per training phase

## Tech and repo

- Python (data clients, analysis), SQLite for the local store, Intervals.icu REST, GarminDB.
- Secrets in `.env` (git-ignored). Never committed. PAT to be rotated after setup.
- Repo: `github.com/jaybaybay7/cyclingtraining`. First commit: this plan + the PRD.

## Conversational surface (decision)

Decided: build the coaching engine as plain Python modules in the repo, and use the existing
chat as the coach for v1. The athlete talks to the coach here; the modules do diagnosis,
periodization, readiness, and re-flow; outputs are the review doc plus pushed Intervals.icu
workouts. A standalone web app is **v2**, not v1: a FastAPI/Flask backend that imports the
exact same modules and calls the Claude API, with a frontend for phone access. Building the
engine first means the web app is later a thin wrapper, not a rewrite. Rationale: the hard part
is the coaching logic, not the UI, and proving the logic before building an interface avoids
wasted work.

## Phased delivery

All of the below is v1 scope (the loop, RPE, and conversational coach are now core, not later
add-ons). Phases are a build sequence within one release.

- **Phase 0 — Connect & diagnose** (largely done): Intervals.icu live, power profile diagnosed.
- **Phase 1 — Data foundation**: GarminDB pull, normalized store, HRV baseline + readiness.
- **Phase 2 — Plan generation**: periodization from A-races, weekly builder, workout library,
  review doc output.
- **Phase 3 — Loop + feedback**: push structured workouts to Intervals.icu; per-ride RPE
  capture; completed-vs-prescribed feedback into the next week.
- **Phase 4 — Conversational coach + adaptivity**: chat-driven scenario planning, travel/missed
  -session re-flow, guardrails, refined readiness advisories, trend reporting.

## Open items before Phase 2

1. A-race dates, disciplines, priorities.
2. Weekly hours, reliably free days, equipment (ERG?).
3. Which cross-training stays and its rough weekly load.
4. Garmin login to stand up GarminDB.
