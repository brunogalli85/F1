# OpenF1 API — Resumo

Fonte: <https://openf1.org/docs/>

## Visão geral

- **URL base:** `https://api.openf1.org/v1/{endpoint}`
- **Dados históricos (2023 em diante):** gratuitos e sem autenticação.
- **Dados em tempo real:** exigem assinatura paga (ver <https://openf1.org/auth.html>).
- **Formato:** JSON por padrão; acrescente `csv=true` para receber CSV.
  - Ex.: `/v1/sessions?year=2023&csv=true`
- **Suporte:** GitHub Discussions (dúvidas) e GitHub Issues (bugs).

## Filtros

- Qualquer atributo que não seja array pode ser usado como query param.
- Operadores: `=`, `>`, `<`, `>=`, `<=` (ex.: `speed>=315`).
- Vários valores: repita o parâmetro (`driver_number=4&driver_number=81`).
- `latest` vale para `meeting_key` e `session_key` (sessão ou evento atual/mais recente).
- Datas: `date>=2023-09-01&date<=2023-09-30`. Formatos aceitos como no `dateutil.parser` do Python (`2021-09-10`, `09/10/2021`, `10 September 2021`).
- Valores com espaço precisam de URL encoding (`Sprint%20Qualifying`).

## Campos comuns

| Campo | Significado |
|---|---|
| `meeting_key` | ID do fim de semana (GP ou teste) |
| `session_key` | ID da sessão (treino, quali, sprint, corrida) |
| `driver_number` | Número do carro na temporada |
| `date` | Timestamp UTC (ISO 8601) |

## Hierarquia dos dados

```
meetings (GP) ──► sessions (FP1, Quali, Race...) ──► dados por piloto/tempo
```

Fluxo típico: buscar `meetings`/`sessions` → pegar `session_key` → consultar os demais endpoints.

## Endpoints

### Calendário e participantes

| Endpoint | Descrição | Campos principais |
|---|---|---|
| `meetings` | GPs e testes (atualizado diariamente, 00:00 UTC) | `meeting_name`, `meeting_official_name`, `circuit_key`, `circuit_short_name`, `circuit_type` (`Permanent`, `Temporary - Street`, `Temporary - Road`), `circuit_image`, `circuit_info_url` (JSON detalhado do circuito), `country_name`, `country_code`, `country_flag`, `location`, `date_start`, `date_end`, `gmt_offset`, `is_cancelled`, `year` |
| `sessions` | Sessões de cada meeting (atualizado diariamente) | `session_name` (ex.: `Race`, `Qualifying`), `session_type` (ex.: `Practice`, `Race`), `date_start`, `date_end`, `circuit_short_name`, `country_name`, `is_cancelled`, `year` |
| `drivers` | Pilotos de uma sessão | `full_name`, `first_name`, `last_name`, `broadcast_name`, `name_acronym` (ex.: VER), `team_name`, `team_colour` (hex RRGGBB), `headshot_url`. `country_code` está **deprecated** (sai após 2026) |

### Telemetria (~3,7 Hz)

| Endpoint | Descrição | Campos principais |
|---|---|---|
| `car_data` | Telemetria do carro | `speed` (km/h), `rpm`, `n_gear` (0 = neutro, 1–8), `throttle` (%), `brake` (0 ou 100), `drs` (0/1 desligado, 8 detectado/elegível, 10/12/14 ativo, 2/3/9 desconhecido) |
| `location` | Posição aproximada do carro na pista (origem arbitrária, sem posição lateral) | `x`, `y`, `z` |

### Voltas e estratégia

| Endpoint | Descrição | Campos principais |
|---|---|---|
| `laps` | Dados de cada volta | `lap_number`, `lap_duration`, `duration_sector_1/2/3`, `i1_speed`, `i2_speed`, `st_speed` (speed trap), `is_pit_out_lap`, `date_start`, `segments_sector_1/2/3` (minissetores: 0 indisponível, 2048 amarelo, 2049 verde, 2051 roxo, 2064 pit lane; 2050/2052/2068 desconhecidos; não disponível em corridas) |
| `stints` | Períodos contínuos com o mesmo jogo de pneus | `stint_number`, `compound` (SOFT, MEDIUM, HARD...), `lap_start`, `lap_end`, `tyre_age_at_start` |
| `pit` | Passagens pelo pit lane | `lap_number`, `lane_duration` (tempo no pit lane), `stop_duration` (parado, desde o GP dos EUA 2024). `pit_duration` está **deprecated** |

### Corrida e posições

| Endpoint | Descrição | Campos principais |
|---|---|---|
| `position` | Posição dos pilotos ao longo da sessão | `position` |
| `intervals` | Gaps (só corridas, a cada ~4 s) | `gap_to_leader`, `interval` (para o carro da frente); `+1 LAP` se tomou volta; `null` para o líder |
| `overtakes` | Trocas de posição, incluindo por pit stop e punições (só corridas, pode estar incompleto) | `overtaking_driver_number`, `overtaken_driver_number`, `position` |
| `race_control` | Bandeiras, safety car, incidentes, status da sessão | `category` (`Flag`, `SafetyCar`, `Drs`, `CarEvent`, `SessionStatus`), `flag` (`GREEN`, `YELLOW`, `DOUBLE YELLOW`, `CHEQUERED`...), `message`, `scope` (`Track`, `Driver`, `Sector`), `sector`, `lap_number`, `qualifying_phase` |

### Resultados e campeonato

| Endpoint | Descrição | Campos principais |
|---|---|---|
| `starting_grid` | Grid de largada (sai minutos após o resultado oficial) | `position`, `driver_number`, `lap_duration` (volta de classificação) |
| `session_result` | Resultado final da sessão (sai minutos após o resultado oficial) | `position`, `dnf`, `dns` (só quali e corrida), `dsq`, `number_of_laps`, `duration` (melhor volta em treino/quali, tempo total em corrida) e `gap_to_leader` (`+N LAP(S)` se tomou volta); em quali ambos são arrays com Q1/Q2/Q3 |
| `championship_drivers` *(beta)* | Classificação de pilotos (só sessões de corrida) | `points_start`, `points_current`, `position_start`, `position_current` |
| `championship_teams` *(beta)* | Classificação de construtores (só corridas) | `team_name`, `points_start`, `points_current`, `position_start`, `position_current` |

### Outros

| Endpoint | Descrição | Campos principais |
|---|---|---|
| `weather` | Condições da pista (a cada minuto) | `air_temperature`, `track_temperature` (°C), `humidity` (%), `pressure` (mbar), `rainfall`, `wind_speed` (m/s), `wind_direction` (0–359°) |
| `team_radio` | Rádios piloto–equipe (seleção limitada; cobertura bem menor a partir de 2026) | `recording_url` (MP3) |

## Exemplos de requisição

```text
# Sessões de 2023 na Bélgica (Sprint Qualifying)
https://api.openf1.org/v1/sessions?country_name=Belgium&session_name=Sprint%20Qualifying&year=2023

# Telemetria do carro 55 acima de 315 km/h
https://api.openf1.org/v1/car_data?driver_number=55&session_key=9159&speed>=315

# Volta 8 do carro 63
https://api.openf1.org/v1/laps?session_key=9161&driver_number=63&lap_number=8

# Pódio de uma sessão
https://api.openf1.org/v1/session_result?session_key=7782&position<=3

# Pit stops abaixo de 2,3 s
https://api.openf1.org/v1/pit?session_key=9877&stop_duration<2.3

# Sessão mais recente
https://api.openf1.org/v1/drivers?session_key=latest
```

## Exemplo em Python

```python
import requests

BASE = "https://api.openf1.org/v1"

sessions = requests.get(f"{BASE}/sessions", params={"year": 2024, "session_name": "Race"}).json()
session_key = sessions[-1]["session_key"]

laps = requests.get(f"{BASE}/laps", params={"session_key": session_key, "driver_number": 1}).json()
```

> Para filtros com operadores (`>=`, `<`), monte a query string manualmente, pois `params` do `requests` só gera `=`:
> `requests.get(f"{BASE}/car_data?session_key={session_key}&speed>=315")`
