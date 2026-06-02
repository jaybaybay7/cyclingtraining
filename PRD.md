# PRD — Virtual Cycling Coach & Training-Plan Builder

_Owner: Jay (jaymag) · Status: Draft v0.1 · Last updated: 2026-06-02_

## 1. Problem statement

A time-constrained road and gravel racer wants to get faster but can't afford a full-time
coach or wasted training hours. He already generates rich data (power on Intervals.icu,
HRV/sleep/Body Battery on Garmin) but it sits in separate silos and nothing turns it into a
specific, adaptive plan. The cost of not solving it: training is unfocused, weaknesses go
unaddressed, and fatigue or travel quietly derails consistency. Evidence from his own data:
a near-elite sprint sitting on a comparatively weak threshold (FTP 3.68 W/kg), with sustained
power slipping over the last 90 days. The engine that wins road and gravel races is exactly
the part being under-trained.

## 2. Goals

1. **Diagnose accurately**: classify rider type and rank weaknesses from the power curve and
   training history, refreshed as new data lands. _Success: diagnosis matches athlete's felt
   experience and updates automatically._
2. **Produce a race-targeted plan**: generate a periodized plan that peaks for A-races and
   prioritizes the diagnosed limiters. _Success: a plan exists for every week from today to
   each A-race, with clear phase logic._
3. **Make health data actionable**: surface a daily readiness signal (HRV baseline, sleep,
   Body Battery) with a plain-English recommendation. _Success: every planned day shows a
   readiness read and a recommended adjustment._
4. **Stay adaptive**: absorb travel, missed sessions, RPE, and completed-workout feedback
   without manual replanning. _Success: a schedule change re-flows the week while protecting
   key sessions and weekly load targets._
5. **Close the loop**: deliver workouts where the athlete trains. _Success: structured
   workouts appear on the Garmin head unit via Intervals.icu, and a review doc is produced
   weekly._
6. **Coach interactively**: let the athlete talk through "what if" scenarios (missed session,
   travel) and apply the result. _Success: the athlete can describe a disruption in plain
   language and get concrete re-flow options with tradeoffs, then apply one on confirmation._

## 3. Non-goals (v1)

- **No automatic workout rewriting.** Readiness is advisory only; the athlete decides. (His
  explicit preference; also lower risk while the model is young.)
- **No nutrition or strength programming.** Adjacent and valuable, but a separate initiative.
- **No multi-athlete / coaching-for-others support.** Single athlete keeps scope tight.
- **No native mobile app or custom UI.** Outputs live in a doc plus Intervals.icu/Garmin,
  which the athlete already uses. The conversational coach runs in the existing chat, not a
  bespoke interface. A custom UI is premature before the engine is proven.
- **No real-time / in-ride guidance.** Planning and post-activity analysis only for v1.

## 4. User stories (priority order)

1. As the athlete, I want my power curve analyzed so that I know which durations are holding
   me back, without guessing.
2. As the athlete, I want to enter my A-races so that the plan peaks me for the events I
   actually care about.
3. As the athlete, I want a weekly plan that fits my real available hours and days so that I
   can actually complete it.
4. As the athlete, I want a daily readiness read from my HRV, sleep, and Body Battery so that
   I can decide when to push and when to back off.
5. As the athlete, I want to tell the coach I'm traveling so that the week re-flows around it
   instead of leaving dead sessions.
6. As the athlete, I want completed workouts compared to what was prescribed so that next
   week adapts to what I actually did.
7. As the athlete, I want structured workouts pushed to my Garmin so that I'm not manually
   recreating intervals on the head unit.
8. As the athlete, I want B/C races flagged as "train through" so that I don't taper for
   events that don't matter.
9. (Edge) As the athlete, when wellness data is missing for a day, I want the coach to say so
   and fall back gracefully rather than invent a readiness score.

## 5. Requirements

### Must-have (P0)
- **R1 Intervals.icu ingest**: pull power curve, PRs, FTP/zones, eFTP/w'/pMax, activities,
  CTL/ATL/TSB.
  - Given valid credentials, when ingest runs, then current FTP, the mean-max curve, and
    fitness values are stored and queryable.
- **R2 GarminDB ingest**: pull HRV, sleep, resting HR, Body Battery into the local store.
  - Given a Garmin login, when ingest runs, then daily wellness rows exist for available dates;
    missing days are recorded as null, not fabricated.
- **R3 Weakness diagnosis**: classify rider type and rank limiters vs road/gravel demands.
  - Given a power curve, when diagnosis runs, then it outputs ranked weaknesses with W/kg and
    a current-vs-all-time trend.
- **R4 HRV baseline + readiness**: rolling 7-day vs 60-day baseline; daily green/amber/red.
  - Given >= 14 days of HRV history, when a day is scored, then a readiness value and a
    one-line rationale are produced; with insufficient history, it states "baseline building."
- **R5 Race calendar + periodization**: accept A-races (date, discipline, priority) and build
  base/build/peak/taper backward from each.
  - Given >= 1 A-race, when the plan generates, then every week to the race has a named phase
    and a weekly load target.
- **R6 Weekly plan within constraints**: respect total hours, available days, cross-training.
  - Given hours and available days, when a week generates, then prescribed load fits the
    budget and no session lands on a blocked day.
- **R7 Review doc output**: weekly plan as a readable doc with session detail and the readiness
  overlay.
- **R8 Advisory readiness overlay**: each planned day shows readiness + recommended action,
  without auto-changing the workout.

### Promoted into v1 (now P0, per athlete request)
- **R9 Push structured workouts to Intervals.icu calendar** (syncs to Garmin device).
  - Given an approved week, when the athlete confirms, then structured workouts are written to
    the Intervals.icu calendar and appear on the Garmin head unit.
- **R10 Interactive disruption handling**: enter travel/missed days; the week re-flows while
  protecting key sessions and weekly load targets.
- **R11 Completed-vs-prescribed feedback**: compliance and actual TSS feed the next week.
- **R12 Ramp-rate / overtraining guardrails**: monotony, strain, illness flag.
- **R13 Per-ride RPE + subjective feedback**: after each ride the athlete logs RPE and notes
  (legs, motivation, illness); these feed readiness and the next prescription.
  - Given a completed ride, when the athlete submits RPE 1-10 and optional notes, then the
    value is stored against the activity and factored into following sessions.
  - Edge: when actual load and RPE disagree (an easy ride that felt brutal), the coach flags
    possible fatigue instead of ignoring the mismatch.
- **R14 Conversational coach (scenario planning)**: the athlete chats with the coach to run
  "what if" scenarios and apply the outcome.
  - Given the current plan, when the athlete says e.g. "I'm traveling Thu-Sun" or "I skipped
    today's intervals," then the coach proposes one or two concrete re-flow options with the
    tradeoffs (load kept vs lost, key sessions protected) and applies the chosen one on
    confirmation.
  - The coach explains its reasoning and never silently changes the plan.

### Nice-to-have (P1)
- Multi-sport load accounting that models hockey/climbing fatigue more precisely.
- Richer workout-library variants and smarter session naming.

### Future considerations (P2)
- Strength and nutrition modules.
- A lightweight dashboard/artifact for at-a-glance status.
- Auto-regulation mode (opt-in) that applies readiness adjustments automatically.

## 6. Success metrics

Leading (days–weeks):
- Plan coverage: 100% of weeks from today to each A-race have a generated plan.
- Readiness coverage: >= 90% of planned days show a readiness read (given wellness data).
- Compliance: prescribed vs completed sessions; target >= 80% key-session completion.
- Replan latency: a travel/disruption entry re-flows the week in a single pass.

Lagging (weeks–months):
- FTP / threshold W/kg trend up over a training block (primary fitness outcome).
- 5-min and 20-min power trend up; sprint maintained (no meaningful loss).
- A-race outcome / form (TSB in target range on race day).
- Athlete-reported usefulness of the daily readiness call.

Measurement: pulled from Intervals.icu (power, fitness) and the local store (readiness,
compliance); evaluated at the end of each training block.

## 7. Open questions

Blocking (needed before Phase 2 plan generation):
- A-race dates, disciplines, distances, priorities. _(athlete)_
- Weekly hours and reliably available days. _(athlete)_
- Smart trainer with ERG? Indoor vs outdoor split. _(athlete)_
- Garmin Connect login to stand up GarminDB. _(athlete)_

Non-blocking (resolve during build):
- Exact readiness scoring weights and thresholds (tune against his real baseline). _(coach/data)_
- How precisely to model hockey/climbing load. _(coach)_
- Local store format (SQLite vs parquet). _(eng)_
- Workout-library breadth for v1 (how many session types). _(coach)_

## 8. Timeline and phasing

v1 now includes the full loop, RPE feedback, and the conversational coach (R9-R14 promoted to
P0). That widens v1, so the phases below are a build sequence within a single release rather
than separate releases. The honest tradeoff: more to build before "done," but the result is a
coach you interact with, not a static planner.

- **Phase 0 — Connect & diagnose**: done (Intervals.icu live, profile diagnosed).
- **Phase 1 — Data foundation**: GarminDB ingest, normalized store, HRV baseline + readiness.
- **Phase 2 — Plan generation**: periodization, weekly builder, workout library, review doc.
  _Blocked on the four blocking open questions above._
- **Phase 3 — Loop + feedback**: push to Intervals.icu, per-ride RPE capture, completed-vs-
  prescribed feedback into the next week.
- **Phase 4 — Conversational coach + adaptivity**: chat-driven scenario planning, disruption
  handling, guardrails, trend reporting.

No hard external deadline yet; the binding constraint is the first A-race date, which sets the
runway for periodization.
