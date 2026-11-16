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

## Importar dados locais

Na raiz do projeto:

```powershell
python -m pip install -r backend/requirements.txt
python backend/scripts/import_firms.py --chunk-size 100000
python run.py
```

Coloque CSV, CSV.GZ ou ZIP nas subpastas `backend/data/raw/modis/` e
`backend/data/raw/viirs/`, em qualquer organização de anos/países.
Para começar com dados reais do Brasil de 2020, usando o ambiente já existente:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/import_firms.py --match '*Brazil*.csv' --start-year 2020 --end-year 2020
python run.py
```

Se a base principal estiver ocupada por outra importação, gere uma base separada:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/import_firms.py --match '*Brazil*.csv' --start-year 2020 --end-year 2020 --output backend/data/processed/brazil-2020
$env:FIREWATCH_DATA = (Resolve-Path 'backend/data/processed/brazil-2020').Path
python run.py
```

Depois, amplie até 2025 com o mesmo diretório de saída:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/import_firms.py --match '*Brazil*.csv' --start-year 2020 --end-year 2025
```

O processamento percorre os anos em ordem, nos dois sensores. As saídas são:

```text
backend/data/processed/
  firewatch.sqlite
  modis/2020/brazil/part-001.parquet
  modis/2020/brazil/part-002.parquet
  modis/2020/argentina/part-001.parquet
  modis/2021/brazil/part-001.parquet
  viirs/2020/brazil/part-001.parquet
```

Cada país/ano contém partes numeradas a partir de `part-001`, com até 50 mil
registros por parte. Os CSVs correspondentes são salvos ao lado dos Parquets.
O país é extraído do nome FIRMS, como `modis_2020_Brazil.csv` ou
`viirs-jpss1_2020_Argentina.csv`, inclusive nos CSVs dentro de ZIPs.
Também é reconhecida a pasta de país em `sensor/ano/país/arquivo.csv`.
Os nomes das pastas ficam em minúsculas, sem acentos, com `_` entre palavras;
fontes sem país identificável ficam em `unknown`. Não há classificação geográfica
por coordenadas nesta etapa: use fontes separadas por país.
Fontes do mesmo sensor/ano/país compartilham a sequência de partes, preservando
`source_file`. Ao atualizar uma fonte, a partição é reconstruída e partes antigas
excedentes são removidas. Arquivos temporários são escritos antes da publicação;
uma interrupção durante a substituição é recuperada na próxima execução.

Para importar os arquivos locais e gerar a estrutura acima, execute na raiz do projeto:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/import_firms.py --start-year 2020 --end-year 2025
```

O script mostra o diretório absoluto de saída e o período antes de começar.
As pastas são criadas conforme cada fonte/ano termina; pastas sem dados não são
pré-criadas. O índice `firewatch.sqlite` permanece na raiz de `processed` para os checkpoints da importação.

Para reorganizar uma base já processada sem reler os CSVs brutos:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/import_firms.py --export-only --start-year 2020 --end-year 2025
```

`--export-only` consulta apenas registros já presentes no SQLite; ele não importa
`raw`. Se não houver registros no período solicitado, uma mensagem informa isso.
Esse modo abre a base somente para leitura, sem mudar o journal ou criar tabelas.
Se houver bloqueio, o script orienta a aguardar o outro processo e repetir o comando.

Use `--output` para escolher outra base, como `backend/data/processed/brazil-2020`.
As exportações antigas em `year=2020` são removidas apenas após a publicação das
partes correspondentes no novo padrão. Os checkpoints antigos também são
atualizados automaticamente ao repetir a importação normal.

O frontend consulta os Parquets com DuckDB, sem abrir os CSVs brutos.
O SQLite é usado para staging e checkpoints do importador. Assim que uma
fonte/ano termina e publica suas partes, seus registros ficam disponíveis: atualize a página e selecione
um período/região que tenha dados. A importação pode continuar em outro terminal.
O cache considera caminho, tamanho e mtime de cada parte Parquet publicada.

Se houver interrupção, repita o comando. Fontes/anos já concluídos são ignorados;
a fonte/ano em andamento retoma do último lote confirmado. O leitor ainda precisa
percorrer os lotes anteriores do CSV comprimido, mas não os reinsere. Se mudar
`--chunk-size` durante uma retomada, somente a fonte/ano incompleta reinicia.
Um arquivo com vários anos é lido para cada ano solicitado. Prefira arquivos anuais
para reduzir leitura. O ano no caminho/nome é usado como filtro: mantenha-o coerente
com o conteúdo; arquivos sem ano no caminho são inspecionados para cada ano.

Dados e checkpoints intermediários ficam persistidos no SQLite. Uma fonte/ano alterada
é preparada em staging; a versão anterior permanece disponível até a troca em
transação. Se a exportação falhar depois dessa troca, a próxima execução refaz
somente a publicação pendente. Os arquivos CSV e Parquet são substituídos
individualmente; o checkpoint de exportação é confirmado após ambos.
O importador migra o esquema do índice existente sem apagar os dados anteriores.
Índices antigos sem checkpoints anuais são revalidados na primeira importação.
A tabela legada `sources` registra a última execução por fonte; os checkpoints e
relatórios de cada ano ficam em `ingestion_years`. A tabela legada `daily` não é
atualizada: a interface agrega diretamente as detecções dos Parquets via DuckDB.

A normalização valida coordenadas, datas e horários UTC. Confiança baixa é preservada.
Duplicatas na mesma fonte são ignoradas; fontes sobrepostas mantêm a procedência,
e a interface deduplica por sensor, satélite, data, hora, latitude e longitude.
Arquivos sem mudança de tamanho/data são considerados iguais; se substituir um
arquivo mantendo ambos, altere seu mtime para forçar a atualização.
Fontes removidas de `raw` continuam na base. Para gerar uma base independente,
use `--output` e configure `FIREWATCH_DATA` no frontend. Não execute dois importadores
na mesma base ao mesmo tempo.

Este script processa arquivos locais; não baixa dados da NASA. A retomada evita
reprocessar os anos concluídos, e os arquivos já baixados permanecem em `raw`.
A obtenção automática via API FIRMS não faz parte desta versão.

## Análise com DuckDB e integração com o frontend

`src/firms_analysis.py` abre os Parquets publicados em
`processed/{modis,viirs}/AAAA/país/part-NNN.parquet` como uma view DuckDB em memória.
Nenhum banco DuckDB persistente ou novo processamento de `raw` é necessário.
Arquivos CSV, temporários e diretórios antigos `year=AAAA` são ignorados.
A leitura direta usa a API documentada em [DuckDB: Parquet](https://duckdb.org/docs/stable/data/parquet/overview).

O fluxo de consulta é: Parquets → DuckDB (filtros, deduplicação, agregação diária)
→ harmonização mensal no backend → DataFrames pequenos para o Streamlit.
As detecções são deduplicadas entre partes antes de contar células ocupadas.
Os filtros de país, raio e retângulo são aplicados aos pontos originais;
o nome da pasta de país não substitui a seleção geográfica.
O histórico completo da região alimenta a calibração e a linha de base.
A exportação de detecções seleciona os anos do período e limita a saída a 100 mil linhas.

Na raiz do projeto, para abrir o frontend usando os Parquets já gerados:

```powershell
$env:FIREWATCH_DATA = (Resolve-Path 'backend/data/processed').Path
python run.py
```

`python run.py` instala as dependências declaradas, incluindo DuckDB, se necessário.
Sem configuração, a pasta padrão é `backend/data/processed`.
`FIREWATCH_DATA` tem prioridade sobre a configuração legada `FIREWATCH_DB`.
Se apenas `FIREWATCH_DB` estiver definida, a leitura SQLite anterior continua disponível.
Sem partes Parquet publicadas, a interface informa que usa amostra sintética.
Se houver partes, mas nenhum dado para a região/período, o resultado é vazio;
não há substituição desses resultados por amostra sintética.
Atualize a página após a publicação de novas partes para invalidar o cache.

## Git e publicação sem os arquivos grandes

`data/raw/` e `data/processed/` são ignorados pelo Git.
A amostra pequena em `data/sample/hotspots.csv` é **sintética** e versionada.
Para hospedar com dados reais, transfira as pastas Parquet por armazenamento externo
ou volume persistente, preservando sensor/ano/país, e configure `FIREWATCH_DATA`.
O servidor de análise precisa dos Parquets; o SQLite de checkpoints e os CSVs
brutos podem permanecer apenas na máquina de importação.

## Método e limitações

1. Grade cilíndrica de área equivalente: raio autálico 6371007.181 m,
   paralelo padrão de 30°, células de 1000 × 1000 m.
2. Agregação em células ocupadas por dia UTC e sensor: reduz múltiplos pixels
   e passagens, mas não identifica eventos de incêndio independentes.
3. Para cada região e mês, MODIS é a referência quando há registros.
   Na ausência dele, utiliza-se VIIRS vezes a mediana das razões mensais
   MODIS/VIIRS em pelo menos três meses anteriores ao mês de avaliação.
   Sem sobreposição suficiente, VIIRS fica provisório e a anomalia não é calculada.
4. A série exibe **células-dia equivalentes**, mantendo separada a contagem
   de detecções originais. Não misture as unidades.
5. A média histórica considera o mesmo mês/dias em anos anteriores, exclui
   o ano avaliado e utiliza apenas anos com registros comparáveis.
   Lacunas não são zeros. O pico anual usa apenas o intervalo selecionado.

Sem metadados de cobertura, um mês com poucos registros pode refletir dados
incompletos. O ajuste não corrige nuvens, geometria orbital ou sensibilidade;
não garante continuidade MODIS–VIIRS e exige validação científica antes de uso
operacional. As razões regionais podem esconder variação sazonal e espacial.
Não há dados de ocorrências confirmadas ou relatadas por equipes de campo.

Países usam polígonos simplificados do mapa; cidades e estados usam raio
configurável em torno do ponto de referência, explicitamente indicado na UI.
O retângulo manual define limites geográficos independentes do país.
A seleção espacial é aplicada às coordenadas originais antes de agrupar a grade.

A consulta é local, usa DuckDB sobre Parquet e cache invalidado por caminho/mtime/tamanho.
O histórico da região é agregado uma vez por mudança de região/base; filtros
temporais operam sobre esse agregado. A primeira consulta de áreas globais
ainda pode ser custosa. CSV de detecções tem limite explícito de 100 mil linhas
por download para proteger memória do servidor; o resumo mensal é separado.
As visualizações podem ser exportadas como HTML autossuficiente ou PNG pelo Plotly.

Referências oficiais:
- https://firms.modaps.eosdis.nasa.gov/
- https://firms.modaps.eosdis.nasa.gov/map/
- https://firms.modaps.eosdis.nasa.gov/content/active_fire/

## Verificação

```powershell
python -m unittest discover -s backend/tests
frontend/.venv/Scripts/python.exe -m unittest discover -s frontend/tests
```
