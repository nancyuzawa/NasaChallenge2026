
from pathlib import Path


# Project directories
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"


def locate_brazilian_csv_files(raw_root: Path):
    """
    Locate MODIS and VIIRS CSV files for Brazil
    from 2020 to 2025.
    """
    files = []

    years = range(2020, 2026)

    # Sensor-specific filename patterns
    sensors = {
        "modis": "modis_{year}_Brazil.csv",
        "viirs": "viirs-jpss1_{year}_Brazil.csv",
    }

    for sensor, filename_pattern in sensors.items():
        for year in years:
            year_dir = raw_root / sensor / str(year)

            if not year_dir.is_dir():
                print(f"Directory not found: {year_dir}")
                continue

            filename = filename_pattern.format(year=year)
            csv_file = year_dir / filename

            if csv_file.is_file():
                files.append(csv_file)
            else:
                print(f"File not found: {csv_file}")

    return files


def main():
    print("=" * 60)
    print("NASA FIRMS - RAW DATA FILE DISCOVERY")
    print("=" * 60)

    print(f"\nRaw data directory: {RAW_ROOT}")
    print("Country: Brazil")
    print("Years: 2020-2025")
    print("Sensors: MODIS and VIIRS")

    files = locate_brazilian_csv_files(RAW_ROOT)

    print("\nFiles found:")

    for file in files:
        print(f"  - {file.relative_to(PROJECT_ROOT)}")

    expected_files = 12
    found_files = len(files)

    print("\n" + "=" * 60)
    print(f"Total files found: {found_files}")
    print(f"Expected files: {expected_files}")
    print("=" * 60)

    if found_files == expected_files:
        print("\nSUCCESS: All expected CSV files were found.")
    else:
        print(
            f"\nWARNING: {expected_files - found_files} "
            "expected file(s) missing."
        )


if __name__ == "__main__":
    main()
