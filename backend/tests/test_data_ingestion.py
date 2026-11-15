
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
    sensors = ["modis", "viirs"]

    for sensor in sensors:
        for year in years:
            year_dir = raw_root / sensor / str(year)

            if not year_dir.exists():
                print(f"Directory not found: {year_dir}")
                continue

            filename = f"{sensor}_{year}_Brazil.csv"
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

    files = locate_brazilian_csv_files(RAW_ROOT)

    print("\nFiles found:")

    for file in files:
        print(f"  - {file.relative_to(PROJECT_ROOT)}")

    print("\n" + "=" * 60)
    print(f"Total files found: {len(files)}")
    print(f"Expected files: 12")
    print("=" * 60)

    if len(files) == 12:
        print("\nSUCCESS: All expected CSV files were found.")
    else:
        print("\nWARNING: Some expected CSV files are missing.")


if __name__ == "__main__":
    main()
