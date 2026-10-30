# The console menu follows the calculator's if-elif-else structure.

import csv

from src.analytics import period_summary, screen_extremes, trend_summaries
from src.config import BOUNDS, LABELS, MENU_OPTIONS
from src.forecaster import RollingForecaster
from src.gui_helpers import filter_observations, record_from_form
from src.reporting import export_analysis, format_backtest, format_record, format_summary
from src.weather_record import parse_timestamp, validate_number


def read_integer(prompt, minimum, maximum, default=None):
    while True:
        text = input(prompt).strip()
        if text == "" and default is not None:
            return default
        try:
            value = int(text)
            if value < minimum or value > maximum:
                raise ValueError("Out of range")
            return value
        except ValueError:
            print(f"Enter an integer from {minimum} to {maximum}.")


def read_number(parameter, old_value=None):
    label, unit = LABELS[parameter]
    minimum, maximum = BOUNDS[parameter]
    prompt = f"{label} ({unit}; {minimum} to {maximum})"
    if old_value is not None:
        prompt = prompt + f" [Enter keeps {old_value}]"
    while True:
        text = input(f"{prompt}: ").strip()
        if text == "" and old_value is not None:
            return old_value
        try:
            value = float(text)
            validate_number(parameter, value)
            return value
        except ValueError:
            print(f"Enter a finite number in the shown range.")


class WeatherApp:
    def __init__(self, manager, output_path):
        self.manager = manager
        self.output_path = output_path
        self.forecaster = RollingForecaster(manager)

    def run(self):
        print(f"\nDHAKA CITY WEATHER FORECAST AND TREND ANALYSIS")
        print(f"Historical data | source LST | educational estimates")
        while True:
            try:
                print(f"\nMAIN MENU")
                for choice, label in MENU_OPTIONS:
                    print(f"{choice:>2}. {label}")
                choice = input("Choose an option: ").strip()
                if choice == "0":
                    print(f"Goodbye. Successful changes are already saved.")
                    break
                elif choice == "1":
                    self.overview()
                elif choice == "2":
                    self.search()
                elif choice == "3":
                    self.summary()
                elif choice == "4":
                    self.trends()
                elif choice == "5":
                    self.extremes()
                elif choice == "6":
                    self.forecast()
                elif choice == "7":
                    self.add()
                elif choice == "8":
                    self.update()
                elif choice == "9":
                    self.delete()
                elif choice == "10":
                    self.export()
                elif choice == "11":
                    self.reload()
                elif choice == "12":
                    self.backtest()
                else:
                    print(f"Invalid menu choice. Select a number shown above.")
            except (ValueError, OSError, UnicodeError, csv.Error) as error:
                print(f"Could not finish: {error}")
                print(f"You can continue from the main menu.")
            except (EOFError, KeyboardInterrupt):
                print(f"\nSession closed. Successful changes are already saved.")
                break

    def overview(self):
        result = self.manager.quality_report()
        for key, value in result.items():
            print(f"{key}: {value}")

    def search(self):
        query = input("Date YYYY-MM-DD or hour YYYY-MM-DD HH:00: ")
        records = filter_observations(self.manager, query=query)
        for record in records:
            print(f"{format_record(record)}")
        print(f"Found {len(records)} record(s).")

    def summary(self):
        year = read_integer("Year: ", 1900, 2100)
        month = read_integer("Month (0 for whole year): ", 0, 12)
        if month == 0:
            month = None
        result = period_summary(self.manager, year, month)
        print(f"{format_summary(result)}")

    def trends(self):
        choice = read_integer("1 = yearly, 2 = monthly: ", 1, 2)
        if choice == 1:
            mode = "yearly"
        else:
            mode = "monthly"
        rows = trend_summaries(self.manager, mode)
        for row in rows:
            print(f"{row['period']} | Hours: {row['hours']} | Mean temperature: "
                  f"{row['temperature_mean_c']:.2f} C | Rain: {row['observed_rainfall_mm']:.2f} mm")

    def extremes(self):
        events = screen_extremes(self.manager.records)
        for event in events[:100]:
            print(f"{event['timestamp_lst']}: {event['tags']}")
        print(f"Total: {len(events)} events. The preview shows at most 100; export saves all.")

    def forecast(self):
        latest = self.manager.records[-1].record_id
        text = input(f"Cutoff YYYY-MM-DD HH:00 [Enter = {latest}]: ").strip()
        if text == "":
            text = latest
        cutoff = parse_timestamp(text)
        horizon = read_integer("Forecast hours [24]: ", 1, 24, 24)
        window = read_integer("Window hours [24]: ", 2, 168, 24)
        result = self.forecaster.forecast(cutoff, horizon, window)
        for row in result["predictions"]:
            print(f"{row['timestamp_lst']} | T: {row['T2M']:.2f} C | "
                  f"Humidity: {row['RH2M']:.2f}% | Rain: {row['PRECTOTCORR']:.3f} mm/hour")
        print(f"{result['note']}")

    def read_record(self, timestamp, original=None):
        previous = {}
        if original is not None:
            previous = original.to_row()
        values = {}
        for key, value in LABELS.items():
            old_value = None
            if key in previous:
                old_value = previous[key]
            values[key] = read_number(key, old_value)
        return record_from_form(timestamp.strftime("%Y-%m-%d %H:%M"), values)

    def add(self):
        timestamp = parse_timestamp(input("New timestamp YYYY-MM-DD HH:00: "))
        if self.manager.find_hour(timestamp) is not None:
            raise ValueError("Duplicate timestamp; use Update.")
        record = self.read_record(timestamp)
        self.manager.add(record)
        print(f"Added and saved {record.record_id}.")

    def update(self):
        timestamp = parse_timestamp(input("Existing timestamp YYYY-MM-DD HH:00: "))
        original = self.manager.find_hour(timestamp)
        if original is None:
            raise ValueError("Record not found.")
        record = self.read_record(timestamp, original)
        self.manager.update(record)
        print(f"Updated and saved {record.record_id}.")

    def delete(self):
        timestamp = parse_timestamp(input("Timestamp to delete YYYY-MM-DD HH:00: "))
        record = self.manager.find_hour(timestamp)
        if record is None:
            raise ValueError("Record not found.")
        print(f"{format_record(record)}")
        confirmation = input("Type DELETE to confirm: ")
        if confirmation == "DELETE":
            self.manager.delete(timestamp)
            print(f"Deleted and saved {record.record_id}.")
        else:
            print(f"Deletion cancelled.")

    def export(self):
        paths = export_analysis(self.manager, self.output_path)
        for path in paths:
            print(f"Saved: {path}")

    def reload(self):
        self.manager.load(self.manager.store_path)
        print(f"Reloaded {len(self.manager.records):,} records.")

    def backtest(self):
        year = read_integer("Evaluation year [2024]: ", 1900, 2100, 2024)
        result = self.forecaster.backtest(year)
        print(f"{format_backtest(result)}")
