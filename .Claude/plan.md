# plan.md — Projeto F1 (CLI de análises sobre a OpenF1)

## Contexto

O repositório tem só o esqueleto gerado pelo `poetry new`: `pyproject.toml` mínimo, `src/f1/__init__.py`,
`tests/__init__.py` e `.python-version` (3.12.10). O objetivo é uma **CLI de análises de Fórmula 1**
sobre a [OpenF1 API](doc_api.md) (dados históricos de 2023 em diante, gratuitos e sem autenticação), seguindo
o padrão do time em [skill.md](skill.md).

Decisões tomadas:

- **Produto:** CLI (`f1 ...`) que responde perguntas analíticas (resultados, voltas mais rápidas, estratégia de pneus, pit stops).
- **Armazenamento:** cache local em **DuckDB**. A CLI sincroniza dados da API para o banco e as análises leem do banco (rápido, offline, sem estourar o limite de requisições da API).
- **Escopo do MVP:** `meetings`, `sessions`, `drivers`, `session_result`, `laps`, `stints`, `pit`. Telemetria (`car_data`, `location`), `intervals`, `position`, `weather`, `race_control` e campeonato ficam fora.

## Stack e dependências

| Grupo | Pacote | Justificativa |
|---|---|---|
| runtime | `httpx` | Cliente HTTP com timeout explícito, cliente reutilizável e `MockTransport` para testes sem rede |
| runtime | `duckdb` | Banco embarcado em arquivo único, `INSERT ... ON CONFLICT` para cargas idempotentes, SQL para análises |
| dev | `ruff`, `pytest`, `pytest-cov`, `pre-commit` | Padrão obrigatório (skill.md §2.1) |
| docs | `mkdocs>=1.6,<2`, `mkdocs-material` | Padrão obrigatório (skill.md §7) |

Sem dependências extras: CLI com `argparse` (stdlib), modelos com `dataclasses`, tabelas no terminal formatadas
à mão, stubs HTTP com `httpx.MockTransport` (dispensa `respx`). `mkdocstrings` fica fora (não há API pública
consumida por terceiros).

## Arquitetura

```text
src/f1/
├── __init__.py
├── __main__.py                  # entrypoint: configura logging, chama cli.main, trata erros (exit code)
├── cli.py                       # argparse: subcomandos e formatação da saída no terminal
├── config.py                    # Settings (dataclass frozen) + from_env()
├── domain/
│   ├── models.py                # dataclasses: Meeting, Session, Driver, SessionResult, Lap, Stint, PitStop
│   ├── parsing.py               # dict da API -> dataclass; valida campos obrigatórios, conta rejeitados
│   └── analysis.py              # funções puras: fastest_laps, tyre_strategy, pit_summary, classification
├── infrastructure/
│   ├── openf1_client.py         # OpenF1Client (httpx): GET /v1/{endpoint}, timeout, retry 429/5xx, throttle
│   └── duckdb_store.py          # DuckDbStore: cria schema, upsert por chave natural, consultas de leitura
└── pipelines/
    └── sync.py                  # sync_year / sync_session: client -> parsing -> store (uma transação por sessão)
```

Direção de dependências (skill.md §3.3): `cli/pipelines → infrastructure → domain`; `domain` não importa
nada de fora. `application/` e `utils/` não são criados (sem necessidade concreta ainda).

### Configuração (`.env.example`)

| Variável | Padrão | Uso |
|---|---|---|
| `OPENF1_BASE_URL` | `https://api.openf1.org/v1` | URL base da API |
| `F1_DB_PATH` | `data/f1.duckdb` | Arquivo DuckDB (`data/` no `.gitignore`) |
| `HTTP_TIMEOUT_S` | `30` | Timeout das requisições |
| `OPENF1_MIN_INTERVAL_S` | `0.5` | Intervalo mínimo entre requisições (respeitar limites da API gratuita) |

### Esquema DuckDB (chaves naturais → idempotência)

| Tabela | Chave primária | Observação |
|---|---|---|
| `meetings` | `meeting_key` | |
| `sessions` | `session_key` | FK lógica `meeting_key` |
| `drivers` | `session_key, driver_number` | ignorar `country_code` (deprecated) |
| `session_results` | `session_key, driver_number` | em quali `duration`/`gap_to_leader` são arrays Q1–Q3 → colunas `q1/q2/q3` |
| `laps` | `session_key, driver_number, lap_number` | não gravar `segments_sector_*` no MVP |
| `stints` | `session_key, driver_number, stint_number` | |
| `pit_stops` | `session_key, driver_number, lap_number` | usar `lane_duration`/`stop_duration`; ignorar `pit_duration` (deprecated) |

Carga com `INSERT ... ON CONFLICT DO UPDATE`; reexecutar `sync` não duplica linhas. Tabela `sync_runs`
(`run_id`, início, fim, linhas lidas/gravadas/rejeitadas) para observabilidade (skill.md §11.2).

### Comandos da CLI (`[project.scripts] f1 = "f1.__main__:main"`)

```text
f1 sync --year 2024 [--session-type Race] [--session-key 9158]   # baixa da API para o DuckDB
f1 sessions --year 2024 [--country Belgium]                      # lista sessões sincronizadas
f1 results --session-key 9158                                    # classificação final
f1 fastest-laps --session-key 9158 [--top 10]                    # melhores voltas por piloto
f1 strategy --session-key 9158                                   # stints/compostos por piloto
f1 pits --session-key 9158                                       # pit stops e tempos
```

### Pontos de atenção da API

- Filtros com operadores (`>=`, `<`) não saem de `params` do httpx: o client monta a query string desses filtros explicitamente.
- `sync` pula sessões com `is_cancelled = true` e sessões ainda não terminadas (`date_end` comparado a um `now` **injetado**, para testes determinísticos).
- `session_result`/`starting_grid` só existem minutos após o resultado oficial; resposta vazia não é erro.
- Retry apenas para timeout, 429 e 5xx, com backoff exponencial + jitter e máximo de tentativas; 4xx falha direto.

## Etapas (um PR por etapa)

### 0. Fundação do projeto
- `unset VIRTUAL_ENV`, `poetry config virtualenvs.in-project true`, `poetry env use 3.12`, conferir `poetry env info --path`.
- `pyproject.toml` conforme skill.md §8: `requires-python = ">=3.12,<4.0"`, `requires-poetry = ">=2.0,<3.0"`, Ruff (`target-version = "py312"`, `known-first-party = ["f1"]`), pytest (`--cov=f1`, `--import-mode=importlib`, markers `integration`/`e2e`), coverage (`branch = true`, `fail_under = 50`).
- Dependências só via `poetry add` / `poetry add --group dev|docs`.
- Criar `README.md` (já referenciado no `pyproject.toml` e ausente), `.gitignore` (skill.md §8 + `data/`), `.env.example`, `.pre-commit-config.yaml` (§10.1), `.github/workflows/ci.yml` (§10.2), `mkdocs.yml` + `docs/index.md`.
- Remover `tests/__init__.py` (desnecessário com `importlib`); versionar `poetry.lock`.

### 1. Config + cliente OpenF1
- `config.py` com `Settings.from_env()` e falha clara para valor inválido.
- `infrastructure/openf1_client.py`: `get(endpoint, filters) -> list[dict]`, context manager, timeout, retry, throttle.
- Testes com `httpx.MockTransport`: query string com operadores, retry em 429/5xx, sem retry em 404, resposta vazia.

### 2. Modelos e parsing (domínio)
- `domain/models.py` e `domain/parsing.py` para os 7 endpoints, incluindo arrays Q1–Q3 da quali e `+1 LAP` em `gap_to_leader`.
- Registros sem campos obrigatórios são contados como rejeitados (não derrubam o lote).
- Fixtures JSON pequenas em `tests/fixtures/` com formato real da API.

### 3. DuckDB store + sync
- `infrastructure/duckdb_store.py`: schema, upserts, leituras; testes com DuckDB em memória (`:memory:`).
- `pipelines/sync.py`: `sync_year(year, session_type, now)` e `sync_session(session_key)`; teste do pipeline com client fake e store em memória, incluindo reexecução sem duplicar.

### 4. Análises + CLI
- `domain/analysis.py`: funções puras (voltas mais rápidas, estratégia, resumo de pit, classificação), cobrindo positivo, negativo e limites (sessão sem voltas, piloto com DNF, volta de saída de box).
- `cli.py` + `__main__.py`: subcomandos acima; logging configurado só no entrypoint; `print` apenas para saída ao usuário; erro → mensagem + exit code ≠ 0.

### 5. Documentação
- `docs/architecture.md`, `docs/development.md` (setup do zero, variáveis), `docs/testing.md`, `docs/usage.md` (comandos da CLI).

## Verificação

Ao fim de cada etapa (equivalente ao CI):

```bash
poetry check --lock
poetry run ruff check .
poetry run ruff format --check .
poetry run pytest -m "not integration and not e2e"   # gate de 50% de cobertura
poetry run mkdocs build --strict
```

Teste ponta a ponta manual (rede real, ao fim da etapa 4):

```bash
poetry run f1 sync --year 2024 --session-type Race
poetry run f1 sessions --year 2024
poetry run f1 results --session-key <session_key de uma corrida>
poetry run f1 fastest-laps --session-key <...> --top 5
poetry run f1 sync --year 2024 --session-type Race   # reexecução: contagens das tabelas não mudam
```

Opcional: teste marcado `e2e` que chama a API real para uma sessão conhecida, fora do job padrão do CI.
