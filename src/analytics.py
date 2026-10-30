# Statistics and historical event screening using simple loops.

import calendar
from datetime import timedelta
import math

from src.config import PARAMETERS, SCREENING_THRESHOLDS, WET_HOUR_MM


def expected_calendar_hours(year, month=None):
    if month is not None:
        days = calendar.monthrange(year, month)[1]
    elif calendar.isleap(year):
        days = 366
    else:
        days = 365
    return days * 24


def measurement_lists(records):
    columns = {}
    for parameter in PARAMETERS:
        columns[parameter] = []
    for record in records:
        row = record.to_row()
        for parameter in PARAMETERS:
            columns[parameter].append(row[parameter])
    return columns


def calculate_median(values):
    # Arrange observations from smallest to largest.
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2

    if count % 2 == 1:
        return float(ordered[middle])
    else:
        return float((ordered[middle - 1] + ordered[middle]) / 2)


def calculate_population_std(values):
    # Population standard deviation: square root of mean squared deviation.
    average = sum(values) / len(values)
    squared_total = 0

    for number in values:
        difference = number - average
        squared_total = squared_total + difference ** 2

    variance = squared_total / len(values)
    return float(variance ** 0.5)


def summarize(records, expected_hours=None):
    if len(records) == 0:
        raise ValueError("No records match this selection.")

    start = records[0].timestamp
    end = records[0].timestamp
    for record in records:
        if record.timestamp < start:
            start = record.timestamp
        if record.timestamp > end:
            end = record.timestamp
    if expected_hours is None:
        expected_hours = int((end - start).total_seconds() / 3600) + 1

    columns = measurement_lists(records)
    statistics = {}
    for key, value in columns.items():
        statistics[key] = {
            "mean": sum(value) / len(value),
            "median": calculate_median(value),
            "minimum": min(value),
            "maximum": max(value),
            "std_population": calculate_population_std(value)
        }

    wet_hours = 0
    for rainfall in columns["PRECTOTCORR"]:
        if rainfall >= WET_HOUR_MM:
            wet_hours = wet_hours + 1

    result = {
        "count": len(records),
        "start_lst": start.strftime("%Y-%m-%d %H:%M"),
        "end_lst": end.strftime("%Y-%m-%d %H:%M"),
        "expected_hours": expected_hours,
        "missing_hours": expected_hours - len(records),
        "coverage_pct": 100 * len(records) / expected_hours,
        "statistics": statistics,
        "observed_rainfall_mm": sum(columns["PRECTOTCORR"]),
        "wet_hours": wet_hours,
        "wet_hour_fraction_pct": 100 * wet_hours / len(records)
    }
    return result


def period_summary(manager, year, month=None):
    records = manager.select(year, month)
    expected = expected_calendar_hours(year, month)
    return summarize(records, expected)


def trend_summaries(manager, mode="yearly", year=None):
    if mode != "yearly" and mode != "monthly":
        raise ValueError("Trend mode must be yearly or monthly.")
    groups = {}
    records = manager.select(year)
    for record in records:
        if mode == "monthly":
            period = record.timestamp.strftime("%Y-%m")
        else:
            period = record.timestamp.strftime("%Y")
        if period not in groups:
            groups[period] = []
        groups[period].append(record)

    results = []
    for period in sorted(groups):
        records = groups[period]
        record_year = records[0].timestamp.year
        if mode == "monthly":
            month = records[0].timestamp.month
        else:
            month = None
        expected = expected_calendar_hours(record_year, month)
        summary = summarize(records, expected)
        statistics = summary["statistics"]
        row = {
            "period": period,
            "hours": summary["count"],
            "coverage_pct": round(summary["coverage_pct"], 3),
            "temperature_mean_c": round(statistics["T2M"]["mean"], 4),
            "temperature_min_c": statistics["T2M"]["minimum"],
            "temperature_max_c": statistics["T2M"]["maximum"],
            "humidity_mean_pct": round(statistics["RH2M"]["mean"], 4),
            "pressure_mean_kpa": round(statistics["PS"]["mean"], 4),
            "wind_mean_ms": round(statistics["WS10M"]["mean"], 4),
            "observed_rainfall_mm": round(summary["observed_rainfall_mm"], 4)
        }
        results.append(row)
    return results


def screen_extremes(records, thresholds=SCREENING_THRESHOLDS):
    if len(thresholds) != 3:
        raise ValueError("Enter three screening thresholds.")
    for number in thresholds:
        if not math.isfinite(number) or number < 0:
            raise ValueError("Thresholds must be finite, non-negative numbers.")
    heat_limit, rain_limit, pressure_limit = thresholds
    index = {}
    for record in records:
        index[record.timestamp] = record

    events = []
    for timestamp in sorted(index):
        record = index[timestamp]
        tags = []
        if record.temperature > heat_limit:
            tags.append("High temperature")
        if record.rainfall > rain_limit:
            tags.append("Heavy hourly rain")
        previous_time = timestamp - timedelta(hours=3)
        drop = ""
        if previous_time in index:
            previous = index[previous_time]
            drop = round(previous.pressure - record.pressure, 6)
            if drop >= pressure_limit:
                tags.append("Pressure drop")

        if len(tags) > 0:
            event = {
                "timestamp_lst": record.record_id,
                "tags": "; ".join(tags),
                "temperature_c": record.temperature,
                "rainfall_mm_per_hour": record.rainfall,
                "pressure_kpa": record.pressure,
                "pressure_drop_3h_kpa": drop
            }
            events.append(event)
    return events


def correlations(records):
    if len(records) < 2:
        raise ValueError("At least two records are needed for correlation.")
    columns = measurement_lists(records)
    results = {}
    for first in range(len(PARAMETERS)):
        for second in range(first + 1, len(PARAMETERS)):
            first_name = PARAMETERS[first]
            second_name = PARAMETERS[second]
            left = columns[first_name]
            right = columns[second_name]
            left_mean = sum(left) / len(left)
            right_mean = sum(right) / len(right)
            numerator = 0
            left_total = 0
            right_total = 0
            for i in range(len(left)):
                left_difference = left[i] - left_mean
                right_difference = right[i] - right_mean
                numerator = numerator + left_difference * right_difference
                left_total = left_total + left_difference ** 2
                right_total = right_total + right_difference ** 2
            key = f"{first_name} / {second_name}"
            if min(left) == max(left) or min(right) == max(right):
                results[key] = None
            else:
                results[key] = numerator / (left_total * right_total) ** 0.5
    return results
