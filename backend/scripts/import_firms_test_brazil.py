#Rules
# ANOS = range(2020, 2026)
# PAIS = "Brazil"
# SENSORES = ["modis", "viirs"]
# =======================================================================================

from pathlib import Path


def localizar_arquivos(raw_root: Path):
    arquivos = []

    anos = range(2020, 2026)
    sensores = ["modis", "viirs"]

    for sensor in sensores:
        for ano in anos:

            pasta_ano = raw_root / sensor / str(ano)

            if not pasta_ano.exists():
                print(f"Pasta não encontrada: {pasta_ano}")
                continue

            csvs = pasta_ano.glob(
                f"{sensor}_{ano}_Brazil.csv"
            )

            arquivos.extend(csvs)

    return arquivos