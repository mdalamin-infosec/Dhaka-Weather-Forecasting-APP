import csv
import json
import os
from pathlib import Path


def write_csv_file(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".weather-{path.name}.tmp")
    try:
        with open(temporary_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_text_file(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".weather-{path.name}.tmp")
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            file.write(text)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_json_file(path, data):
    text = json.dumps(data, indent=2, allow_nan=False)
    write_text_file(path, text)
