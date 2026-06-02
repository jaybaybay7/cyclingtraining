"""Smoke test for the course analyzer (R15).

Builds a synthetic GPX with a 5 km / ~6% climb and checks the analyzer detects it
and classifies the terrain as a climber's course. Run: python -m tests.test_course
"""
from __future__ import annotations

import os
import tempfile

from src.analysis.course import analyze, parse_gpx


def _write_gpx(path: str) -> None:
    pts = []
    lat, lon, ele = 37.80, -122.40, 20.0
    dlat = 50 / 111000.0

    def add(n: int, dele: float):
        nonlocal lat, ele
        for _ in range(n):
            lat += dlat
            ele = max(0.0, ele + dele)
            pts.append((lat, lon, ele))

    add(60, 0.0)     # 3 km flat
    add(100, 3.0)    # 5 km at 6%
    add(40, -2.0)    # 2 km descent
    add(80, 0.6)     # 4 km rolling
    with open(path, "w") as f:
        f.write('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1">'
                '<trk><trkseg>')
        for la, lo, el in pts:
            f.write(f'<trkpt lat="{la:.6f}" lon="{lo:.6f}"><ele>{el:.1f}</ele></trkpt>')
        f.write('</trkseg></trk></gpx>')


def test_climb_detection() -> None:
    with tempfile.TemporaryDirectory() as d:
        gpx = os.path.join(d, "c.gpx")
        _write_gpx(gpx)
        pts = parse_gpx(gpx)
        assert len(pts) > 250, f"expected parsed points, got {len(pts)}"
        demand = analyze(pts)
        assert demand.distance_km > 13
        assert demand.ascent_m > 250
        assert demand.climbs, "should detect at least one sustained climb"
        assert demand.climbs[0].length_km >= 4
        assert "Climber" in demand.terrain
    print("test_climb_detection: OK")


if __name__ == "__main__":
    test_climb_detection()
    print("All course tests passed.")
