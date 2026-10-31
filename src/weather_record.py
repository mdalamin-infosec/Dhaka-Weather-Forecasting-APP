import math
from datetime import datetime

from src.config import BOUNDS


def parse_timestamp(text):
    text = text.strip()
    try:
        timestamp = datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("Use a real calendar date: YYYY-MM-DD HH:00.")

    if timestamp.strftime("%Y-%m-%d %H:%M") != text:
        raise ValueError("Use YYYY-MM-DD HH:00, including leading zeros.")
    if timestamp.minute != 0:
        raise ValueError("Minutes must be 00 because the data is hourly.")
    if timestamp.year < 1900 or timestamp.year > 2100:
        raise ValueError("Record year must be from 1900 to 2100.")
    return timestamp


def validate_number(parameter, value):
    if isinstance(value, bool):
        raise ValueError(f"{parameter} must be a number, not True or False.")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{parameter} must be a number.")
    minimum, maximum = BOUNDS[parameter]
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError(f"{parameter} must be between {minimum} and {maximum}.")


class WeatherRecord:
    def __init__(self, timestamp, temperature, humidity, pressure, wind_speed, rainfall):
        if not isinstance(timestamp, datetime):
            raise ValueError("A valid date and hour are required.")
        if timestamp.year < 1900 or timestamp.year > 2100:
            raise ValueError("Record year must be from 1900 to 2100.")
        if timestamp.minute != 0 or timestamp.second != 0 or timestamp.microsecond != 0:
            raise ValueError("Use a whole hour, with minutes and seconds set to zero.")
        if timestamp.tzinfo is not None:
            raise ValueError("Enter the source LST date without a timezone offset.")

        values = {
            "T2M": temperature,
            "RH2M": humidity,
            "PS": pressure,
            "WS10M": wind_speed,
            "PRECTOTCORR": rainfall
        }
        for key, value in values.items():
            validate_number(key, value)

        self.timestamp = timestamp
        self.temperature = float(temperature)
        self.humidity = float(humidity)
        self.pressure = float(pressure)
        self.wind_speed = float(wind_speed)
        self.rainfall = float(rainfall)
        self.record_id = timestamp.strftime("%Y-%m-%d %H:%M")

    def values(self):
        return (self.temperature, self.humidity, self.pressure, self.wind_speed, self.rainfall)

    def to_row(self):
        row = {
            "YEAR": self.timestamp.year,
            "MO": self.timestamp.month,
            "DY": self.timestamp.day,
            "HR": self.timestamp.hour,
            "T2M": self.temperature,
            "RH2M": self.humidity,
            "PS": self.pressure,
            "WS10M": self.wind_speed,
            "PRECTOTCORR": self.rainfall
        }
        return row

    def display(self):
        print(f"Timestamp: {self.record_id} LST")
        print(f"Temperature: {self.temperature:.2f} C")
        print(f"Humidity: {self.humidity:.2f} %")
        print(f"Pressure: {self.pressure:.2f} kPa")
        print(f"Wind speed: {self.wind_speed:.2f} m/s")
        print(f"Rainfall: {self.rainfall:.2f} mm/hour")


def record_from_row(row):
    try:
        year = int(row["YEAR"])
        month = int(row["MO"])
        day = int(row["DY"])
        hour = int(row["HR"])
        timestamp = datetime(year, month, day, hour)
        temperature = float(row["T2M"])
        humidity = float(row["RH2M"])
        pressure = float(row["PS"])
        wind_speed = float(row["WS10M"])
        rainfall = float(row["PRECTOTCORR"])
        record = WeatherRecord(timestamp, temperature, humidity, pressure, wind_speed, rainfall)
        return record
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("The row contains a missing or invalid date or measurement.")
