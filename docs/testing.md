# Testes

## Executar

```bash
poetry run pytest                                     # suíte + cobertura (gate de 50%)
poetry run pytest -m "not integration and not e2e"    # o que o CI roda
poetry run pytest -m e2e                              # chama a OpenF1 real (precisa de rede)
poetry run pytest tests/unit/domain --no-cov          # execução parcial, sem o gate
poetry run pytest --cov-report=html                   # relatório em htmlcov/
```

A cobertura (linhas + branches) é medida pelo pytest-cov; `fail_under = 50` fica em
`[tool.coverage.report]` no `pyproject.toml`.

## Organização

```text
tests/
├── conftest.py              # fixtures: load_fixture (JSON) e store (DuckDB em memória)
├── fixtures/                # respostas reais da OpenF1 (GP do Catar 2024), recortadas
├── unit/
│   ├── domain/              # parsing e análises: a maior parte dos casos
│   ├── infrastructure/      # cliente HTTP (httpx.MockTransport) e DuckDbStore (:memory:)
│   ├── pipelines/           # sync com cliente falso e DuckDB em memória
│   ├── test_cli.py
│   └── test_config.py
└── e2e/                     # marcados com `e2e`: rede real, fora do CI
```

## Markers

| Marker | Uso |
|---|---|
| `integration` | Dependem de serviços locais. Nenhum teste usa ainda |
| `e2e` | Chamam a OpenF1 real. Rodam só sob demanda |

## Princípios

- Testes unitários não usam rede: o cliente HTTP recebe um `httpx.MockTransport`, e o relógio e o `sleep`
  são injetados, então retry e intervalo mínimo são testados sem esperar.
- O `sync` recebe `now` por parâmetro: as regras de "sessão ainda não terminou" são determinísticas.
- O DuckDB dos testes é `:memory:` (ou um arquivo em `tmp_path` nos testes da CLI).
- As fixtures vêm da API real, no formato original (incluindo campos deprecated e minissetores), para
  garantir que o parsing ignora o que deve ignorar.

## Atualizar fixtures

As fixtures são recortes de respostas reais, por exemplo:

```bash
curl -s "https://api.openf1.org/v1/session_result?session_key=9655"
```

Mantenha-as pequenas (poucos pilotos e voltas) e com os casos-limite que os testes usam: piloto com DNF,
piloto com volta de atraso (`+1 LAP`), volta de saída de box, pit stop sem `stop_duration`.
