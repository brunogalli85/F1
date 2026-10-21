# Arquitetura

## Camadas

```text
src/f1/
├── __main__.py                  # entrypoint: logging, chama cli.main, converte erros em exit code
├── cli.py                       # argparse e formatação das tabelas no terminal
├── config.py                    # Settings (dataclass frozen) + from_env()
├── domain/
│   ├── models.py                # dataclasses: Meeting, Session, Driver, SessionResult, Lap, Stint, PitStop, SyncRun
│   ├── parsing.py               # dict da API -> dataclass; valida campos, conta rejeitados
│   └── analysis.py              # funções puras: classification, fastest_laps, tyre_strategy, pit_summary
├── infrastructure/
│   ├── openf1_client.py         # OpenF1Client (httpx): timeout, retry, intervalo mínimo
│   └── duckdb_store.py          # DuckDbStore: schema, upsert por chave natural, leituras
└── pipelines/
    └── sync.py                  # sync_year / sync_session: client -> parsing -> store
```

Direção das dependências:

```text
cli / __main__ ──► pipelines ──► infrastructure ──► domain
       │                                              ▲
       └──────────────────────────────────────────────┘
config ◄── (usado por cli)
```

`domain` não importa nada de fora dele. Não há `application/` nem `utils/`: ainda não existe um caso de uso
compartilhado por mais de um entrypoint, nem utilidade técnica usada por duas camadas.

## Fluxo do `sync`

1. `meetings?year=Y` e `sessions?year=Y[&session_type=T]` são baixados, validados e gravados.
2. Para cada sessão encerrada e não cancelada (comparando `date_end` com um `now` injetado):
    1. busca `drivers`, `session_result`, `laps`, `stints` e `pit` filtrando por `session_key`;
    2. converte cada lote com `parse_many` (rejeitados são contados e logados);
    3. grava os cinco lotes em **uma transação**: ou a sessão entra inteira, ou não entra.
3. Grava um registro em `sync_runs` com volumes e duração.

## Esquema DuckDB

| Tabela | Chave primária | Observação |
|---|---|---|
| `meetings` | `meeting_key` | |
| `sessions` | `session_key` | `meeting_key` como FK lógica |
| `drivers` | `session_key, driver_number` | `country_code` (deprecated) não é gravado |
| `session_results` | `session_key, driver_number` | quali: `q1/q2/q3`; corrida: `gap_to_leader` ou `laps_behind` |
| `laps` | `session_key, driver_number, lap_number` | `segments_sector_*` não são gravados |
| `stints` | `session_key, driver_number, stint_number` | |
| `pit_stops` | `session_key, driver_number, lap_number` | `lane_duration`/`stop_duration`; `pit_duration` (deprecated) ignorado |
| `sync_runs` | `run_id` | observabilidade de cada execução |

Datas são gravadas como `TIMESTAMP` em UTC e voltam como `datetime` com fuso UTC.

## Decisões

**DuckDB como cache local.** Banco embarcado em um arquivo, sem servidor, com SQL e `INSERT ... ON CONFLICT`
para cargas idempotentes. As análises ficam offline e não gastam o limite de requisições da API.

**Carga em lote via JSON.** O `upsert` envia o lote inteiro como um único parâmetro JSON e o DuckDB converte
com `from_json`, usando os tipos lidos do próprio schema. Medido neste projeto: 1.200 voltas levavam ~5 s
com parâmetros posicionais (`VALUES`, `executemany` ou listas por coluna) e ~0,1 s com JSON. Os valores
continuam parametrizados; só nomes de tabela e coluna (constantes do código) entram no SQL.

**404 "No results found." é lista vazia.** A OpenF1 responde 404 com `{"detail": "No results found."}` quando
o filtro não encontra registros. O cliente trata esse caso como lista vazia; qualquer outro 404 é erro.

**Filtros com operadores.** `params` do httpx só gera `=`; o cliente monta a query string com
`build_query`, aceitando chaves como `"date_start>="` ou `"position<"`.

**Retry só para erros transitórios.** Timeout, 429 e 5xx são repetidos com backoff exponencial e jitter
(respeitando `Retry-After`), até 5 tentativas. Erros 4xx falham na hora.

**Limite de rejeição.** Mais de 10% de registros inválidos em um endpoint aborta o `sync`, porque indica
mudança de contrato da API, e não dado sujo pontual.

**Sem dependências extras.** CLI com `argparse`, modelos com `dataclasses`, tabelas formatadas à mão, stubs
HTTP com `httpx.MockTransport`.
