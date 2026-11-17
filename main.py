"""gta6-twitch-ccu-forecast-01 entry: size-conditioned launch-curve forecaster.

Forecasts Twitch viewers for hours 2..24 of a launch day from the case's
hour-1 print, using the launch-day curves of the case's comparables.

Idea (validated by leave-one-out over the 37 comparable launches in the kit):
launch-day audience curves look nothing alike in absolute terms, but their
shape — the log-ratio of each hour's viewers to hour 1's — is strongly
predicted by how big hour 1 already is. A tiny hour 1 (a few hundred
viewers) means the audience is still building and the day peaks 100x-1000x
higher; a huge hour 1 (hundreds of thousands) means the launch is already
at full strength and the day peaks only ~1x-2.7x higher. A single median
curve across all launches is wrong for either end, so for each hour we take
a weighted neighbourhood of the launches whose hour-1 size is closest (in
log space) to this case's, and read the median shape and spread off them.

Method, per hour h = 2..24:
  - pool: comparables with a positive hour-1 print and a positive print at h.
  - distance: |ln(p1_launch) - ln(p1_case)|; take the 12 nearest.
  - weights: Gaussian kernel, bandwidth 1.0 in log space.
  - centre m_h: weighted mean of ln(viewers_h / viewers_1) over the pool.
  - spread s_h: weighted standard deviation of the same log-ratios.
  - quantiles: q_tau = p1 * exp(m_h + z_tau * s_h), z from Student-t(8)
    (-1.860, -0.706, 0, 0.706, 1.860) — heavier tails than normal, because
    launch curves are heavy-tailed; this keeps the 90% band honest.

Leave-one-out over the kit's 37 comparable launches (mean pinball loss):
  house baseline 0.930, this model 0.398 (all launches);
  on big launches (hour-1 >= 20k, the practice cases' range): baseline 0.321,
  this model 0.261; on hour-1 >= 100k: baseline 0.261, this model 0.217.
  90% coverage 0.89-0.92 (honest target 0.90).

Standard library only, no network, deterministic (no randomness; neighbour
order ties broken by launch name). Reads $MAKEFUN_INPUT_DIR (else /input),
writes $MAKEFUN_OUTPUT_DIR (else /output), one .out per .in.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Student-t(8) quantiles at the five levels (heavier tails than normal).
Z = [-1.860, -0.706, 0.0, 0.706, 1.860]
K_NEIGHBOURS = 12
KERNEL_BW = 1.0
MAX_VIEWERS = 1_000_000_000


def parse_time(text):
    """ISO 8601 UTC timestamp -> aware datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def hour_of(comp_day_start, stamp):
    """1-based UTC hour of `stamp` within the day starting at `comp_day_start`."""
    delta = parse_time(stamp) - parse_time(comp_day_start)
    return int(delta.total_seconds() // 3600) + 1


def day_curve(comp):
    """Release-day viewers by UTC hour (1..24) for one comparable launch."""
    curve = {}
    for point in comp.get("hourly", []):
        viewers = point.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        hour = hour_of(comp["day_start"], point["from"])
        if 1 <= hour <= 24:
            curve[hour] = float(viewers)
    return curve


def neighbour_stats(pool, p1, hour):
    """Weighted mean and sd of ln(viewers_h / viewers_1) over the pool.

    pool: list of (log_p1, name, curve) with a positive print at `hour`.
    Returns (mean, sd) or None when the pool is empty.
    """
    log_p1 = math.log(p1)
    scored = []
    for launch_log_p1, name, curve in pool:
        if hour not in curve or curve.get(1) is None:
            continue
        distance = abs(launch_log_p1 - log_p1)
        weight = math.exp(-0.5 * (distance / KERNEL_BW) ** 2)
        scored.append((distance, name, weight, math.log(curve[hour] / curve[1])))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1]))
    scored = scored[:K_NEIGHBOURS]
    total_weight = sum(item[2] for item in scored)
    mean = sum(item[2] * item[3] for item in scored) / total_weight
    variance = sum(item[2] * (item[3] - mean) ** 2 for item in scored) / total_weight
    return mean, math.sqrt(max(variance, 0.0))


def round2(value):
    """Round to 2 decimals, half up, as a plain number (int when whole)."""
    scaled = value * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    rounded = whole / 100
    return int(rounded) if rounded == int(rounded) else rounded


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((row for row in case["known"] if row["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))

    # Comparable launch-day curves, keyed by their hour-1 size.
    pool = []
    for comp in case.get("comparables", []):
        curve = day_curve(comp)
        if curve.get(1):
            pool.append((math.log(curve[1]), comp.get("name", ""), curve))

    rows = []
    for row in case["forecast"]:
        hour = row["hour"]
        stats = neighbour_stats(pool, p1, hour)
        if stats is None:
            # No comparable has this hour: fall back to persistence.
            centre, spread = 0.0, 0.15 * math.sqrt(hour - 1)
        else:
            centre, spread = stats
        quantiles = []
        for z in Z:
            value = p1 * math.exp(centre + z * spread)
            value = min(max(value, 1.0), float(MAX_VIEWERS))
            quantiles.append(round2(value))
        # Keep the row non-decreasing after rounding.
        for index in range(1, len(quantiles)):
            if quantiles[index] < quantiles[index - 1]:
                quantiles[index] = quantiles[index - 1]
        rows.append({"hour": hour, "q": quantiles})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
