# Start the project. GUI is the default; --cli uses the simple console menu.

import csv
from pathlib import Path
import sys

from src.config import OUTPUT_PATH, SOURCE_PATH, STORE_PATH
from src.weather_manager import WeatherManager


def read_options(arguments):
    options = {
        "source": SOURCE_PATH,
        "store": STORE_PATH,
        "output": OUTPUT_PATH,
        "mode": "gui"
    }
    i = 0
    while i < len(arguments):
        argument = arguments[i]
        if argument == "--cli":
            options["mode"] = "cli"
        elif argument == "--demo":
            options["mode"] = "demo"
        elif argument == "--help":
            options["mode"] = "help"
        elif argument == "--source" or argument == "--store" or argument == "--output":
            if i + 1 >= len(arguments):
                raise ValueError(f"A file or folder path is required after {argument}.")
            i = i + 1
            if argument == "--source":
                options["source"] = Path(arguments[i])
            elif argument == "--store":
                options["store"] = Path(arguments[i])
            else:
                options["output"] = Path(arguments[i])
        else:
            raise ValueError(f"Unknown option: {argument}. Use --help.")
        i = i + 1
    return options


def load_project(options):
    if options["source"].resolve() == options["store"].resolve():
        raise ValueError("Use different source and working CSV paths.")
    manager = WeatherManager(options["store"])
    if options["store"].exists():
        manager.load(options["store"])
    else:
        manager.load(options["source"])
        manager.save()
    return manager


def main(arguments=None):
    if arguments is None:
        arguments = sys.argv[1:]
    try:
        options = read_options(arguments)
    except ValueError as error:
        print(f"{error}")
        return 1
    if options["mode"] == "help":
        print(f"python main.py                         Open the GUI")
        print(f"python main.py --cli                   Open the console menu")
        print(f"python main.py --demo                  Calculate and export a sample")
        print(f"Optional paths: --source FILE --store FILE --output FOLDER")
        return 0

    if options["mode"] == "gui":
        try:
            from src.gui import launch_gui
            return launch_gui(options)
        except ModuleNotFoundError as error:
            print(f"Missing module: {error}. Install requirements and Tkinter.")
            return 1

    try:
        manager = load_project(options)
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        print(f"Could not load the dataset: {error}")
        print(f"Existing files were kept. Check the paths or restore the working CSV.")
        return 1
    if manager.load_info["rejected_rows"] > 0:
        print(f"Warning: {manager.load_info['rejected_rows']} invalid or duplicate rows were rejected.")
    try:
        if options["mode"] == "demo":
            from src.analytics import period_summary
            from src.reporting import export_analysis, format_summary
            print(f"{format_summary(period_summary(manager, 2023, 7))}")
            paths = export_analysis(manager, options["output"])
            for path in paths:
                print(f"Saved: {path.name}")
        else:
            from src.interface import WeatherApp
            app = WeatherApp(manager, options["output"])
            app.run()
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        print(f"Could not finish: {error}")
        return 1
    return 0


# This standard line runs main() when this file is started directly.
if __name__ == "__main__":
    sys.exit(main())
