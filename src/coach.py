"""Coach orchestration entry point - STUB.

For v1 the conversational coach runs in chat. This module assembles the analyzed
context (power diagnosis, fitness, readiness, current plan) so the coach can reason
over it, and exposes the actions the coach can take: re-flow a week, push workouts,
record RPE (R10, R11, R13, R14). The same assembly becomes the web-app backend in v2.
"""
from __future__ import annotations

from .config import Config
from .intervals_client import IntervalsClient
from .analysis.power_profile import diagnose


def build_context() -> dict:
    """Assemble the snapshot the coach reasons over. Expands through Phases 1-4."""
    cfg = Config.load()
    c = IntervalsClient(cfg)
    weight = cfg.athlete_weight_kg or 74.0
    diag = diagnose(c.power_curve("all"), c.ftp(), float(weight))
    return {
        "ftp": c.ftp(),
        "rider_type": diag.rider_type,
        "weaknesses": diag.weaknesses,
        "summary": diag.summary,
        # TODO Phase 1+: readiness, fitness/TSB, current plan, RPE history
    }


if __name__ == "__main__":
    from pprint import pprint

    pprint(build_context())
