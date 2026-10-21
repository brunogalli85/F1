# Análises de Fórmula 1: pipeline de dados com Python e DuckDB

CLI que coleta dados da [OpenF1 API](https://openf1.org/docs/) (temporadas de 2023 em diante, gratuitas e sem autenticação), armazena em um banco local DuckDB e gera análises de corrida direto no terminal, sem depender da rede depois da sincronização.

## O que o projeto demonstra

- **Ingestão de dados** de API REST com `httpx`
- **Modelagem e parsing** em entidades tipadas (`dataclasses`), com datas normalizadas em UTC
- **Armazenamento analítico** em DuckDB, usado como cache local
- **Arquitetura em camadas**: domínio, infraestrutura e pipelines separados
- **Testes automatizados** unitários e ponta a ponta com pytest, com cobertura via pytest-cov
- **Integração contínua** com GitHub Actions: lint, formatação, testes com gate de cobertura e build da documentação
- **Qualidade de código** com Ruff e pre-commit
- **Documentação** com MkDocs Material

## Fluxo de dados

```
OpenF1 API → httpx → parsing (dataclasses) → DuckDB → análises → CLI
```

## Análises disponíveis

| Comando        | O que mostra                          |
| -------------- | ------------------------------------- |
| `sessions`     | Sessões sincronizadas e suas chaves   |
| `results`      | Classificação final                   |
| `fastest-laps` | Voltas mais rápidas, com setores      |
| `strategy`     | Estratégia de pneus (stints e compostos) |
| `pits`         | Resumo de pit stops por piloto        |

## Como rodar

Pré-requisitos: Python 3.12 e Poetry 2.x.

```bash
poetry env use 3.12
poetry install

poetry run f1 sync --year 2024 --session-type Race   # baixa as corridas de 2024
poetry run f1 sessions --year 2024                   # lista as sessões e suas chaves
poetry run f1 results --session-key 9655             # classificação final
poetry run f1 fastest-laps --session-key 9655 --top 5
poetry run f1 strategy --session-key 9655            # stints e compostos
poetry run f1 pits --session-key 9655                # pit stops
```

## Testes

```bash
poetry run pytest -m "not integration and not e2e"   # unitários, como no CI
poetry run pytest -m e2e                             # chama a OpenF1 API real
```

## Documentação

Uso, arquitetura, desenvolvimento e testes estão em `docs/`:

```bash
poetry run task docs
```

## Sobre o autor

Sou engenheiro mecatrônico, com mais de 10 anos em manutenção industrial. Na indústria, calculava todo mês 12 indicadores à mão, a partir de dados presos no SAP. Isso me levou à engenharia de dados: quero construir pipelines que automatizem a análise na operação.

[LinkedIn](https://www.linkedin.com/in/bruno-galli-engenharia)
