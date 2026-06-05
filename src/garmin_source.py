"""Garmin wellness ingest (R2).

Intervals.icu does NOT carry this athlete's HRV, sleep, resting HR, or Body Battery,
so Garmin is the source of truth for readiness. Uses the `garminconnect` library
(garth auth). Tokens are cached so MFA is only needed on the first login.

Pulls HRV, sleep score, resting HR, and Body Battery into data/wellness.json (git-ignored),
which feeds src/analysis/readiness.py.

Setup:
    pip install garminconnect garth
    # in .env:  GARMIN_EMAIL=...  GARMIN_PASSWORD=...
First login may need an MFA code (set GARMIN_MFA or you'll be prompted).

Usage:
    python -m src.garmin_source --days 90
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from .config import Config
from .analysis.readiness import Wellness

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "wellness.json"
TOKENSTORE = os.path.expanduser("~/.garminconnect")


def _mfa_prompt() -> str:
    code = os.environ.get("GARMIN_MFA")
    if code:
        return code
    return input("Garmin MFA code: ").strip()


class GarminSource:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config.load()
        self.api = None

    def login(self):
        from garminconnect import Garmin
        os.makedirs(TOKENSTORE, exist_ok=True)
        try:                                   # resume cached session (no creds/MFA)
            self.api = Garmin()
            self.api.login(TOKENSTORE)
            if getattr(self.api, "display_name", None):
                return self
        except Exception:
            pass
        # Fresh login. prompt_mfa handles the code interactively; passing TOKENSTORE
        # to login() makes garminconnect persist the tokens so future runs skip MFA.
        if not self.cfg.garmin_email or not self.cfg.garmin_password:
            raise RuntimeError("Set GARMIN_EMAIL and GARMIN_PASSWORD in .env")
        self.api = Garmin(email=self.cfg.garmin_email,
                          password=self.cfg.garmin_password,
                          prompt_mfa=_mfa_prompt)
        self.api.login(TOKENSTORE)
        return self

    # --- defensive extractors (Garmin JSON shapes vary by account/firmware) ---
    @staticmethod
    def _hrv(api, cd):
        try:
            d = api.get_hrv_data(cd) or {}
            return (d.get("hrvSummary") or {}).get("lastNightAvg")
        except Exception:
            return None

    @staticmethod
    def _sleep(api, cd):
        try:
            dto = (api.get_sleep_data(cd) or {}).get("dailySleepDTO") or {}
            sc = (dto.get("sleepScores") or {}).get("overall") or {}
            return sc.get("value")
        except Exception:
            return None

    @staticmethod
    def _rhr(api, cd):
        try:
            d = api.get_rhr_day(cd) or {}
            m = (d.get("allMetrics") or {}).get("metricsMap") or {}
            vals = m.get("WELLNESS_RESTING_HEART_RATE") or []
            return vals[0].get("value") if vals else d.get("restingHeartRate")
        except Exception:
            return None

    @staticmethod
    def _body_battery(api, cd):
        try:
            data = api.get_body_battery(cd, cd) or []
            vals = []
            for day in data:
                for _ts, _status, lvl in (day.get("bodyBatteryValuesArray") or []):
                    if lvl is not None:
                        vals.append(lvl)
            return max(vals) if vals else None
        except Exception:
            return None

    def wellness_for(self, d: date) -> Wellness:
        cd = d.isoformat()
        a = self.api
        return Wellness(d, self._hrv(a, cd), self._sleep(a, cd),
                        self._body_battery(a, cd), self._rhr(a, cd))

    def pull(self, days: int = 90) -> list[Wellness]:
        today = date.today()
        out = [self.wellness_for(today - timedelta(days=i)) for i in range(days)]
        out.sort(key=lambda w: w.date)
        return out

    @staticmethod
    def save(records: list[Wellness]) -> Path:
        STORE.parent.mkdir(exist_ok=True)
        rows = [{**asdict(w), "date": w.date.isoformat()} for w in records]
        STORE.write_text(json.dumps(rows, indent=1))
        return STORE


def main() -> None:
    days = 90
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    src = GarminSource().login()
    recs = src.pull(days)
    GarminSource.save(recs)
    have = sum(1 for w in recs if w.hrv is not None)
    print(f"Pulled {len(recs)} days ({have} with HRV) -> {STORE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
