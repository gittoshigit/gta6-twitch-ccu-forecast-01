"""Deterministic launch-day forecasts; Python standard library only."""

import json
import math
import os
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path

BW = 1.0
ALPHA = 0.0  # tools/cv.py leave-one-launch-out: mean 0.408515 vs 0.477386 at 0.25; baseline 0.929650.
SMOOTH = 3
MIN_POINTS = 8

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
HOURS = tuple(range(2, 25))


def round2(x):
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Expected positive finite viewers")
    return value


def first_viewers(case):
    rows = sorted(case.get("known", []), key=lambda r: json.dumps(r, sort_keys=True))
    for row in rows:
        if isinstance(row, dict) and row.get("hour") == 1:
            value = row.get("viewers")
            if isinstance(value, (int, float)) and math.isfinite(value):
                return max(1, value)
    for source in ("history_hourly", "history"):
        for row in reversed(case.get(source) or []):
            value = row.get("viewers") if isinstance(row, dict) else None
            if isinstance(value, (int, float)) and math.isfinite(value) and value > 0:
                return value
    return 1


def is_launch(comparable):
    if not isinstance(comparable, dict):
        return False
    # OR is deliberate: either marker identifies the one non-launch comparable.
    return not (
        "before release" in str(comparable.get("name") or "").lower()
        or str(comparable.get("unlock") or "").lower().startswith("not a launch")
    )


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def release_hours(comparable):
    """Extract positive observations at exact release-day hourly timestamps."""
    start = timestamp(comparable["day_start"])
    expected = {start + timedelta(hours=h - 1): h for h in range(1, 25)}
    result = {}
    for row in sorted(comparable["hourly"], key=lambda r: json.dumps(r, sort_keys=True)):
        try:
            hour = expected.get(timestamp(row["from"]))
            if hour is not None:
                result[hour] = positive(row["viewers"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return result


def baseline_logs(hour):
    return [z * 0.15 * math.sqrt(hour - 1) for z in Z]


def quantiles(p1, logs):
    # Clip in log space first, so even extreme finite inputs cannot overflow exp.
    base = math.log(positive(p1))
    result = []
    previous = 1
    for value in logs:
        if not math.isfinite(value):
            raise ValueError("Nonfinite log quantile")
        q = round2(math.exp(min(math.log(1e9), max(0, base + value))))
        previous = max(previous, min(1e9, q))
        result.append(previous)
    return result


def baseline_hours(p1, hours):
    return [{"hour": h, "q": quantiles(p1, baseline_logs(h))} for h in sorted(hours)]


def weighted_quantile(pairs, tau):
    pairs = sorted(pairs)
    cumulative = []
    total = 0.0
    for _, weight in pairs:
        total += weight
        cumulative.append(total)
    if total <= 0 or not math.isfinite(total):
        raise ValueError("No usable weights")
    target = max(cumulative[0], min(total, tau * total))
    index = bisect_left(cumulative, target)
    if index == 0:
        return pairs[0][0]
    fraction = (target - cumulative[index - 1]) / (cumulative[index] - cumulative[index - 1])
    return pairs[index - 1][0] + fraction * (pairs[index][0] - pairs[index - 1][0])


def model_hours(case, p1):
    if case.get("levels", LEVELS) != LEVELS:
        raise ValueError("Unsupported levels")
    if not math.isfinite(BW) or BW <= 0 or not 0 <= ALPHA <= 1:
        raise ValueError("Invalid model constants")
    if not isinstance(SMOOTH, int) or SMOOTH < 1:
        raise ValueError("Invalid smoothing window")
    pairs = {h: [] for h in HOURS}
    for comparable in sorted(case.get("comparables", []), key=lambda c: json.dumps(c, sort_keys=True)):
        try:
            if not is_launch(comparable):
                continue
            values = release_hours(comparable)
            if 1 not in values:
                continue
            log_v1 = math.log(values[1])
            distance = (math.log(p1) - log_v1) / BW
            weight = math.exp(-0.5 * distance * distance)
            for h in sorted(values):
                if h in pairs:
                    pairs[h].append((math.log(values[h]) - log_v1, weight))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    series = []
    for h in HOURS:
        if len(pairs[h]) < MIN_POINTS:
            series.append(baseline_logs(h))
        else:
            series.append([weighted_quantile(pairs[h], tau) for tau in LEVELS])
    result = []
    left = (SMOOTH - 1) // 2
    right = SMOOTH // 2
    for i, h in enumerate(HOURS):
        window = series[max(0, i - left):min(len(series), i + right + 1)]
        baseline = baseline_logs(h)
        logs = [(1 - ALPHA) * math.fsum(row[j] for row in window) / len(window)
                + ALPHA * baseline[j] for j in range(5)]
        result.append({"hour": h, "q": quantiles(p1, logs)})
    return result


def forecast_case(case: dict) -> dict:
    p1 = 1
    try:
        p1 = first_viewers(case)
        return {"hours": model_hours(case, p1)}
    except Exception:
        try:
            return {"hours": baseline_hours(p1, HOURS)}
        except Exception:
            try:
                flat = round2(min(1e9, max(1, positive(p1))))
            except Exception:
                flat = 1
            return {"hours": [{"hour": h, "q": [flat] * 5} for h in HOURS]}


def main():
    input_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(input_dir.glob("*.in")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            forecast = forecast_case(case)
        except Exception:
            forecast = forecast_case({})
        (output_dir / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":"), allow_nan=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
