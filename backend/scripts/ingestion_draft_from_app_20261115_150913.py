from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterator
from zipfile import BadZipFile, ZipFile
import re

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


# ============================================================
# CONFIGURAÇÕES
# ============================================================

REQUIRED_COLUMNS = [
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
]

OUTPUT_COLUMNS = [
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "frp",
    "brightness",
    "bright_ti4",
    "bright_t31",
    "bright_ti5",
    "scan",
    "track",
    "daynight",
    "type",
    "version",
    "sensor",
    "source_file",
    "ingested_at_utc",
]

NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "frp",
    "brightness",
    "bright_ti4",
    "bright_t31",
    "bright_ti5",
    "scan",
    "track",
]

TEXT_COLUMNS = [
    "satellite",
    "instrument",
    "confidence",
    "daynight",
    "type",
    "version",
]

DEFAULT_CHUNK_SIZE = 100_000

ALIASES = {
    "lat": "latitude",
    "latitude": "latitude",
    "lon": "longitude",
    "long": "longitude",
    "longitude": "longitude",
    "date": "acq_date",
    "acq_date": "acq_date",
    "time": "acq_time",
    "acq_time": "acq_time",
    "sat": "satellite",
    "satellite": "satellite",
    "instrument": "instrument",
    "conf": "confidence",
    "confidence": "confidence",
    "day_night": "daynight",
    "daynight": "daynight",
    "bright_ti4": "bright_ti4",
    "bright_ti5": "bright_ti5",
    "bright_t31": "bright_t31",
    "brightness": "brightness",
    "frp": "frp",
    "scan": "scan",
    "track": "track",
    "type": "type",
    "version": "version",
}

PARQUET_SCHEMA = pa.schema(
    [
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("acq_date", pa.string()),
        ("acq_time", pa.string()),
        ("satellite", pa.string()),
        ("instrument", pa.string()),
        ("confidence", pa.string()),
        ("frp", pa.float64()),
        ("brightness", pa.float64()),
        ("bright_ti4", pa.float64()),
        ("bright_t31", pa.float64()),
        ("bright_ti5", pa.float64()),
        ("scan", pa.float64()),
        ("track", pa.float64()),
        ("daynight", pa.string()),
        ("type", pa.string()),
        ("version", pa.string()),
        ("sensor", pa.string()),
        ("source_file", pa.string()),
        ("ingested_at_utc", pa.string()),
    ]
)


# ============================================================
# NORMALIZAÇÃO E VALIDAÇÃO
# ============================================================

def normalize_column_name(name: object) -> str:
    """Normaliza nomes e aplica aliases conhecidos do FIRMS."""
    value = str(name).strip().lower()
    value = re.sub(r"[^a-z0-9_]", "", value)
    return ALIASES.get(value, value)


def normalize_time(series: pd.Series) -> pd.Series:
    """
    Normaliza horários para HHMM e invalida horários impossíveis.
    Exemplos aceitos: 823, 0823, 08:23 e 823.0.
    """
    values = series.astype("string").str.strip()
    values = values.str.replace(":", "", regex=False)
    values = values.str.replace(r"\.0$", "", regex=True)

    numeric = values.str.fullmatch(r"\d{1,4}").fillna(False)
    values = values.where(numeric).str.zfill(4)

    hour = pd.to_numeric(values.str.slice(0, 2), errors="coerce")
    minute = pd.to_numeric(values.str.slice(2, 4), errors="coerce")

    valid_time = hour.between(0, 23) & minute.between(0, 59)
    return values.where(valid_time)


def prepare_dataframe(
    frame: pd.DataFrame,
    sensor: str,
    source_file: str,
) -> tuple[pd.DataFrame, dict]:
    """Padroniza um chunk MODIS ou VIIRS no esquema comum do projeto."""
    df = frame.copy()

    df.columns = [normalize_column_name(column) for column in df.columns]
    df = df.loc[:, ~df.columns.duplicated()].copy()

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            f"{source_file}: colunas obrigatórias ausentes: {missing}"
        )

    # Cria colunas opcionais ausentes para manter o mesmo schema.
    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    # Campos numéricos. Valores não conversíveis viram nulos.
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("float64")

    # Datas no padrão ISO YYYY-MM-DD.
    parsed_dates = pd.to_datetime(df["acq_date"], errors="coerce")
    df["acq_date"] = parsed_dates.dt.strftime("%Y-%m-%d").astype("string")

    # Horário HHMM, validando também hora e minuto.
    df["acq_time"] = normalize_time(df["acq_time"])

    # Mantém confidence, type e version como texto:
    # MODIS pode trazer confidence numérico e VIIRS categorias como "n".
    for column in TEXT_COLUMNS:
        df[column] = df[column].astype("string").str.strip()

    df["sensor"] = sensor.upper()
    df["source_file"] = source_file
    df["ingested_at_utc"] = datetime.now(timezone.utc).isoformat()

    rows_read = len(df)

    valid = (
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
        & df["acq_date"].notna()
        & df["acq_time"].notna()
    )

    invalid_count = int((~valid).sum())
    standardized = df.loc[valid, OUTPUT_COLUMNS].copy()

    report = {
        "source_file": source_file,
        "sensor": sensor.upper(),
        "rows_read": rows_read,
        "rows_valid": len(standardized),
        "rows_invalid": invalid_count,
    }

    return standardized, report


# ============================================================
# LEITURA EM CHUNKS
# ============================================================

def read_csv_chunks(
    path: Path,
    member: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[pd.DataFrame]:
    """Lê CSV, CSV.GZ ou membro CSV de um ZIP sem carregar tudo na RAM."""
    if member is not None:
        with ZipFile(path) as archive:
            with archive.open(member) as file:
                reader = pd.read_csv(
                    file,
                    encoding="utf-8-sig",
                    chunksize=chunk_size,
                    low_memory=True,
                )
                yield from reader
        return

    compression = "gzip" if path.name.lower().endswith(".csv.gz") else "infer"

    reader = pd.read_csv(
        path,
        encoding="utf-8-sig",
        compression=compression,
        chunksize=chunk_size,
        low_memory=True,
    )
    yield from reader


def iter_csv_files(
    path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[tuple[str, Iterator[pd.DataFrame]]]:
    """Retorna cada CSV encontrado, inclusive CSVs dentro de arquivos ZIP."""
    if path.suffix.lower() == ".zip":
        try:
            with ZipFile(path) as archive:
                members = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".csv") and not name.endswith("/")
                ]
        except BadZipFile as exc:
            raise ValueError(f"Arquivo ZIP inválido: {path}") from exc

        for member in members:
            yield (
                f"{path.name}:{member}",
                read_csv_chunks(path, member=member, chunk_size=chunk_size),
            )

    elif path.suffix.lower() == ".csv" or path.name.lower().endswith(".csv.gz"):
        yield (
            path.name,
            read_csv_chunks(path, chunk_size=chunk_size),
        )


# ============================================================
# DESCOBERTA E NOMES DE SAÍDA
# ============================================================

def discover_sensor_files(folder: Path) -> list[Path]:
    """Localiza recursivamente arquivos CSV, CSV.GZ e ZIP."""
    if not folder.exists():
        print(f"[AVISO] Diretório não encontrado: {folder}")
        return []

    files = [
        path
        for path in folder.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() in {".csv", ".zip"}
            or path.name.lower().endswith(".csv.gz")
        )
    ]
    return sorted(files)


def build_source_name(path: Path, raw_root: Path, member_name: str) -> str:
    """Gera uma identificação relativa e rastreável do arquivo de origem."""
    try:
        relative_path = path.relative_to(raw_root).as_posix()
    except ValueError:
        relative_path = path.name

    if ":" in member_name:
        archive_name, inner_member = member_name.split(":", 1)
        return f"{relative_path}::{inner_member}"

    return relative_path


def build_output_stem(source_file: str) -> str:
    """Cria nome determinístico e evita colisão entre arquivos homônimos."""
    source_hash = sha256(source_file.encode("utf-8")).hexdigest()[:12]
    original_name = source_file.split("::")[-1].split("/")[-1]
    original_name = re.sub(r"\.csv(\.gz)?$", "", original_name, flags=re.IGNORECASE)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", original_name).strip("_")
    return f"{safe_name or 'firms_data'}_{source_hash}"


# ============================================================
# GRAVAÇÃO PARQUET
# ============================================================

def dataframe_to_arrow(df: pd.DataFrame) -> pa.Table:
    """Converte o chunk para o schema estável compartilhado pelos sensores."""
    return pa.Table.from_pandas(
        df[OUTPUT_COLUMNS],
        schema=PARQUET_SCHEMA,
        preserve_index=False,
        safe=False,
    )


def write_source_to_parquet(
    chunks: Iterator[pd.DataFrame],
    sensor: str,
    source_file: str,
    output_dir: Path,
) -> dict:
    """
    Processa um CSV de origem em chunks e grava um Parquet por ano de aquisição.
    A escrita ocorre primeiro em arquivo temporário e só depois é finalizada.
    """
    writers: dict[int, pq.ParquetWriter] = {}
    temporary_paths: dict[int, Path] = {}
    final_paths: dict[int, Path] = {}
    rows_read = 0
    rows_valid = 0
    rows_invalid = 0
    chunk_count = 0

    output_stem = build_output_stem(source_file)

    try:
        for raw_chunk in chunks:
            chunk_count += 1
            standardized, report = prepare_dataframe(
                raw_chunk,
                sensor=sensor,
                source_file=source_file,
            )

            rows_read += report["rows_read"]
            rows_valid += report["rows_valid"]
            rows_invalid += report["rows_invalid"]

            if standardized.empty:
                print(
                    f"    Chunk {chunk_count}: "
                    f"{report['rows_read']:,} lidas, 0 válidas"
                )
                continue

            # Agrupa pelo ano real da data de aquisição.
            years = standardized["acq_date"].str.slice(0, 4)
            for year_text, year_frame in standardized.groupby(years, sort=True):
                year = int(year_text)
                year_dir = output_dir / sensor.lower() / f"year={year}"
                year_dir.mkdir(parents=True, exist_ok=True)

                final_path = year_dir / f"{output_stem}.parquet"
                temporary_path = year_dir / f"{output_stem}.parquet.tmp"

                if year not in writers:
                    # Remove temporário abandonado de uma execução anterior.
                    if temporary_path.exists():
                        temporary_path.unlink()

                    writers[year] = pq.ParquetWriter(
                        temporary_path,
                        PARQUET_SCHEMA,
                        compression="snappy",
                    )
                    temporary_paths[year] = temporary_path
                    final_paths[year] = final_path

                table = dataframe_to_arrow(year_frame)
                writers[year].write_table(table)

            print(
                f"    Chunk {chunk_count}: "
                f"{report['rows_read']:,} lidas, "
                f"{report['rows_valid']:,} válidas, "
                f"{report['rows_invalid']:,} inválidas"
            )

        # Fecha todos os writers antes de publicar os arquivos finais.
        for writer in writers.values():
            writer.close()

        # Substituição atômica: o arquivo final só aparece após concluir a escrita.
        for year, temporary_path in temporary_paths.items():
            temporary_path.replace(final_paths[year])

    except Exception:
        for writer in writers.values():
            try:
                writer.close()
            except Exception:
                pass

        for temporary_path in temporary_paths.values():
            if temporary_path.exists():
                temporary_path.unlink()

        raise

    return {
        "source_file": source_file,
        "sensor": sensor.upper(),
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "rows_invalid": rows_invalid,
        "chunks_processed": chunk_count,
        "parquet_files": ";".join(str(path) for path in final_paths.values()),
        "status": "completed" if chunk_count else "empty",
    }


# ============================================================
# INGESTÃO COMPLETA
# ============================================================

def ingest_all(
    raw_root: Path,
    output_dir: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> pd.DataFrame:
    """
    Executa a ingestão histórica MODIS e VIIRS.

    Observação: esta primeira versão não remove duplicatas e reprocessa
    os arquivos de origem quando o comando é executado novamente.
    """
    raw_root = Path(raw_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sensors = {
        "MODIS": raw_root / "modis",
        "VIIRS": raw_root / "viirs",
    }

    all_files: list[tuple[Path, str]] = []
    for sensor, folder in sensors.items():
        files = discover_sensor_files(folder)
        print(f"\n[{sensor}] Arquivos encontrados: {len(files)}")
        all_files.extend((path, sensor) for path in files)

    if not all_files:
        raise RuntimeError(
            "Nenhum CSV, CSV.GZ ou ZIP foi encontrado em "
            "data/raw/modis ou data/raw/viirs."
        )

    reports: list[dict] = []

    for index, (path, sensor) in enumerate(all_files, start=1):
        print(f"\n[{index}/{len(all_files)}] Processando: {path}")

        for member_name, chunks in iter_csv_files(path, chunk_size=chunk_size):
            source_file = build_source_name(path, raw_root, member_name)
            print(f"  Origem: {source_file}")

            report = write_source_to_parquet(
                chunks=chunks,
                sensor=sensor,
                source_file=source_file,
                output_dir=output_dir,
            )
            reports.append(report)

            print(
                f"  Resultado: lidas={report['rows_read']:,} | "
                f"válidas={report['rows_valid']:,} | "
                f"inválidas={report['rows_invalid']:,} | "
                f"status={report['status']}"
            )

    report_df = pd.DataFrame(reports)

    total_read = int(report_df["rows_read"].sum()) if not report_df.empty else 0
    total_valid = int(report_df["rows_valid"].sum()) if not report_df.empty else 0
    total_invalid = int(report_df["rows_invalid"].sum()) if not report_df.empty else 0

    print("\n" + "=" * 65)
    print("RELATÓRIO FINAL - NASA FIRMS")
    print("=" * 65)
    print(f"Arquivos CSV processados: {len(report_df):,}")
    print(f"Registros lidos: {total_read:,}")
    print(f"Registros válidos: {total_valid:,}")
    print(f"Registros inválidos: {total_invalid:,}")
    print(f"Saída Parquet: {output_dir}")
    print("=" * 65)

    return report_df
