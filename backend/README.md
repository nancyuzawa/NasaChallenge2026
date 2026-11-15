| Directory | Responsibility |
| --- | --- |
| `api/routes` | Receive requests from the frontend |
| `services` | Run processing and business rules |
| `models` | Represent system entities and, eventually, database tables |
| `schemas` | Define API request and response formats |
| `database` | Manage connections and persistence |
| `core` | Configuration and environment variables |
| `data/raw` | Original files |
| `data/processed` | Standardized and harmonized data |
| `data/aggregated` | Consolidated data for analysis |

Este projeto é um primeiro passo do backend: lê arquivos CSV, CSV.GZ ou ZIP
baixados do FIRMS, padroniza campos essenciais e gera uma base consolidada.

## Estrutura

```text
fire_firms_ingestion/
├── data/
│   ├── raw/
│   │   ├── modis/
│   │   └── viirs/
│   └── processed/
├── scripts/
│   └── import_firms.py
├── src/
│   └── firms_ingestion.py
└── requirements.txt
```

## 1. Preparar ambiente

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Colocar os arquivos

- Arquivos MODIS em `data/raw/modis/`
- Arquivos VIIRS em `data/raw/viirs/`

Pode colocar CSVs individuais ou ZIPs que contenham CSVs. O script também aceita
arquivos `.csv.gz`.

Importante: a pasta define o sensor. Confira se cada arquivo foi colocado na
pasta correta.

## 3. Executar

Na raiz do projeto:

```bash
python scripts/import_firms.py
```

Para escolher outras pastas:

```bash
python scripts/import_firms.py --raw "data/raw" --output "data/processed"
```

## 4. Saídas

- `data/processed/hotspots_normalized.csv`
- `data/processed/hotspots_normalized.parquet`

O relatório no terminal mostra quantas linhas foram lidas, quantas foram
consideradas válidas e quantas foram descartadas por falta de campos essenciais
ou coordenadas inválidas.

## Cuidados importantes

1. O script não faz calibração científica entre MODIS e VIIRS.
2. O script não remove confiança baixa: preserva o valor original para que a
   regra de qualidade seja definida e documentada em uma etapa posterior.
3. A deduplicação é operacional e usa sensor, satélite, instrumento, data,
   horário e coordenadas. Ela ajuda a evitar reimportação idêntica, mas deve ser
   validada com os produtos reais antes de ser usada como regra definitiva.
4. O script não substitui os arquivos originais; mantenha os ZIPs/CSVs em `raw`.
5. Se o arquivo tiver colunas diferentes das esperadas, o script apresentará
   um erro com os nomes das colunas encontradas. Nesse caso, adapte o mapa
   `ALIASES` em `src/firms_ingestion.py`.
