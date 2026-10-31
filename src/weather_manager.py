import csv
from datetime import timedelta
from pathlib import Path

from src.config import COLUMNS
from src.file_helpers import write_csv_file
from src.weather_record import record_from_row


class WeatherManager:
    def __init__(self, store_path):
        self.store_path = Path(store_path)
        self.records = []
        self.by_timestamp = {}
        self.by_day = {}
        self.years = set()
        self.load_info = {}

    def organize_records(self, records):
    
        by_timestamp = {}
        for record in records:
            by_timestamp[record.timestamp] = record

        self.records = []
        self.by_timestamp = {}
        self.by_day = {}
        self.years = set()
        timestamps = sorted(by_timestamp)
        for timestamp in timestamps:
            record = by_timestamp[timestamp]
            self.records.append(record)
            self.by_timestamp[timestamp] = record
            day = timestamp.date()
            if day not in self.by_day:
                self.by_day[day] = []
            self.by_day[day].append(record)
            self.years.add(timestamp.year)

    def load(self, path):
        accepted = []
        seen = set()
        rejected = 0
        duplicates = 0
        examples = []
        ignored = []
        header_found = False
        header=[]

        with open(path, "r", newline="", encoding="utf-8-sig") as file:
            for line in file:
                header = []
                for part in line.strip().split(","):
                    header.append(part.strip())
                valid_header = True
                for column in COLUMNS:
                    if column not in header:
                        valid_header = False
                if valid_header:
                    if len(header) != len(set(header)):
                        raise ValueError("The CSV header contains duplicate columns.")
                    header_found = True
                    break

            if not header_found:
                raise ValueError("Required weather columns are missing from the CSV.")
            for column in header:
                if column not in COLUMNS:
                    ignored.append(column)

            reader = csv.DictReader(file, fieldnames=header, strict=True)
            row_number = 0
            for row in reader:
                row_number = row_number + 1
                try:
                    if None in row:
                        raise ValueError("Too many CSV fields.")
                    for column in COLUMNS:
                        if row[column] is None:
                            raise ValueError("A CSV field is missing.")
                    record = record_from_row(row)
                    if record.timestamp in seen:
                        duplicates = duplicates + 1
                        raise ValueError("Duplicate timestamp; first valid row kept.")
                    seen.add(record.timestamp)
                    accepted.append(record)
                except ValueError as error:
                    rejected = rejected + 1
                    if len(examples) < 5:
                        examples.append(f"Row {row_number}: {error}")

        if len(accepted) == 0:
            raise ValueError("No valid weather records found; existing records were kept.")
        
        self.organize_records(accepted)
        self.load_info = {
            "source": Path(path).name,
            "accepted_rows": len(accepted),
            "rejected_rows": rejected,
            "duplicate_rows": duplicates,
            "ignored_columns": ignored,
            "rejection_examples": examples
        }
        return self.load_info

    def save(self, path=None, records=None):
        if path is None:
            path = self.store_path
        if records is None:
            records = self.records
        rows = []
        for record in records:
            rows.append(record.to_row())
        write_csv_file(path, rows, COLUMNS)

    def save_changes(self, changed):
        
        records = []
        for key, value in changed.items():
            records.append(value)
        self.save(records=records)
        self.organize_records(records)

    def add(self, record):
        if record.timestamp in self.by_timestamp:
            raise ValueError("Duplicate timestamp: use Update for an existing record.")
        changed = self.by_timestamp.copy()
        changed[record.timestamp] = record
        self.save_changes(changed)

    def update(self, record):
        if record.timestamp not in self.by_timestamp:
            raise ValueError("Record not found.")
        changed = self.by_timestamp.copy()
        changed[record.timestamp] = record
        self.save_changes(changed)

    def delete(self, timestamp):
        if timestamp not in self.by_timestamp:
            raise ValueError("Record not found.")
        if len(self.records) == 1:
            raise ValueError("Keep at least one record in the dataset.")
        changed = self.by_timestamp.copy()
        del changed[timestamp]
        self.save_changes(changed)

    def find_hour(self, timestamp):
        if timestamp in self.by_timestamp:
            return self.by_timestamp[timestamp]
        return None

    def find_day(self, day):
        if day in self.by_day:
            return self.by_day[day].copy()
        return []

    def select(self, year=None, month=None):
        if year is not None and (type(year) != int or year < 1900 or year > 2100):
            raise ValueError("Year must be an integer from 1900 to 2100.")
        if month is not None and (type(month) != int or month < 1 or month > 12):
            raise ValueError("Month must be an integer from 1 to 12.")
        selected = []
        for record in self.records:
            if year is not None and record.timestamp.year != year:
                continue
            if month is not None and record.timestamp.month != month:
                continue
            selected.append(record)
        return selected

    def quality_report(self):
        if len(self.records) == 0:
            return {"records": 0, "missing_hours": 0, "coverage_pct": 0.0}
        start = self.records[0].timestamp
        end = self.records[-1].timestamp
        expected = int((end - start) / timedelta(hours=1)) + 1
        result = {
            "records": len(self.records),
            "start_lst": self.records[0].record_id,
            "end_lst": self.records[-1].record_id,
            "expected_hours_in_span": expected,
            "missing_hours": expected - len(self.records),
            "coverage_pct": 100 * len(self.records) / expected,
            "time_standard": "LST as supplied; no timezone conversion",
            "load": self.load_info,
            "excluded_column": "PSC is excluded; PS is used for pressure."
        }
        return result
