# Use f-strings for readable results and export dictionaries to files.

from pathlib import Path

from src.analytics import correlations, screen_extremes, summarize, trend_summaries
from src.config import LABELS
from src.file_helpers import write_csv_file, write_json_file, write_text_file
from src.forecaster import RollingForecaster

EVENT_COLUMNS = (
    "timestamp_lst", "tags", "temperature_c", "rainfall_mm_per_hour",
    "pressure_kpa", "pressure_drop_3h_kpa"
)
FORECAST_COLUMNS = (
    "timestamp_lst", "T2M", "RH2M", "PS", "WS10M", "PRECTOTCORR",
    "recent_wet_fraction_pct"
)
RECORD_HEADER = "Timestamp LST         T(C)     RH(%)   PS(kPa)  Wind(m/s) Rain(mm/h)"


def format_record(record):
    text = f"{record.record_id}  {record.temperature:7.2f}  {record.humidity:7.2f}  "
    text = text + f"{record.pressure:7.2f}  {record.wind_speed:7.2f}  {record.rainfall:8.2f}"
    return text


def format_summary(summary):
    text = f"Observed period (LST): {summary['start_lst']} to {summary['end_lst']}\n"
    text = text + f"Records: {summary['count']:,} / {summary['expected_hours']:,} expected hours\n"
    text = text + f"Coverage: {summary['coverage_pct']:.2f}%\n\n"
    text = text + f"Parameter                 Mean    Median       Min       Max    Std(pop)\n"
    for key, value in summary["statistics"].items():
        label, unit = LABELS[key]
        text = text + f"{label + ' (' + unit + ')':24} {value['mean']:8.3f} "
        text = text + f"{value['median']:9.3f} {value['minimum']:9.3f} "
        text = text + f"{value['maximum']:9.3f} {value['std_population']:9.3f}\n"
    text = text + f"\nObserved rainfall: {summary['observed_rainfall_mm']:.2f} mm\n"
    text = text + f"Wet hours (rain >= 0.1 mm/hour): {summary['wet_hours']:,} "
    text = text + f"({summary['wet_hour_fraction_pct']:.2f}%)\n"
    text = text + f"Missing hours: {summary['missing_hours']:,}. Rainfall totals cover observed hours only."
    return text


def format_backtest(result):
    text = f"Historical evaluation: {result['year']}\n"
    text = text + f"Window: {result['window_hours']} hours; horizon: 24 hours\n"
    text = text + f"Evaluated: {result['evaluated_hours']:,} hours in {result['forecast_days']} days\n"
    text = text + f"Skipped days: {result['skipped_days']}\n\n"
    text = text + f"Temperature method                  MAE(C)   RMSE(C)\n"
    for key, value in result["temperature_c"].items():
        text = text + f"{key:35} {value['mae']:7.3f}   {value['rmse']:7.3f}\n"
    rain = result["rainfall_mm_per_hour"]["rolling_mean"]
    text = text + f"\nRain estimate: MAE {rain['mae']:.3f}; RMSE {rain['rmse']:.3f} mm/hour\n"
    text = text + f"Lower errors are better. Compare all three methods before judging accuracy."
    return text


def export_analysis(manager, directory):
    directory = Path(directory)
    summary = summarize(manager.records)
    monthly = trend_summaries(manager, "monthly")
    yearly = trend_summaries(manager, "yearly")
    events = screen_extremes(manager.records)
    forecaster = RollingForecaster(manager)
    try:
        forecast = forecaster.forecast(manager.records[-1].timestamp)
    except ValueError as error:
        forecast = {"status": "unavailable", "reason": str(error), "predictions": []}
    try:
        evaluation = forecaster.backtest(max(manager.years))
    except ValueError as error:
        evaluation = {"status": "unavailable", "reason": str(error)}
    if len(manager.records) >= 2:
        correlation_results = correlations(manager.records)
    else:
        correlation_results = {"status": "unavailable", "reason": "At least two records are needed."}

    text = f"DHAKA CITY WEATHER FORECAST AND TREND ANALYSIS\n\n"
    text = text + format_summary(summary)
    text = text + f"\n\nDATA NOTES\nTimes are source LST, not converted to civil time.\n"
    text = text + f"Pressure uses PS. PSC is excluded pending source verification.\n"
    text = text + f"Historical estimates and threshold screens are educational outputs.\n"
    if "reason" in forecast:
        text = text + f"\nForecast unavailable: {forecast['reason']}\n"
    if "reason" in evaluation:
        text = text + f"\nEvaluation unavailable: {evaluation['reason']}\n"
    else:
        text = text + f"\n{format_backtest(evaluation)}\n"

    # Fixed output filenames also replace stale results after data changes.
    paths = []
    path = directory / "weather_summary_report.txt"
    write_text_file(path, text)
    paths.append(path)
    path = directory / "summary.json"
    write_json_file(path, summary)
    paths.append(path)
    path = directory / "quality_report.json"
    write_json_file(path, manager.quality_report())
    paths.append(path)
    path = directory / "monthly_trends.csv"
    write_csv_file(path, monthly, tuple(monthly[0]))
    paths.append(path)
    path = directory / "yearly_trends.csv"
    write_csv_file(path, yearly, tuple(yearly[0]))
    paths.append(path)
    path = directory / "extreme_events.csv"
    write_csv_file(path, events, EVENT_COLUMNS)
    paths.append(path)
    path = directory / "correlations.json"
    write_json_file(path, correlation_results)
    paths.append(path)
    path = directory / "forecast.json"
    write_json_file(path, forecast)
    paths.append(path)
    path = directory / "forecast.csv"
    write_csv_file(path, forecast["predictions"], FORECAST_COLUMNS)
    paths.append(path)
    path = directory / "backtest_summary.json"
    write_json_file(path, evaluation)
    paths.append(path)
    return paths
