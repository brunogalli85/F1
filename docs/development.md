# Desenvolvimento

## Pré-requisitos

- Python 3.12 (o repositório tem `.python-version` para o pyenv)
- Poetry 2.x, instalado fora do projeto (ex.: `pipx install poetry`)

## Setup do zero

```bash
git clone <url-do-repositório> f1 && cd f1
poetry config virtualenvs.in-project true   # ambiente em .venv/
poetry env use 3.12
poetry env info --path                      # precisa apontar para <repo>/.venv
poetry install
poetry run pre-commit install
```

!!! warning "`VIRTUAL_ENV` herdado"
    Se `poetry env info --path` apontar para fora do projeto (por exemplo, para o Python global do pyenv),
    a variável `VIRTUAL_ENV` está definida no shell. Remova-a (`unset VIRTUAL_ENV` no bash,
    `Remove-Item Env:VIRTUAL_ENV` no PowerShell) e rode os comandos de novo.

Dependências entram sempre pelo Poetry:

```bash
poetry add <pacote>                 # runtime
poetry add --group dev <pacote>     # ferramentas
poetry add --group docs <pacote>    # documentação
```

## Variáveis de ambiente

Todas são opcionais. Veja `.env.example`.

| Variável | Padrão | Uso |
|---|---|---|
| `OPENF1_BASE_URL` | `https://api.openf1.org/v1` | URL base da API |
| `F1_DB_PATH` | `data/f1.duckdb` | Arquivo DuckDB (`data/` está no `.gitignore`) |
| `HTTP_TIMEOUT_S` | `30` | Timeout das requisições, em segundos (> 0) |
| `OPENF1_MIN_INTERVAL_S` | `0.5` | Intervalo mínimo entre requisições, em segundos (>= 0) |

Valor inválido faz a CLI falhar na hora, com o nome da variável na mensagem.

## Executar

```bash
poetry run f1 --help
poetry run python -m f1 --help      # equivalente
```

## Workflow

```bash
poetry run ruff check --select I --fix .
poetry run ruff check --fix .       # revise o diff
poetry run ruff format .
poetry run pytest
poetry run task docs-build
```

Validação equivalente ao CI (`.github/workflows/ci.yml`):

```bash
poetry check --lock
poetry run ruff check .
poetry run ruff format --check .
poetry run pytest -m "not integration and not e2e"
poetry run task docs-build
```

O pre-commit roda `ruff check --fix`, `ruff format` e `poetry check --lock` com as versões do `poetry.lock`.
