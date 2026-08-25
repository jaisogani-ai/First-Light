"""Telemetry Analysis Engine — deterministic, NOT an LLM. Every metric is a real
statistic (numpy) computed over a mission's actual telemetry rows: no interpretation, no
inference beyond arithmetic. Returns an honest 'no telemetry recorded' result rather than
fabricating statistics when a mission has no data yet."""

from datetime import datetime, timezone

import numpy as np

# A gap is flagged when the interval between consecutive samples exceeds this multiple of
# the median sampling interval — a real, simple statistical threshold, not a fixed magic
# number tuned to any one mission's cadence.
GAP_THRESHOLD_MULTIPLIER = 3.0

NUMERIC_FIELDS = ["omega_x", "omega_y", "omega_z", "reaction_wheel_momentum", "battery_soc_pct",
                  "temperature_c", "power_draw_w", "comm_delay_ms", "sensor_latency_ms"]
TREND_FIELDS = ["battery_soc_pct", "temperature_c", "reaction_wheel_momentum"]


def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _linear_trend(values: np.ndarray) -> dict:
    """Real least-squares linear fit (numpy.polyfit, degree 1) over sample index —
    slope is 'units per sample', not per second (sampling isn't assumed uniform)."""
    if len(values) < 2:
        return {"slope_per_sample": 0.0, "direction": "insufficient_data"}
    slope, _intercept = np.polyfit(np.arange(len(values)), values, 1)
    direction = "increasing" if slope > 1e-9 else "decreasing" if slope < -1e-9 else "stable"
    return {"slope_per_sample": float(slope), "direction": direction}


def run_telemetry_analysis(rows: list[dict]) -> dict:
    if not rows:
        return {"record_count": 0, "message": "No telemetry recorded for this mission yet"}

    rows = sorted(rows, key=lambda r: r["ts"])
    timestamps = [_parse_ts(r["ts"]) for r in rows]

    deltas_s = [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]
    out_of_order = sum(1 for d in deltas_s if d < 0)

    result = {
        "record_count": len(rows),
        "time_range": {"start": rows[0]["ts"], "end": rows[-1]["ts"]},
        "time_synchronization": {
            "monotonically_increasing": out_of_order == 0,
            "out_of_order_count": out_of_order,
        },
    }

    positive_deltas = [d for d in deltas_s if d > 0]
    if positive_deltas:
        median_interval = float(np.median(positive_deltas))
        result["sampling"] = {
            "median_interval_seconds": median_interval,
            "mean_interval_seconds": float(np.mean(positive_deltas)),
            "sampling_frequency_hz": (1.0 / median_interval) if median_interval > 0 else None,
        }
        gap_threshold = median_interval * GAP_THRESHOLD_MULTIPLIER
        gaps = []
        for i, d in enumerate(deltas_s):
            if d > gap_threshold:
                gaps.append({"after_ts": rows[i]["ts"], "before_ts": rows[i + 1]["ts"], "gap_seconds": d})
        result["packet_gaps"] = gaps
        result["communication_gaps"] = gaps  # same underlying cadence — telemetry arrival is the comm channel here
        result["missing_packets_estimate"] = sum(
            max(0, round(g["gap_seconds"] / median_interval) - 1) for g in gaps
        ) if median_interval > 0 else 0
    else:
        result["sampling"] = {"median_interval_seconds": None, "mean_interval_seconds": None, "sampling_frequency_hz": None}
        result["packet_gaps"] = []
        result["communication_gaps"] = []
        result["missing_packets_estimate"] = 0

    stats = {}
    for field in NUMERIC_FIELDS:
        values = np.array([r[field] for r in rows if r.get(field) is not None], dtype=float)
        if len(values) == 0:
            continue
        stats[field] = {
            "min": float(values.min()), "max": float(values.max()),
            "mean": float(values.mean()), "std": float(values.std()),
            "sample_count": len(values),
        }
    result["sensor_statistics"] = stats

    omega_mag = np.array([
        (r["omega_x"] ** 2 + r["omega_y"] ** 2 + r["omega_z"] ** 2) ** 0.5 for r in rows
    ])
    result["trends"] = {"attitude_rate_magnitude": _linear_trend(omega_mag)}
    for field in TREND_FIELDS:
        values = np.array([r[field] for r in rows if r.get(field) is not None], dtype=float)
        result["trends"][field] = _linear_trend(values)

    if "comm_delay_ms" in stats and "sensor_latency_ms" in stats:
        result["signal_quality"] = {
            "comm_delay_ms": stats["comm_delay_ms"], "sensor_latency_ms": stats["sensor_latency_ms"],
        }

    return result
