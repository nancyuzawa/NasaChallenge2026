from pathlib import Path
import argparse

from src.firms_ingestion import ingest_all


def main():
    parser = argparse.ArgumentParser(
        description="Importa CSVs históricos MODIS e VIIRS do NASA FIRMS."
    )
    parser.add_argument(
        "--raw",
        default="data/raw",
        help="Pasta que contém as subpastas modis/ e viirs/."
    )
    parser.add_argument(
        "--output",
        default="data/processed",
        help="Pasta de saída."
    )
    parser.add_argument(
        "--no-deduplicate",
        action="store_true",
        help="Desativa a deduplicação operacional."
    )
    args = parser.parse_args()

    ingest_all(
        raw_root=Path(args.raw),
        output_dir=Path(args.output),
        deduplicate=not args.no_deduplicate
    )


if __name__ == "__main__":
    main()
