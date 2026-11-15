from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import re

import pandas as pd


REQUIRED_COLUMNS = ["latitude", "longitude", "acq_date", "acq_time"]

# Variações comuns de nomes de colunas. Campos desconhecidos são ignorados.
ALIASES = {
    "lat": "latitude",
    "latitude": "latitude",
    "lon": "longitude",
    "long": "longitude",
    "longitude": "longitude",
    "acq_date": "acq_date",
    "date": "acq_date",
    "acq_time": "acq_time",
    "time": "acq_time",
    "satellite": "satellite",
    "sat": "satellite",
    "instrument": "instrument",
    "confidence": "confidence",
    "conf": "confidence",
    "frp": "frp",
    "daynight": "daynight",
    "day_night": "daynight",
    "scan": "scan",
    "track": "track",
    "bright_ti4": "bright_ti4",
    "bright_ti5": "bright_ti5",
    "brightness": "brightness",
    "bright_t31": "bright_t31",
}


OUTPUT_COLUMNS = [
    "latitude", "longitude", "acq_date", "acq_time",
    "satellite", "instrument", "confidence", "frp",
    "daynight", "scan", "track", "sensor",
    "source_file", "ingested_at_utc",
]


def _normalize_column_name(name: object) -> str:
    value = str(name).strip().lower()
    value = re.sub(r"[^a-z0-9_]", "", value)
    return ALIASES.get(value, value)


def _read_csv_bytes(content: bytes, source_name: str) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(content), encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(BytesIO(content), encoding="latin-1")


def _load_csv_or_zip(path: Path) -> list[tuple[str, pd.DataFrame]]:
    """Lê um CSV, CSV.GZ ou todos os CSVs encontrados dentro de um ZIP."""
    suffix = path.suffix.lower()

    if suffix == ".zip":
        loaded = []
        with ZipFile(path) as archive:
            csv_members = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv") and not name.endswith("/")
            ]
            for member in csv_members:
                loaded.append((
                    f"{path.name}:{member}",
                    _read_csv_bytes(archive.read(member), member)
                ))
        return loaded

    if path.name.lower().endswith(".csv.gz"):
        return [(path.name, pd.read_csv(path, compression="gzip"))]

    if suffix == ".csv":
        return [(path.name, pd.read_csv(path, encoding="utf-8-sig"))]

    return []


def _standardize_frame(
    frame: pd.DataFrame,
    sensor: str,
    source_file: str
) -> tuple[pd.DataFrame, dict]:
    df = frame.copy()
    df.columns = [_normalize_column_name(c) for c in df.columns]

    # Se duas colunas acabarem com o mesmo nome após a normalização,
    # mantém a primeira para evitar ambiguidades silenciosas.
    df = df.loc[:, ~df.columns.duplicated()].copy()

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"{source_file}: faltam colunas obrigatórias: {', '.join(missing)}. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df["scan"] = pd.to_numeric(df["scan"], errors="coerce")
    df["track"] = pd.to_numeric(df["track"], errors="coerce")

    df["acq_date"] = pd.to_datetime(
        df["acq_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    # FIRMS normalmente fornece acq_time como HHMM. Preservamos como texto
    # com quatro dígitos para não perder zeros à esquerda.
    time_values = (
        df["acq_time"].astype("string")
        .str.strip()
        .str.replace(":", "", regex=False)
        .str.replace(r"\.0$", "", regex=True)
    )
    time_values = time_values.where(time_values.str.fullmatch(r"\d{1,4}"))
    df["acq_time"] = time_values.str.zfill(4)

    for col in ["satellite", "instrument", "confidence", "daynight"]:
        df[col] = df[col].astype("string").str.strip()

    df["sensor"] = sensor.upper()
    df["source_file"] = source_file
    df["ingested_at_utc"] = datetime.now(timezone.utc).isoformat()

    before = len(df)

    # Remove apenas registros sem os campos essenciais ou com coordenadas
    # fora dos limites geográficos. Não filtra confidence nesta etapa.
    valid = (
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
        & df["acq_date"].notna()
        & df["acq_time"].notna()
    )
    invalid_count = int((~valid).sum())
    df = df.loc[valid, OUTPUT_COLUMNS].copy()

    report = {
        "source_file": source_file,
        "sensor": sensor.upper(),
        "rows_read": before,
        "rows_valid": len(df),
        "rows_invalid": invalid_count,
    }
    return df, report


def ingest_sensor_folder(folder: Path, sensor: str) -> tuple[pd.DataFrame, list[dict]]:
    files = sorted(
        p for p in folder.rglob("*")
        if p.is_file() and (
            p.suffix.lower() in {".csv", ".zip"}
            or p.name.lower().endswith(".csv.gz")
        )
    )

    frames = []
    reports = []

    for path in files:
        for source_name, raw_df in _load_csv_or_zip(path):
            standardized, report = _standardize_frame(
                raw_df, sensor=sensor, source_file=source_name
            )
            frames.append(standardized)
            reports.append(report)

    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS), reports

    return pd.concat(frames, ignore_index=True), reports


def build_record_key(df: pd.DataFrame) -> pd.Series:
    """Chave operacional para evitar reimportar a mesma detecção."""
    key_columns = [
        "sensor", "satellite", "instrument",
        "acq_date", "acq_time", "latitude", "longitude"
    ]
    values = df[key_columns].astype("string").fillna("")
    return pd.util.hash_pandas_object(values, index=False).astype("string")


def ingest_all(
    raw_root: Path,
    output_dir: Path,
    deduplicate: bool = True
) -> pd.DataFrame:
    modis, modis_reports = ingest_sensor_folder(raw_root / "modis", "MODIS")
    viirs, viirs_reports = ingest_sensor_folder(raw_root / "viirs", "VIIRS")

    frames = [df for df in [modis, viirs] if not df.empty]
    if not frames:
        raise RuntimeError(
            "Nenhum CSV foi encontrado. Coloque os arquivos em "
            "data/raw/modis/ ou data/raw/viirs/."
        )

    combined = pd.concat(frames, ignore_index=True)
    total_before_dedup = len(combined)

    if deduplicate:
        combined["_record_key"] = build_record_key(combined)
        combined = combined.drop_duplicates(
            subset=["_record_key"], keep="last"
        ).drop(columns=["_record_key"])

    combined = combined.sort_values(
        ["acq_date", "acq_time", "sensor"],
        kind="stable"
    ).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "hotspots_normalized.csv"
    parquet_path = output_dir / "hotspots_normalized.parquet"

    combined.to_csv(csv_path, index=False, encoding="utf-8")
    try:
        combined.to_parquet(parquet_path, index=False)
    except ImportError as exc:
        raise RuntimeError(
            "Para gerar Parquet, instale pyarrow: pip install pyarrow"
        ) from exc

    print("\n=== Relatório de ingestão ===")
    for report in modis_reports + viirs_reports:
        print(
            f"{report['sensor']} | {report['source_file']} | "
            f"lidas: {report['rows_read']} | válidas: {report['rows_valid']} | "
            f"inválidas: {report['rows_invalid']}"
        )

    print(f"\nRegistros antes da deduplicação: {total_before_dedup}")
    print(f"Registros finais: {len(combined)}")
    print(f"CSV: {csv_path}")
    print(f"Parquet: {parquet_path}")

    return combined
