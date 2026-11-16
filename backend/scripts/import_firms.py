from pathlib import Path
import argparse
import sys
import sqlite3

# Diretório backend/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Permite importar o pacote src sem instalar o projeto.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.firms_ingestion import ingest_all
from src.fire_store import readonly
from src.parquet_writer import export_existing


def _main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Importa arquivos históricos MODIS e VIIRS da NASA FIRMS "
            "e grava um índice SQLite local para o Dashboard."
        )
    )

    parser.add_argument(
        "--raw",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw",
        help="Diretório com as subpastas modis/ e viirs/.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed",
        help="Diretório de saída do índice SQLite.",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100_000,
        help="Quantidade de linhas lidas por chunk (padrão: 100000).",
    )

    parser.add_argument("--export-only", action="store_true", help="Reorganiza o SQLite existente sem reler os arquivos brutos.")
    parser.add_argument("--start-year", type=int, default=2020, help="Primeiro ano (padrao: 2020).")
    parser.add_argument("--end-year", type=int, default=2025, help="Ultimo ano (padrao: 2025).")
    parser.add_argument("--match", help="Filtro opcional de nome, por exemplo *Brazil*.csv")
    args = parser.parse_args()

    if args.chunk_size <= 0:
        parser.error("--chunk-size precisa ser maior que zero.")

    if not 1900 <= args.start_year <= args.end_year <= 9998:
        parser.error("Periodo de anos invalido (1900 a 9998).")

    print(f"[saida] {args.output.resolve()}", flush=True)
    print(f"[periodo] {args.start_year}-{args.end_year}", flush=True)
    if args.export_only:
        print("[modo] Exportar dados ja existentes no SQLite.", flush=True)
        database = args.output / "firewatch.sqlite"
        if not database.is_file():
            parser.error(f"Base inexistente: {database}")
        conn = readonly(database, timeout=5)
        try:
            export_existing(conn, args.output, args.start_year, args.end_year, args.match)
        finally:
            conn.close()
        return

    print(f"[entrada] {args.raw.resolve()}", flush=True)
    print("[modo] Importar e salvar em sensor/ano/pais/part-NNN.parquet.", flush=True)
    ingest_all(
        raw_root=args.raw,
        output_dir=args.output,
        chunk_size=args.chunk_size,
        match=args.match,
        start_year=args.start_year,
        end_year=args.end_year,
    )


def main() -> None:
    try:
        _main()
    except sqlite3.OperationalError as error:
        code = getattr(error, "sqlite_errorcode", 0) or 0
        if (code & 255) not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) and not any(
            word in str(error).lower() for word in ("locked", "busy")
        ):
            raise
        print("Base SQLite ocupada por outro processo. Aguarde a importacao terminar "
              "ou interrompa-a com Ctrl+C no terminal dela e execute novamente.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
