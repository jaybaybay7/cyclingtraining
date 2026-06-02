"""Course / route ingest and demand analysis (R15).

Reads a GPX (XML, no deps) or FIT (needs `fitdecode`) route file, then computes the
demands that should shape race-specific training: total distance, climbing, gradient
distribution, and sustained climbs. From that it recommends a training emphasis.

Usage:
    python -m src.analysis.course path/to/route.gpx
"""
from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


# ---- geometry ------------------------------------------------------------
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---- parsing -------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # strip namespace


def parse_gpx(path: str) -> list[tuple[float, float, float]]:
    """Return [(lat, lon, ele_m)] from a GPX track. Namespace-agnostic.

    ElementTree's `{*}` wildcard only works in find/findall paths, not in iter(),
    so we walk every element and match on the local tag name.
    """
    root = ET.parse(path).getroot()
    pts: list[tuple[float, float, float]] = []
    for tp in root.iter():
        if _local(tp.tag) != "trkpt":
            continue
        ele = None
        for child in tp:
            if _local(child.tag) == "ele" and child.text:
                ele = float(child.text)
                break
        if ele is None:
            continue
        pts.append((float(tp.get("lat")), float(tp.get("lon")), ele))
    return pts


def parse_fit(path: str) -> list[tuple[float, float, float]]:
    """Return [(lat, lon, ele_m)] from a FIT route/activity. Requires fitdecode."""
    try:
        import fitdecode
    except ImportError as e:
        raise RuntimeError("FIT support needs fitdecode: pip install fitdecode") from e

    SC = 180.0 / (2 ** 31)  # semicircles -> degrees
    pts: list[tuple[float, float, float]] = []
    with fitdecode.FitReader(path) as fr:
        for frame in fr:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
            if frame.name not in ("record", "course_point"):
                continue
            try:
                lat = frame.get_value("position_lat") * SC
                lon = frame.get_value("position_long") * SC
            except (KeyError, TypeError):
                continue
            ele = None
            for f in ("enhanced_altitude", "altitude"):
                try:
                    ele = frame.get_value(f)
                    break
                except KeyError:
                    continue
            if ele is not None:
                pts.append((lat, lon, float(ele)))
    return pts


def load_route(path: str) -> list[tuple[float, float, float]]:
    p = path.lower()
    if p.endswith(".gpx"):
        return parse_gpx(path)
    if p.endswith(".fit"):
        return parse_fit(path)
    raise ValueError("Unsupported file: use .gpx or .fit")


# ---- analysis ------------------------------------------------------------
@dataclass
class Climb:
    start_km: float
    length_km: float
    avg_grade: float
    vertical_m: float


@dataclass
class CourseDemand:
    distance_km: float
    ascent_m: float
    ascent_per_km: float
    max_grade: float
    grade_buckets: dict[str, float]      # label -> km in that bucket
    climbs: list[Climb] = field(default_factory=list)
    terrain: str = ""
    emphasis: str = ""


def _smooth(vals: list[float], k: int = 5) -> list[float]:
    if len(vals) < k:
        return vals
    out = []
    for i in range(len(vals)):
        lo, hi = max(0, i - k // 2), min(len(vals), i + k // 2 + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def analyze(points: list[tuple[float, float, float]]) -> CourseDemand:
    if len(points) < 2:
        raise ValueError("Route has too few points with elevation.")

    eles = _smooth([p[2] for p in points], k=7)
    dist_cum = [0.0]
    for i in range(1, len(points)):
        d = haversine_m(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
        dist_cum.append(dist_cum[-1] + d)

    total_m = dist_cum[-1]
    ascent = 0.0
    buckets = {"flat <2%": 0.0, "rolling 2-5%": 0.0, "moderate 5-8%": 0.0, "steep >8%": 0.0}
    grades: list[float] = []
    max_grade = 0.0

    for i in range(1, len(points)):
        seg = dist_cum[i] - dist_cum[i - 1]
        if seg < 1e-6:
            grades.append(0.0)
            continue
        dele = eles[i] - eles[i - 1]
        if dele > 0:
            ascent += dele
        g = (dele / seg) * 100
        grades.append(g)
        max_grade = max(max_grade, g)
        ag = abs(g)
        km = seg / 1000
        if ag < 2:
            buckets["flat <2%"] += km
        elif ag < 5:
            buckets["rolling 2-5%"] += km
        elif ag < 8:
            buckets["moderate 5-8%"] += km
        else:
            buckets["steep >8%"] += km

    # sustained climbs: contiguous stretches averaging >=3% for >=0.4 km
    climbs: list[Climb] = []
    i = 1
    while i < len(points):
        if grades[i - 1] >= 3:
            start = i - 1
            while i < len(points) and grades[i - 1] >= 1.5:
                i += 1
            seg_len = dist_cum[i - 1] - dist_cum[start]
            vert = eles[i - 1] - eles[start]
            if seg_len >= 400 and vert > 0:
                climbs.append(
                    Climb(
                        round(dist_cum[start] / 1000, 1),
                        round(seg_len / 1000, 2),
                        round(vert / seg_len * 100, 1),
                        round(vert),
                    )
                )
        else:
            i += 1

    dist_km = total_m / 1000
    apk = ascent / dist_km if dist_km else 0
    longest = max((c.length_km for c in climbs), default=0)

    if apk >= 15 or longest >= 3:
        terrain = "Climber's course: significant sustained climbing"
        emphasis = (
            "Threshold and sustained tempo, plus long aerobic durability. Prioritize "
            "20-40 min efforts at/just below FTP and long climbs. This is exactly your "
            "weak zone, so it doubles as both race-prep and limiter work."
        )
    elif buckets["steep >8%"] >= 1.0 or (longest and longest < 1.5 and len(climbs) >= 4):
        terrain = "Punchy / rolling: many short sharp climbs"
        emphasis = (
            "Repeated VO2max and over-unders, plus 30/30s and short anaerobic repeats to "
            "survive repeated surges. Keep threshold work as the base under it."
        )
    else:
        terrain = "Flat to rolling: sustained-power and pacing course"
        emphasis = (
            "Sustained threshold / sweet-spot and fatigue resistance. Long steady efforts "
            "and pacing discipline matter more than punch. Build the aerobic engine."
        )

    return CourseDemand(
        distance_km=round(dist_km, 1),
        ascent_m=round(ascent),
        ascent_per_km=round(apk, 1),
        max_grade=round(max_grade, 1),
        grade_buckets={k: round(v, 1) for k, v in buckets.items()},
        climbs=sorted(climbs, key=lambda c: c.vertical_m, reverse=True)[:8],
        terrain=terrain,
        emphasis=emphasis,
    )


def summarize(path: str) -> CourseDemand:
    d = analyze(load_route(path))
    print(f"Course: {d.distance_km} km, {d.ascent_m} m climbing "
          f"({d.ascent_per_km} m/km), max grade {d.max_grade}%")
    print(f"Terrain: {d.terrain}")
    print("Gradient mix (km):", d.grade_buckets)
    if d.climbs:
        print("Notable climbs (km @ avg%, vertical):")
        for c in d.climbs:
            print(f"  km {c.start_km}: {c.length_km} km @ {c.avg_grade}% ({c.vertical_m} m)")
    print(f"\nTraining emphasis:\n  {d.emphasis}")
    return d


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m src.analysis.course <route.gpx|route.fit>")
        sys.exit(1)
    summarize(sys.argv[1])
