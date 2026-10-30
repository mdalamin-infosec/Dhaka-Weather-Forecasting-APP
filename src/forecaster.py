# Moving-average forecasts and chronological accuracy checks.
# datetime and calendar are allowed standard-library modules.
# The moving-average and MAE/RMSE calculations are implemented with basic loops.

import calendar
from datetime import datetime, timedelta

from src.config import PARAMETERS, WET_HOUR_MM


def calculate_errors(actual, predicted):
    # MAE = mean absolute error; RMSE = root mean squared error.
    absolute_total = 0
    squared_total = 0
    for i in range(len(actual)):
        difference = predicted[i] - actual[i]
        absolute_total = absolute_total + abs(difference)
        squared_total = squared_total + difference ** 2
    return {
        "mae": absolute_total / len(actual),
        "rmse": (squared_total / len(actual)) ** 0.5
    }


class RollingForecaster:
    def __init__(self, manager):
        self.manager = manager

    def forecast(self, cutoff, horizon=24, window=24):
        if type(horizon) != int or horizon < 1 or horizon > 24:
            raise ValueError("Forecast hours must be an integer from 1 to 24.")
        if type(window) != int or window < 2 or window > 168:
            raise ValueError("Window must be an integer from 2 to 168 hours.")
        if self.manager.find_hour(cutoff) is None:
            raise ValueError("The cutoff must be an existing hourly timestamp.")

        history = {}
        for parameter in PARAMETERS:
            history[parameter] = []
        wet_hours = 0
        for offset in range(window - 1, -1, -1):
            timestamp = cutoff - timedelta(hours=offset)
            record = self.manager.find_hour(timestamp)
            if record is None:
                raise ValueError(f"Forecast needs {window} consecutive observed hours.")
            row = record.to_row()
            for parameter in PARAMETERS:
                history[parameter].append(row[parameter])
            if record.rainfall >= WET_HOUR_MM:
                wet_hours = wet_hours + 1
        recent_wet_fraction = 100 * wet_hours / window

        predictions = []
        for step in range(1, horizon + 1):
            forecast_time = cutoff + timedelta(hours=step)
            prediction = {"timestamp_lst": forecast_time.strftime("%Y-%m-%d %H:%M")}
            for key, value in history.items():
                recent_values = value[-window:]
                estimate = sum(recent_values) / window
                prediction[key] = estimate
                # Later steps include the estimate just calculated.
                value.append(estimate)
            prediction["recent_wet_fraction_pct"] = recent_wet_fraction
            predictions.append(prediction)

        result = {
            "method": "recursive trailing moving average",
            "cutoff_lst": cutoff.strftime("%Y-%m-%d %H:%M"),
            "window_hours": window,
            "horizon_hours": horizon,
            "predictions": predictions,
            "note": "Historical educational estimate, not a live forecast. Wet-hour fraction is not a calibrated rain probability."
        }
        return result

    def backtest(self, year=2024, window=24):
        if type(year) != int or year < 1900 or year > 2100:
            raise ValueError("Evaluation year must be from 1900 to 2100.")
        if type(window) != int or window < 2 or window > 168:
            raise ValueError("Window must be an integer from 2 to 168 hours.")
        if calendar.isleap(year):
            days = 366
        else:
            days = 365
        actual_temperature = []
        rolling_temperature = []
        last_temperature = []
        previous_day_temperature = []
        actual_rainfall = []
        rolling_rainfall = []
        forecast_days = 0
        skipped_days = 0

        for day_number in range(days):
            target_day = datetime(year, 1, 1) + timedelta(days=day_number)
            cutoff = target_day - timedelta(hours=1)
            targets = []
            previous = []
            complete = True
            for hour in range(24):
                actual = self.manager.find_hour(target_day + timedelta(hours=hour))
                old = self.manager.find_hour(target_day + timedelta(hours=hour - 24))
                if actual is None or old is None:
                    complete = False
                targets.append(actual)
                previous.append(old)
            if not complete:
                skipped_days = skipped_days + 1
                continue
            try:
                forecast = self.forecast(cutoff, 24, window)
            except ValueError:
                skipped_days = skipped_days + 1
                continue
            last = self.manager.find_hour(cutoff)
            for hour in range(24):
                actual = targets[hour]
                old = previous[hour]
                prediction = forecast["predictions"][hour]
                actual_temperature.append(actual.temperature)
                rolling_temperature.append(prediction["T2M"])
                last_temperature.append(last.temperature)
                previous_day_temperature.append(old.temperature)
                actual_rainfall.append(actual.rainfall)
                rolling_rainfall.append(prediction["PRECTOTCORR"])
            forecast_days = forecast_days + 1

        if len(actual_temperature) == 0:
            raise ValueError("No complete evaluation days with earlier history were found.")
        temperature_errors = {
            "rolling_mean": calculate_errors(actual_temperature, rolling_temperature),
            "last_observation": calculate_errors(actual_temperature, last_temperature),
            "previous_day_same_hour": calculate_errors(actual_temperature, previous_day_temperature)
        }
        result = {
            "year": year,
            "window_hours": window,
            "horizon_hours": 24,
            "forecast_days": forecast_days,
            "skipped_days": skipped_days,
            "evaluated_hours": len(actual_temperature),
            "expected_target_hours": days * 24,
            "coverage_pct": 100 * len(actual_temperature) / (days * 24),
            "temperature_c": temperature_errors,
            "rainfall_mm_per_hour": {"rolling_mean": calculate_errors(actual_rainfall, rolling_rainfall)},
            "protocol": "Issue at previous day 23:00 LST. Only observations up to each cutoff enter the forecast."
        }
        return result
