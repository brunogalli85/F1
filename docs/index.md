# F1

CLI de análises de Fórmula 1 sobre a [OpenF1 API](https://openf1.org/docs/). Responde perguntas como
"qual foi a classificação final?", "quem fez a volta mais rápida?", "qual foi a estratégia de pneus de cada
piloto?" e "quanto tempo durou cada pit stop?".

Para quem: quem quer explorar dados de F1 (2023 em diante) pelo terminal, sem montar consultas HTTP à mão.

## Fluxo de dados

```text
OpenF1 API ──(f1 sync)──► parsing/validação ──► DuckDB (data/f1.duckdb) ──(f1 results, ...)──► terminal
```

1. `f1 sync` baixa meetings, sessões, pilotos, resultados, voltas, stints e pit stops da API.
2. Os registros são validados e convertidos em entidades do domínio; inválidos são contados e descartados.
3. Os dados são gravados no DuckDB com upsert por chave natural: reexecutar o `sync` não duplica nada.
4. Os comandos de análise leem só do DuckDB: são rápidos, funcionam offline e não consomem o limite da API.

## Quickstart

```bash
poetry install
poetry run f1 sync --year 2024 --session-type Race
poetry run f1 sessions --year 2024 --country Qatar
poetry run f1 results --session-key 9655
```

Veja [Uso da CLI](usage.md) para todos os comandos.

## Escopo

Incluído: `meetings`, `sessions`, `drivers`, `session_result`, `laps`, `stints`, `pit`.

Fora do escopo por enquanto: telemetria (`car_data`, `location`), `intervals`, `position`, `weather`,
`race_control` e campeonato.
