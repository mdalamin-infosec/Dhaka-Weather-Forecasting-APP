# Fixed paths, tuples and dictionaries used by the project.

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = PROJECT_ROOT / "data/nasa_power_dhaka_weather_timeseries_dataset_2019_to_2024.csv"
STORE_PATH = PROJECT_ROOT / "data/weather_records.csv"
OUTPUT_PATH = PROJECT_ROOT / "output"

DATE_COLUMNS = ("YEAR", "MO", "DY", "HR")
PARAMETERS = ("T2M", "RH2M", "PS", "WS10M", "PRECTOTCORR")
COLUMNS = DATE_COLUMNS + PARAMETERS

LABELS = {
    "T2M": ("Temperature", "C"),
    "RH2M": ("Humidity", "%"),
    "PS": ("Pressure", "kPa"),
    "WS10M": ("Wind speed", "m/s"),
    "PRECTOTCORR": ("Rainfall", "mm/hour")
}

BOUNDS = {
    "T2M": (-60, 60),
    "RH2M": (0, 100),
    "PS": (80, 110),
    "WS10M": (0, 100),
    "PRECTOTCORR": (0, 300)
}

SCREENING_THRESHOLDS = (35.0, 10.0, 0.3)
WET_HOUR_MM = 0.1

MENU_OPTIONS = (
    ("1", "Dataset overview"),
    ("2", "Search records"),
    ("3", "Monthly or yearly summary"),
    ("4", "Monthly or yearly trends"),
    ("5", "Screen historical events"),
    ("6", "Generate a historical forecast"),
    ("7", "Add a record"),
    ("8", "Update a record"),
    ("9", "Delete a record"),
    ("10", "Export results"),
    ("11", "Reload saved records"),
    ("12", "Evaluate forecasts"),
    ("0", "Exit")
)
