"""Tests for the stream-based session classifier (R11).

Builds synthetic power streams with known shapes and checks the classifier labels
them correctly. No network. Run: python -m tests.test_compliance
"""
from __future__ import annotations

from src.analysis.compliance import classify, metrics

FTP = 272


def _crit() -> list[float]:
    # 60 s soft pedal (80 W) then 20 s surge (450 W), repeated for ~60 min
    s = []
    for _ in range(45):
        s += [80] * 60 + [450] * 20
    return s


def _endurance() -> list[float]:
    return [175] * 3600  # steady Z2, ~0.64 IF


def _threshold() -> list[float]:
    s = [150] * 600                     # warmup
    for _ in range(2):
        s += [255] * 720                # 12 min @ ~0.94 FTP
        s += [150] * 300                # recovery
    s += [150] * 300                    # cooldown
    return s


def test_classifier() -> None:
    assert classify(metrics(_crit(), FTP))[0] == "group_ride_crit"
    assert classify(metrics(_endurance(), FTP))[0] == "endurance"
    assert classify(metrics(_threshold(), FTP))[0] == "threshold"
    print("test_classifier: OK")


if __name__ == "__main__":
    test_classifier()
    print("All compliance tests passed.")
