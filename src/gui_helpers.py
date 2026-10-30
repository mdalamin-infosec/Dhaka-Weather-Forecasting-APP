"""Small, testable input and selection functions shared by the Tkinter screens."""

from datetime import datetime

from .analytics import period_summary, summarize
from .config import LABELS, PARAMETERS
from .weather_manager import WeatherManager
from .weather_record import WeatherRecord, parse_timestamp


def filter_observations(manager, year=None, month=None, query=""):
    """Filter by calendar period and optionally an exact date or hourly ID."""
    selected = manager.select(year, month)
    query = query.strip()
    if not query:
        return selected
    if len(query) == 10:
        try:
            day = datetime.strptime(query, "%Y-%m-%d").date()
            if day.isoformat() != query:
                raise ValueError
        except ValueError as exc:
            raise ValueError(
                "Enter a real date as YYYY-MM-DD, or an hour as YYYY-MM-DD HH:00."
            ) from exc
        return [record for record in selected if record.timestamp.date() == day]
    stamp = parse_timestamp(query)
    return [record for record in selected if record.timestamp == stamp]


def record_from_form(timestamp_text, field_values):
    """Read form text, convert measurements to numbers, then validate the record."""
    stamp = parse_timestamp(timestamp_text)
    values = {}
    for parameter in PARAMETERS:
        text = str(field_values.get(parameter, "")).strip()
        try:
            if not text:
                raise ValueError
            values[parameter] = float(text)
        except ValueError as exc:
            raise ValueError(f"{LABELS[parameter][0]} needs a numeric value.") from exc
    return WeatherRecord(
        timestamp=stamp,
        temperature=values["T2M"],
        humidity=values["RH2M"],
        pressure=values["PS"],
        wind_speed=values["WS10M"],
        rainfall=values["PRECTOTCORR"],
    )


def selected_summary(manager, year=None, month=None):
    """Return both the calculated summary and the records used to calculate it."""
    if year is None:
        if month is not None:
            raise ValueError("Select a year before selecting a month.")
        return summarize(manager.records), list(manager.records)
    return period_summary(manager, year, month), manager.select(year, month)


def daily_temperatures(records):
    """Group temperatures by date and calculate a mean for each observed day."""
    grouped = {}
    for record in records:
        day = record.timestamp.date()
        if day not in grouped:
            grouped[day] = []
        grouped[day].append(record.temperature)

    daily_means = []
    for day, temperatures in sorted(grouped.items()):
        mean_temperature = sum(temperatures) / len(temperatures)
        daily_means.append((day.isoformat(), mean_temperature))
    return daily_means


def snapshot_manager(manager):
    """Give a background calculation its own list and indexes.

    The simple model does not freeze objects. The application only edits data by
    replacing whole record objects, so a copied manager remains consistent.
    """
    snapshot = WeatherManager(manager.store_path)
    snapshot.organize_records(list(manager.records))
    snapshot.load_info = manager.load_info.copy()
    return snapshot
