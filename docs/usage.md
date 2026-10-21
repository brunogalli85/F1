# Uso da CLI

Todos os comandos rodam com `poetry run f1 <comando>` (ou `f1 <comando>` com o ambiente ativado).
Logs vão para o stderr; as tabelas vão para o stdout. Em caso de erro, a CLI mostra a mensagem e sai
com código 1 (erros de argumento saem com código 2).

## `f1 sync`

Baixa dados da OpenF1 para o cache DuckDB.

```bash
f1 sync --year 2024                        # temporada inteira (todas as sessões)
f1 sync --year 2024 --session-type Race    # só corridas e sprints (session_type = Race)
f1 sync --session-key 9655                 # uma única sessão
```

| Opção | Descrição |
|---|---|
| `--year` | Temporada (2023 em diante). Exclusiva com `--session-key` |
| `--session-key` | Chave de uma sessão |
| `--session-type` | `Practice`, `Qualifying` ou `Race` (apenas com `--year`) |

Regras:

- Sessões canceladas e sessões que ainda não terminaram são puladas (os metadados delas ficam no cache).
- Sessões sem resultado publicado ainda (`session_result` sai minutos após o resultado oficial) não são erro;
  basta rodar o `sync` de novo mais tarde.
- Reexecutar é seguro: as gravações são upserts por chave natural.
- Cada execução fica registrada na tabela `sync_runs` (linhas lidas, gravadas e rejeitadas).
- Se mais de 10% dos registros de um endpoint forem rejeitados, o `sync` falha: provavelmente o formato da
  API mudou.

!!! note "Limite de requisições"
    A API gratuita limita a taxa de requisições. O cliente espera `OPENF1_MIN_INTERVAL_S` entre chamadas e
    repete com backoff exponencial em respostas 429/5xx. Uma temporada inteira de corridas leva alguns
    minutos.

## `f1 sessions`

Lista as sessões do cache, em ordem cronológica, com a chave usada pelos outros comandos.

```bash
f1 sessions --year 2024 --country Belgium
```

## `f1 results`

Classificação final. Em corrida mostra voltas, tempo total do vencedor, gap dos demais, `+N voltas`,
`DNF`/`DNS`/`DSQ` e pontos. Em classificação mostra os tempos de Q1, Q2 e Q3.

```bash
f1 results --session-key 9655
```

## `f1 fastest-laps`

Melhor volta de cada piloto, com gap para a mais rápida e os tempos de setor. Voltas de saída de box e
voltas sem tempo são ignoradas.

```bash
f1 fastest-laps --session-key 9655 --top 10
```

## `f1 strategy`

Stints de cada piloto na ordem de chegada, no formato `COMPOSTO(voltas)`.

```bash
f1 strategy --session-key 9655
```

## `f1 pits`

Passagens pelo pit lane: número de paradas, voltas, parada mais rápida (`stop_duration`, disponível desde o
GP dos EUA 2024) e tempo total no pit lane.

```bash
f1 pits --session-key 9655
```
