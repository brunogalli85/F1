---
name: python-data-engineering-standards
description: Padrão oficial de engenharia do time de Dados para projetos Python — Poetry 2.x (sem pip), src layout, Ruff, pytest + pytest-cov (cobertura mínima de 50%), MkDocs Material, CI e segurança. Use ao criar, implementar, revisar, testar, documentar ou evoluir qualquer projeto Python do time.
---

# Padrões de Engenharia Python para Data Engineering

Este documento é o **padrão oficial de engenharia** do time de Engenharia de Dados para projetos Python. Ele vale para assistentes de IA e para desenvolvedores, em todas as fases do projeto: criação da estrutura, implementação, revisão, testes, documentação, manutenção e evolução.

**Como ler as regras:**

| Marcador | Significado |
|---|---|
| **[OBRIGATÓRIO]** | Precisa ser cumprido. Um desvio só é aceito se for justificado e registrado (ADR, PR ou `docs/architecture.md`). |
| **[RECOMENDADO]** | É o padrão esperado. Pode ser dispensado quando o contexto justificar; nesse caso, explique o motivo no PR. |
| **[AVALIAR]** | Depende do contexto. Adote apenas quando o benefício for concreto. |

A stack foi validada em Poetry 2.5, Ruff 0.17, pytest 9, pytest-cov 7, pre-commit 4, MkDocs 1.6 e Material for MkDocs 9.7. As regras de compatibilidade de versões estão na seção 2.3.

---

## Sumário

1. [Princípios](#1-principios)
2. [Stack e ambiente](#2-stack-e-ambiente)
3. [Arquitetura e estrutura do projeto](#3-arquitetura-e-estrutura-do-projeto)
4. [Padrões de código Python](#4-padroes-de-codigo-python)
5. [Ruff: lint, formatação e imports](#5-ruff-lint-formatacao-e-imports)
6. [Testes com pytest](#6-testes-com-pytest)
7. [Documentação com MkDocs Material](#7-documentacao-com-mkdocs-material)
8. [pyproject.toml de referência](#8-pyprojecttoml-de-referencia)
9. [Workflow de desenvolvimento](#9-workflow-de-desenvolvimento)
10. [Automação e qualidade contínua](#10-automacao-e-qualidade-continua)
11. [Segurança, robustez e produção](#11-seguranca-robustez-e-producao)
12. [Como a IA deve aplicar este skill](#12-como-a-ia-deve-aplicar-este-skill)
13. [Apêndice A: checklist de conformidade do projeto](#apendice-a-checklist-de-conformidade-do-projeto)
14. [Apêndice B: comandos de referência](#apendice-b-comandos-de-referencia)
15. [Apêndice C: checklist de revisão de pull request](#apendice-c-checklist-de-revisao-de-pull-request)

---

## 1. Princípios

1. **Simplicidade antes de abstração.** Escreva a solução mais simples que resolve o problema atual. Abstrações só entram quando houver uma segunda implementação real ou uma necessidade concreta de teste.
2. **Responsabilidades explícitas.** Regra de negócio, acesso a dados, configuração e orquestração ficam em lugares diferentes.
3. **Reprodutibilidade.** Qualquer pessoa reproduz o ambiente com `poetry install` a partir de `pyproject.toml` + `poetry.lock`.
4. **Qualidade verificável.** Lint, formatação, testes, cobertura e documentação são verificados por comandos, não por promessa.
5. **Evidência acima de afirmação.** Nada é declarado como "testado" ou "passando" sem que o comando tenha sido executado e a saída observada.

---

## 2. Stack e ambiente

### 2.1 Ferramentas obrigatórias

| Ferramenta | Papel | Grupo de dependência |
|---|---|---|
| Python (≥ 3.12 por padrão) | Linguagem | `requires-python` |
| Poetry 2.x | Dependências, ambiente virtual, execução de comandos, build | Instalado fora do projeto |
| src layout | Organização do código em `src/<pacote>/` | — |
| Ruff | Lint, formatação e ordenação de imports | `dev` |
| pytest | Testes | `dev` |
| pytest-cov | Cobertura (com gate de 50%) | `dev` |
| MkDocs + Material for MkDocs | Documentação técnica | `docs` |
| pre-commit | Hooks locais | `dev` (recomendado) |
| mkdocstrings[python] | Referência de API gerada a partir de docstrings | `docs` ([AVALIAR]) |

### 2.2 Regra inegociável: nunca usar pip diretamente

**[OBRIGATÓRIO]** Todo o gerenciamento de dependências e de ambientes é feito pelo Poetry. Os comandos abaixo são **proibidos** em instruções, scripts, Dockerfiles, CI e documentação do projeto:

- `pip install ...`, `pip uninstall ...`, `pip freeze`
- `python -m pip install ...`
- `poetry run pip install ...`, que contorna o lock file e também é proibido

Use o equivalente no Poetry:

| Necessidade | Comando Poetry |
|---|---|
| Adicionar dependência de runtime | `poetry add <pacote>` |
| Adicionar dependência de desenvolvimento | `poetry add --group dev <pacote>` |
| Adicionar dependência de documentação | `poetry add --group docs <pacote>` |
| Remover dependência | `poetry remove <pacote>` (ou `poetry remove --group dev <pacote>`) |
| Instalar o ambiente a partir do lock | `poetry install` |
| Sincronizar o ambiente com o lock (remove pacotes que sobraram) | `poetry sync` |
| Instalar só o runtime (produção) | `poetry install --only main` |
| Executar uma ferramenta no ambiente | `poetry run <comando>` |
| Ver informações do ambiente | `poetry env info` |
| Ativar o ambiente no shell | `poetry env activate` (imprime o comando de ativação) |
| Escolher o interpretador | `poetry env use 3.12` |
| Atualizar o lock sem atualizar versões | `poetry lock` |
| Atualizar dependências dentro das restrições | `poetry update [<pacote>]` |
| Validar `pyproject.toml` e o lock | `poetry check --lock` |
| Listar dependências desatualizadas | `poetry show --outdated` |
| Listar dependências diretas | `poetry show --top-level` |

**[OBRIGATÓRIO] Não misture sintaxes do Poetry 1.x e 2.x.** No Poetry 2.x:

| Poetry 1.x (não usar) | Poetry 2.x (usar) |
|---|---|
| `poetry shell` | `poetry env activate` (o `shell` virou plugin externo) |
| `poetry lock --no-update` | `poetry lock` (que já não atualiza por padrão) |
| `poetry lock --check` | `poetry check --lock` |
| `poetry install --sync` | `poetry sync` (`--sync` está depreciado) |
| `[tool.poetry.dependencies]` para runtime | `[project].dependencies` (PEP 621) |
| `poetry export` embutido | Plugin `poetry-plugin-export`, somente se for necessário |

Antes de recomendar um comando, confira a versão com `poetry --version` e respeite o campo `requires-poetry` do projeto.

**[OBRIGATÓRIO]** Não crie ambientes paralelos (`python -m venv`, conda, virtualenv manual) sem uma justificativa arquitetural explícita. Ferramentas auxiliares rodam no ambiente do Poetry, via `poetry run`.

**[OBRIGATÓRIO] Cuidado com `VIRTUAL_ENV` herdado.** Se a variável `VIRTUAL_ENV` estiver definida no shell (por configuração da IDE ou do perfil, por exemplo), o Poetry usa esse interpretador em vez de criar o ambiente do projeto. Isso pode instalar pacotes no Python global. Antes do primeiro `poetry install`, confira com `poetry env info --path`. Se o caminho apontar para fora do projeto ou do cache de virtualenvs do Poetry, remova `VIRTUAL_ENV` do shell e rode de novo.

**[RECOMENDADO]** Para manter o ambiente dentro do projeto, use `poetry config virtualenvs.in-project true`, que cria o ambiente em `.venv/`. Esse diretório precisa estar no `.gitignore`.

### 2.3 Versões e compatibilidade

- **[OBRIGATÓRIO]** Versione o `poetry.lock` em aplicações, pipelines e qualquer projeto executável. Em bibliotecas publicadas, versionar o lock continua recomendado para a reprodutibilidade do ambiente de desenvolvimento.
- **[OBRIGATÓRIO]** Declare `requires-python` (ex.: `">=3.12,<4.0"`) e mantenha coerentes:
  - `requires-python` (limite inferior) = `tool.ruff.target-version` (ex.: `py312`) = versão mínima testada no CI.
- **[OBRIGATÓRIO]** Declare `requires-poetry = ">=2.0,<3.0"` em `[tool.poetry]`, para que versões incompatíveis do Poetry falhem logo.
- **[RECOMENDADO]** Fixe o interpretador local com `poetry env use 3.12` (ou um `.python-version` com pyenv). Sem isso, o Poetry pode escolher o Python mais novo disponível que satisfaça `requires-python`, que não necessariamente é a versão mínima testada.
- **[RECOMENDADO]** Não fixe versões exatas (`==`) no `pyproject.toml`. Use as restrições que o `poetry add` gera (ex.: `>=0.17.1,<0.18.0`). Quem garante a reprodutibilidade é o lock file.
- **[OBRIGATÓRIO]** Limite o MkDocs a `<2`: `poetry add --group docs "mkdocs>=1.6,<2"`. A equipe do Material for MkDocs avisa que o MkDocs 2.0 remove o sistema de plugins e de temas, o que quebraria `mkdocstrings` e o próprio tema. Acompanhe os anúncios do Material antes de mudar essa restrição.
- **[RECOMENDADO]** O Ruff muda regras e formatação entre versões *minor* (0.x). Por isso, a restrição `<0.(x+1)` gerada pelo Poetry é desejável. Atualize o Ruff em um PR dedicado: `poetry update ruff`, depois `ruff format .`, depois `ruff check .`.

### 2.4 Grupos de dependência

O Poetry 2.2+ grava grupos com `poetry add --group <nome>` na tabela padrão **PEP 735** `[dependency-groups]`. Projetos mais antigos podem usar `[tool.poetry.group.<nome>.dependencies]`.

- **[OBRIGATÓRIO]** Respeite o formato que o projeto já usa e não duplique o mesmo grupo nas duas tabelas.
- **[OBRIGATÓRIO]** Dependência de runtime fica em `[project].dependencies`. Ferramentas (Ruff, pytest, pre-commit) ficam em `dev`. Ferramentas de documentação ficam em `docs`.
- **[OBRIGATÓRIO]** Não edite as dependências à mão quando um comando do Poetry resolve. Se editar à mão, rode `poetry lock` e `poetry check --lock` em seguida.

---

## 3. Arquitetura e estrutura do projeto

### 3.1 src layout

**[OBRIGATÓRIO]** O código do pacote fica em `src/<nome_do_pacote>/`. O src layout impede que os testes importem o código "por acidente" a partir da raiz do repositório e obriga a testar o pacote instalado. O Poetry instala o projeto em modo editável no `poetry install`.

```toml
[tool.poetry]
packages = [{ include = "meu_projeto", from = "src" }]
```

### 3.2 Estrutura de referência

```text
meu-projeto/
├── pyproject.toml
├── poetry.lock
├── README.md
├── mkdocs.yml
├── .gitignore
├── .pre-commit-config.yaml
├── .env.example              # nomes das variáveis, sem valores sensíveis
├── src/
│   └── meu_projeto/
│       ├── __init__.py
│       ├── __main__.py       # entrypoint opcional: python -m meu_projeto
│       ├── config/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       ├── pipelines/
│       └── utils/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── conftest.py
└── docs/
    ├── index.md
    ├── architecture.md
    ├── development.md
    ├── testing.md
    └── api.md
```

**[OBRIGATÓRIO]** Essa estrutura é uma **referência adaptável**. Não crie diretórios vazios nem módulos "para o futuro". Cada diretório nasce junto com o primeiro código que precisa dele.

### 3.3 Responsabilidade de cada diretório

| Diretório | Responsabilidade | Quando criar | Não deve conter |
|---|---|---|---|
| `config/` | Carregar e validar configurações (variáveis de ambiente, arquivos de config) e expor objetos tipados | Quando houver mais de um parâmetro externo ou mais de um ambiente | Regras de negócio; leitura de `os.environ` espalhada pelo código |
| `domain/` | Entidades, schemas, regras de negócio e transformações **puras** (sem I/O) | Quando houver regra de negócio ou transformação não trivial | Conexões, SDKs de nuvem, clientes HTTP, `logging.basicConfig` |
| `application/` | Casos de uso: coordena domínio e portas de I/O para realizar uma operação | Quando um fluxo combinar várias etapas reutilizáveis por mais de um entrypoint | Detalhes de driver/SQL específicos |
| `infrastructure/` | Conectores: APIs, bancos, storage, filas, data warehouse/lake | Quando houver integração com um sistema externo | Regra de negócio |
| `pipelines/` | Orquestração e entrypoints: monta as dependências e executa extract → transform → load | Quando houver um job executável | Lógica de transformação inline |
| `utils/` | Utilidades técnicas **genéricas e coesas**, separadas por tema (`utils/dates.py`, `utils/retry.py`) | Somente quando duas ou mais camadas precisarem da mesma utilidade técnica | Regras de negócio; um `utils.py`/`helpers.py` que funcione como depósito |

**Projetos pequenos** (um script de ingestão, por exemplo): `config.py`, `extract.py`, `transform.py`, `load.py` e `main.py` dentro de `src/<pacote>/` já atendem ao padrão. Passe para subpacotes quando um módulo crescer em responsabilidades, e não por antecipação.

**Direção das dependências [OBRIGATÓRIO]:**

```text
pipelines ──► application ──► domain
    │              │
    └──────► infrastructure ──► domain (apenas tipos/schemas)
config ◄── (usado por pipelines e infrastructure)
```

- `domain` não importa nada de `infrastructure`, `pipelines` ou `config`.
- Não há imports circulares nem dependências bidirecionais entre pacotes.

### 3.4 Regras de modularidade

1. **[OBRIGATÓRIO]** Cada módulo tem uma responsabilidade clara e coesa. O nome do módulo descreve essa responsabilidade (`race_results_extractor.py`, não `stuff.py`).
2. **[OBRIGATÓRIO]** Não concentre regra de negócio, acesso a dados, configuração e orquestração no mesmo arquivo.
3. **[OBRIGATÓRIO]** Uma função faz uma coisa. Se precisar de "e" para descrevê-la ("busca **e** transforma **e** grava"), divida.
4. **[OBRIGATÓRIO]** Dependências são explícitas: recebidas por parâmetro ou construtor. Não use estado global mutável, singletons implícitos nem leitura de ambiente em módulos de domínio.
5. **[OBRIGATÓRIO]** Separe regra de negócio de detalhes de infraestrutura.
6. **[OBRIGATÓRIO]** Não crie imports circulares. Se surgir um, o desenho de responsabilidades está errado: extraia o tipo compartilhado para `domain`.
7. **[OBRIGATÓRIO]** Não crie classes, interfaces (`Protocol`/ABC) ou camadas sem necessidade concreta. Função simples é preferível a classe sem estado.
8. **[OBRIGATÓRIO]** Não use `helpers.py` ou `utils.py` genéricos. Utilidades vão em módulos temáticos.
9. **[OBRIGATÓRIO]** Nomes descritivos e consistentes: `snake_case` para módulos, funções e variáveis; `PascalCase` para classes; `UPPER_SNAKE_CASE` para constantes.
10. **[RECOMENDADO]** Funções e classes pequenas o suficiente para ler, testar e manter. Não há limite fixo de linhas; o critério é coesão e testabilidade.
11. **[RECOMENDADO]** Prefira composição a herança.

### 3.5 Organização para Engenharia de Dados

**Extração** (`infrastructure/`). Um conector por sistema de origem, por exemplo `infrastructure/ergast_api.py`, `infrastructure/postgres_source.py`, `infrastructure/s3_reader.py`. O conector devolve dados em uma estrutura neutra (dataclasses, dicts tipados, DataFrames) e não aplica regra de negócio.

**Transformação e validação** (`domain/`). Funções puras: recebem dados e devolvem dados. A validação de schema e de contrato fica aqui ou em `domain/schemas.py`. São as partes mais fáceis de testar, por isso concentram a maior parte da cobertura.

**Carga** (`infrastructure/`). Um writer por destino (`warehouse_writer.py`, `lake_writer.py`). É responsável por idempotência, transações e particionamento (ver seção 11.2).

**Pipelines** (`pipelines/`). Cada pipeline é um módulo fino que monta as dependências e chama extract → transform → load:

```python
"""Pipeline batch de resultados de corridas."""

import logging
from datetime import date

from meu_projeto.config.settings import Settings
from meu_projeto.domain.results import normalize_results
from meu_projeto.infrastructure.results_api import ResultsApiClient
from meu_projeto.infrastructure.warehouse_writer import WarehouseWriter

logger = logging.getLogger(__name__)


def run(settings: Settings, run_date: date) -> int:
    """Executa o pipeline para uma data e retorna o número de linhas carregadas."""
    client = ResultsApiClient(settings.api_base_url, timeout=settings.http_timeout_s)
    writer = WarehouseWriter(settings.warehouse_dsn)

    raw = client.fetch_results(run_date)
    rows = normalize_results(raw)
    loaded = writer.upsert_results(rows, partition=run_date)

    logger.info("pipeline concluído", extra={"run_date": run_date.isoformat(), "rows": loaded})
    return loaded
```

**Batch × streaming.** Batch é o padrão. Para streaming, as mesmas regras de `domain` valem por mensagem ou micro-lote; o consumidor e o produtor ficam em `infrastructure/`, e o loop de consumo fica em `pipelines/`.

**Integrações com warehouse, lake e serviços externos.** SDKs de nuvem e drivers só aparecem em `infrastructure/`. Trocar de destino não deve exigir mudança em `domain/`.

**Configuração por ambiente.** Fica em `config/` (ver seção 4.6). O ambiente (`dev`, `staging`, `prod`) é selecionado por variável de ambiente, não por `if` espalhado pelo código.

**Observabilidade.** Logging estruturado (seção 4.5), métricas de volume (linhas lidas, gravadas e rejeitadas), duração por etapa e erros com contexto (`run_id`, partição, origem).

**[OBRIGATÓRIO]** Não adote frameworks de orquestração (Airflow, Dagster, Prefect), processamento distribuído (Spark, Dask) ou tecnologias de armazenamento específicas sem requisito que justifique (volume, SLA, agendamento, dependências entre jobs). Quando adotados, eles chamam funções de `pipelines/`. A regra de negócio não fica presa ao framework.

---

## 4. Padrões de código Python

Base: PEP 8 (estilo, aplicada pelo Ruff), PEP 257 (docstrings) e o Zen of Python.

### 4.1 Obrigatório × avaliado no contexto

| Prática | Nível | Critério objetivo |
|---|---|---|
| Type hints em funções, métodos e classes **públicas** | [OBRIGATÓRIO] | Toda função sem prefixo `_` exportada pelo módulo |
| Type hints em funções privadas | [RECOMENDADO] | Quando o tipo não for óbvio |
| `pathlib.Path` para caminhos | [OBRIGATÓRIO] | Não use `os.path.join` nem concatenação de strings |
| `with` para arquivos, conexões, locks e sessões | [OBRIGATÓRIO] | Todo recurso que precisa ser fechado |
| `logging` em vez de `print()` para observabilidade | [OBRIGATÓRIO] | `print` só em saída de CLI destinada ao usuário |
| Credenciais fora do código | [OBRIGATÓRIO] | Zero segredos em código, testes, notebooks ou docs |
| Exceções específicas | [OBRIGATÓRIO] | `except Exception` só em fronteiras (entrypoint) e com log + re-raise ou código de saída |
| Docstrings em módulos, classes e funções públicas | [OBRIGATÓRIO] | Verificado pelo Ruff (`D`), estilo Google |
| Checagem estática de tipos (mypy/pyright) | [AVALIAR] | Recomendada em projetos com muitas interfaces entre camadas. Se adotada, roda no CI e é configurada no `pyproject.toml` |
| Dataclasses ou modelos de validação (ex.: pydantic) | [AVALIAR] | Dataclasses por padrão; pydantic quando houver validação rica de entrada externa |

### 4.2 Type hints

- Use a sintaxe moderna (`list[str]`, `dict[str, int]`, `X | None`); o Ruff `UP` ajusta automaticamente.
- Em parâmetros, prefira tipos abstratos (`Iterable`, `Mapping`, `Sequence` de `collections.abc`). Em retornos, use tipos concretos.
- Imports usados só para tipagem ficam em `if TYPE_CHECKING:` quando isso evita custo de import ou import circular.

### 4.3 Caminhos, arquivos e recursos

```python
from pathlib import Path


def read_manifest(base_dir: Path) -> str:
    """Lê o manifesto do diretório de dados."""
    manifest = base_dir / "manifest.json"
    with manifest.open(encoding="utf-8") as fh:
        return fh.read()
```

- **[OBRIGATÓRIO]** Informe `encoding="utf-8"` ao abrir arquivos de texto.
- **[OBRIGATÓRIO]** Conexões de banco, sessões HTTP e clientes de storage são abertos e fechados com `with` (ou `contextlib.closing` / `ExitStack`).
- **[RECOMENDADO]** Escreva um context manager próprio (`contextlib.contextmanager`) quando houver setup/teardown que se repete.

### 4.4 Exceções

```python
class SourceUnavailableError(RuntimeError):
    """A fonte de dados não respondeu dentro das tentativas configuradas."""


def fetch(client: ResultsApiClient, run_date: date) -> list[dict]:
    """Busca resultados, traduzindo falhas de rede em erro de domínio."""
    try:
        return client.fetch_results(run_date)
    except TimeoutError as exc:
        raise SourceUnavailableError(f"timeout ao buscar {run_date}") from exc
```

- **[OBRIGATÓRIO]** Capture a exceção mais específica possível e preserve a causa com `raise ... from exc`.
- **[OBRIGATÓRIO]** Não use `except:` vazio nem `except Exception: pass`. Erro engolido é bug escondido.
- **[OBRIGATÓRIO]** Valide entradas na fronteira (API pública do módulo, leitura de origem) e levante `ValueError`/`TypeError` ou uma exceção de domínio com mensagem clara.
- **[RECOMENDADO]** Crie exceções de domínio quando o chamador precisar distinguir os casos de erro. Não crie hierarquias que ninguém captura.

### 4.5 Logging

```python
import logging

logger = logging.getLogger(__name__)


def load(rows: list[Row]) -> None:
    """Carrega linhas no destino."""
    logger.info("carregando %d linhas", len(rows))
```

- **[OBRIGATÓRIO]** Use `logging.getLogger(__name__)` por módulo.
- **[OBRIGATÓRIO]** A configuração do logging (handlers, nível, formato) é feita **uma vez**, no entrypoint. Bibliotecas e módulos de domínio não chamam `logging.basicConfig`.
- **[OBRIGATÓRIO]** Não registre segredos, tokens, DSNs com senha nem dados pessoais (PII). Mascare quando precisar referenciá-los.
- **[RECOMENDADO]** Use interpolação lazy (`logger.info("x=%s", x)`) e campos de contexto (`extra=` ou formatador JSON) em produção.
- Use `logger.exception(...)` dentro de `except` para registrar o traceback.

### 4.6 Configuração e segredos

```python
"""Configurações carregadas do ambiente."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuração imutável da aplicação."""

    env: str
    api_base_url: str
    warehouse_dsn: str
    http_timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        """Cria as configurações a partir de variáveis de ambiente.

        Raises:
            KeyError: Se uma variável obrigatória não estiver definida.
        """
        return cls(
            env=os.environ.get("APP_ENV", "dev"),
            api_base_url=os.environ["API_BASE_URL"],
            warehouse_dsn=os.environ["WAREHOUSE_DSN"],
            http_timeout_s=float(os.environ.get("HTTP_TIMEOUT_S", "30")),
        )
```

- **[OBRIGATÓRIO]** Configuração externa ao código. Segredos vêm do ambiente ou de um gerenciador de segredos (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault), nunca de literais no código.
- **[OBRIGATÓRIO]** Falhe cedo e com mensagem clara quando faltar uma variável obrigatória.
- **[OBRIGATÓRIO]** Versione `.env.example` só com os nomes das variáveis. `.env` fica no `.gitignore`.
- **[AVALIAR]** `pydantic-settings` quando houver muitas variáveis, conversões e validações. Senão, a dataclass acima é suficiente.

### 4.7 `None`, valores padrão e mutáveis

```python
# Errado: a lista é compartilhada entre chamadas (o Ruff B006 detecta)
def add_tag(tag: str, tags: list[str] = []) -> list[str]: ...


# Certo
def add_tag(tag: str, tags: list[str] | None = None) -> list[str]:
    """Adiciona uma tag a uma nova lista."""
    result = list(tags) if tags is not None else []
    result.append(tag)
    return result
```

- **[OBRIGATÓRIO]** Não use mutáveis como valor padrão.
- **[OBRIGATÓRIO]** Compare com `None` usando `is` / `is not`.
- **[RECOMENDADO]** Use dataclasses `frozen=True` para objetos de valor e `field(default_factory=list)` para coleções.

### 4.8 Docstrings, comentários e código morto

- **[OBRIGATÓRIO]** Docstrings no **estilo Google** em módulos, classes e funções públicas. Inclua `Args`, `Returns` e `Raises` quando agregarem informação além da assinatura.
- **[OBRIGATÓRIO]** Comentários explicam o **porquê**, não o "o quê". Remova comentários que repetem o código.
- **[OBRIGATÓRIO]** Não deixe código comentado, funções sem uso nem `TODO` sem issue associada. O histórico fica no git.
- **[RECOMENDADO]** Elimine duplicação quando a mesma regra aparecer em três lugares ou quando a duplicação puder divergir de forma perigosa. Duplicação acidental de duas linhas não justifica abstração.

---

## 5. Ruff: lint, formatação e imports

**[OBRIGATÓRIO]** O Ruff é a única ferramenta de lint, formatação e ordenação de imports. Não adicione Black, isort, flake8 ou pylint em paralelo. Toda a configuração fica no `pyproject.toml`.

### 5.1 Configuração de referência

```toml
[tool.ruff]
target-version = "py312"          # igual ao limite inferior de requires-python
line-length = 100
src = ["src", "tests"]            # identifica o pacote em src/ como first-party
extend-exclude = ["docs", "notebooks"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle: erros de estilo
    "W",    # pycodestyle: avisos (espaços em branco)
    "F",    # Pyflakes: nomes indefinidos, imports não usados etc.
    "I",    # isort: ordenação e agrupamento de imports
    "B",    # flake8-bugbear: padrões que costumam ser bugs
    "UP",   # pyupgrade: sintaxe moderna para a target-version
    "SIM",  # flake8-simplify: simplificações seguras
    "D",    # pydocstyle: docstrings (adotado conscientemente, estilo Google)
]
ignore = [
    "E501",  # comprimento de linha: o formatter cuida; strings/URLs longas são toleradas
    "D104",  # docstring em __init__.py de pacote: opcional
    "D105",  # docstring em métodos mágicos: redundante
    "D107",  # docstring em __init__: documente na classe
    "W191",  # redundante com o formatter (indentação com tab)
    "D206",  # redundante com o formatter
    "D300",  # redundante com o formatter (estilo de aspas de docstring)
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D"]           # nomes de teste descritivos substituem docstrings

[tool.ruff.lint.isort]
known-first-party = ["meu_projeto"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
```

**Justificativa das decisões:**

- **Conjunto de regras enxuto e coeso.** `E`/`W`/`F` cobrem PEP 8 e erros estáticos. `B` pega bugs reais (mutáveis como default, `except` amplo, `zip` sem `strict`). `UP` mantém a sintaxe atual. `SIM` sugere simplificações seguras. `I` substitui o isort.
- **`D` com `convention = "google"`.** A convenção desliga automaticamente as regras de pydocstyle incompatíveis com o estilo Google. Testes ficam isentos.
- **`ignore` mínimo.** Cada item tem motivo. As regras `W191`, `D206` e `D300` são listadas pela documentação do Ruff como redundantes ou conflitantes com o formatter.
- **Não habilitar `ALL`** nem famílias inteiras sem análise. Adicionar uma família nova (ex.: `S` bandit, `PTH`, `RUF`, `PL`) exige PR próprio, rodando no código existente, com justificativa.
- **`src = ["src", "tests"]`.** Faz o Ruff classificar `meu_projeto` como first-party na ordenação de imports. O `known-first-party` deixa isso explícito.

### 5.2 Ordem de execução

A organização de imports acontece **antes** da validação final de lint, e a formatação acontece depois das correções:

```bash
poetry run ruff check --select I --fix .   # 1. organiza imports
poetry run ruff check --fix .              # 2. aplica correções seguras (revise o diff)
poetry run ruff format .                   # 3. formata
poetry run ruff format --check .           # 4. valida a formatação (modo CI)
poetry run ruff check .                    # 5. validação final de lint (modo CI)
```

- **[OBRIGATÓRIO]** Revise o diff de qualquer `--fix`. Por padrão o Ruff aplica apenas *safe fixes*. **Não use `--unsafe-fixes`** sem revisar caso a caso, porque essas correções podem mudar o comportamento (ex.: `x == True` → `x`).
- **[OBRIGATÓRIO]** Não silencie regras para fazer o lint passar. `# noqa` só com o código da regra e um motivo: `# noqa: B008 - dependência resolvida pelo framework`. `noqa` sem código não é permitido.
- **[OBRIGATÓRIO]** No CI rodam apenas `ruff check .` e `ruff format --check .`, sem `--fix` (ver seção 10).

---

## 6. Testes com pytest

### 6.1 Requisito de cobertura

**[OBRIGATÓRIO]** Cobertura **global mínima de 50%** (linhas + branches), medida pelo pytest-cov e **verificada automaticamente**. Com a configuração abaixo, `poetry run pytest` falha (exit code ≠ 0) quando a cobertura fica abaixo de 50%:

```text
FAIL Required test coverage of 50% not reached. Total coverage: 42.10%
```

### 6.2 Configuração de referência

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = [
    "--strict-markers",          # marker não declarado gera erro
    "--strict-config",           # configuração inválida gera erro
    "--import-mode=importlib",   # recomendado para projetos novos; dispensa __init__.py em tests/
    "-ra",                       # resumo de testes pulados/falhos
    "--cov=meu_projeto",
    "--cov-report=term-missing",
]
markers = [
    "integration: testes que dependem de serviços locais (ex.: banco em container)",
    "e2e: testes ponta a ponta do pipeline",
]

[tool.coverage.run]
branch = true
source = ["meu_projeto"]

[tool.coverage.report]
fail_under = 50
show_missing = true
skip_covered = true
exclude_also = [
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

Observações:

- O pytest-cov lê `fail_under` de `[tool.coverage.report]`. O limite fica definido **em um único lugar**, sem repetir `--cov-fail-under` nos comandos.
- `source = ["meu_projeto"]` usa o **nome do pacote importável**, não o caminho. Isso funciona com o src layout porque o Poetry instala o projeto no ambiente.
- `__init__.py` **não** é omitido da cobertura. Pelo padrão, esses arquivos são finos e não distorcem o número. Se um `__init__.py` tiver lógica, ela precisa ser testada.
- Como `--cov` está em `addopts`, execuções parciais (um único arquivo de teste) podem falhar no gate. Nesses casos use `--no-cov`. O gate continua valendo na execução completa e no CI.
- O pytest 9 também aceita a tabela nativa `[tool.pytest]`. Mantenha `[tool.pytest.ini_options]` para compatibilidade com pytest 8, e não use as duas ao mesmo tempo.

### 6.3 Linhas × branches

- **Cobertura de linhas** mede se cada linha foi executada.
- **Cobertura de branches** mede se cada caminho de decisão foi seguido. Um `if` sem `else` executado só com condição verdadeira tem 100% das linhas cobertas, mas o caminho "falso" nunca foi testado.
- **[RECOMENDADO]** `branch = true` por padrão: em código de transformação, os bugs costumam estar no caminho não testado.
- **50% é um piso, não uma meta de qualidade.** Cobertura mede execução, não verificação. Um teste sem `assert` relevante aumenta a cobertura sem provar nada. Concentre testes no `domain/` (regras e transformações), onde o retorno é maior.

### 6.4 Organização e nomenclatura

```text
tests/
├── conftest.py                 # fixtures compartilhadas
├── fixtures/                   # arquivos de dados de exemplo (JSON, CSV pequenos)
├── unit/
│   ├── domain/test_results.py  # espelha src/meu_projeto/domain/results.py
│   └── infrastructure/test_results_api.py
└── integration/
    └── test_warehouse_writer.py
```

- **[OBRIGATÓRIO]** Arquivos `test_*.py` e funções `test_*`. A estrutura de `tests/unit/` espelha `src/<pacote>/`.
- **[OBRIGATÓRIO]** Nomes de teste descrevem o comportamento: `test_normalize_results_drops_rows_without_driver_id`.
- **[OBRIGATÓRIO]** Testes unitários são **independentes e determinísticos**: sem ordem de execução, sem relógio real (injete `date`/`datetime` ou use fixtures), sem aleatoriedade sem seed.
- **[OBRIGATÓRIO]** Testes unitários **não** usam rede, credenciais reais nem infraestrutura externa.
- **[OBRIGATÓRIO]** Testes de integração e e2e são marcados (`pytestmark = pytest.mark.integration` no módulo) e podem ser selecionados com `-m`.

### 6.5 Fixtures, parametrização e casos-limite

```python
# tests/conftest.py
import pytest

from meu_projeto.domain.transformations import LapTime


@pytest.fixture
def laps() -> list[LapTime]:
    return [LapTime("VER", 90_100), LapTime("HAM", 89_900)]
```

```python
# tests/unit/domain/test_transformations.py
import pytest

from meu_projeto.domain.transformations import LapTime, fastest_lap


def test_fastest_lap_returns_lowest_time(laps):
    assert fastest_lap(laps) == LapTime("HAM", 89_900)


@pytest.mark.parametrize("empty", [[], ()])
def test_fastest_lap_rejects_empty_input(empty):
    with pytest.raises(ValueError, match="nenhuma volta"):
        fastest_lap(empty)
```

- **[OBRIGATÓRIO]** Para toda regra relevante, teste o cenário positivo, o negativo (entrada inválida → exceção esperada, com `pytest.raises(..., match=...)`) e os casos-limite (vazio, `None`, um elemento, duplicados, fronteiras de data e fuso).
- **[RECOMENDADO]** Use `pytest.mark.parametrize` em vez de laços ou de testes copiados.
- **[RECOMENDADO]** Use as fixtures embutidas para isolamento: `tmp_path` (arquivos), `monkeypatch` (variáveis de ambiente, atributos), `caplog` (logs).

### 6.6 Mocks e isolamento

```python
from datetime import date
from unittest.mock import Mock

from meu_projeto.pipelines import results_pipeline


# `settings` é uma fixture do conftest.py que devolve um Settings com valores fictícios
def test_run_loads_normalized_rows(monkeypatch, settings):
    client = Mock()
    client.fetch_results.return_value = [{"driver": "VER", "position": "1"}]
    writer = Mock()
    writer.upsert_results.return_value = 1
    monkeypatch.setattr(results_pipeline, "ResultsApiClient", lambda *a, **kw: client)
    monkeypatch.setattr(results_pipeline, "WarehouseWriter", lambda *a, **kw: writer)

    assert results_pipeline.run(settings, date(2024, 3, 2)) == 1
    writer.upsert_results.assert_called_once()
```

- **[OBRIGATÓRIO]** Faça mock **nas fronteiras** (cliente HTTP, driver, SDK), nunca na regra de negócio que está sendo testada.
- **[OBRIGATÓRIO]** Não faça mocks em excesso. Se o teste só confirma que mocks chamam mocks, ele não testa nada. Prefira testar funções puras de `domain/` com dados reais de exemplo.
- **[RECOMENDADO]** Use `Mock(spec=Classe)` / `create_autospec` para que o mock falhe se a interface real mudar.
- **[AVALIAR]** Bibliotecas de stub HTTP (`respx`, `responses`) ou containers efêmeros (`testcontainers`) para testes de integração, adicionadas com `poetry add --group dev`.
- **[RECOMENDADO]** Bancos em testes: SQLite em memória ou container efêmero em integração. Nunca um banco compartilhado ou de produção.

### 6.7 Proibições

- **[OBRIGATÓRIO]** Não reduza a cobertura artificialmente com `omit`, `exclude_also` ou `# pragma: no cover` injustificados. Cada exclusão precisa de um motivo (código inalcançável por definição, bloco `TYPE_CHECKING`).
- **[OBRIGATÓRIO]** Não escreva testes que apenas executam código sem verificar o resultado.
- **[OBRIGATÓRIO]** Não baixe `fail_under` para fazer o CI passar.
- **[OBRIGATÓRIO]** Não marque testes que falham como `skip`/`xfail` sem issue associada e motivo explícito.

---

## 7. Documentação com MkDocs Material

**[OBRIGATÓRIO]** A documentação é parte do código: fica em `docs/`, é revisada em PR e precisa compilar com `mkdocs build --strict` antes do merge.

### 7.1 Estrutura mínima

| Página | Conteúdo |
|---|---|
| `docs/index.md` | O que o projeto faz, para quem, visão geral do fluxo de dados, quickstart |
| `docs/architecture.md` | Camadas, direção de dependências, fluxos principais (origem → transformação → destino), decisões arquiteturais (ADRs curtos) |
| `docs/development.md` | Pré-requisitos, instalação com Poetry, variáveis de ambiente (nomes e propósito, **sem valores sensíveis**), como executar, workflow, pre-commit |
| `docs/testing.md` | Como rodar testes unitários e de integração, cobertura, markers, como preparar dependências locais |
| `docs/api.md` | Referência dos módulos públicos ([AVALIAR] geração automática com mkdocstrings) |

Priorize o que ajuda quem precisa **instalar, executar, entender, operar ou manter** o projeto. Não documente detalhes triviais que a assinatura e a docstring já explicam.

### 7.2 Dependências

```bash
poetry add --group docs "mkdocs>=1.6,<2" mkdocs-material
poetry add --group docs "mkdocstrings[python]"   # apenas se docs/api.md usar geração automática
```

**[AVALIAR] mkdocstrings.** Adote quando houver API pública consumida por outras pessoas ou outros projetos. Em pipelines sem API reutilizável, uma página manual de arquitetura costuma ser mais útil.

### 7.3 `mkdocs.yml` de referência

```yaml
site_name: Meu Projeto
site_description: Documentação técnica do pipeline de dados.
repo_url: https://github.com/minha-org/meu-projeto
docs_dir: docs
strict: true

theme:
  name: material
  language: pt-BR
  features:
    - navigation.sections
    - navigation.top
    - search.highlight
    - content.code.copy

nav:
  - Início: index.md
  - Arquitetura: architecture.md
  - Desenvolvimento: development.md
  - Testes: testing.md
  - Referência da API: api.md

plugins:
  - search
  - mkdocstrings:            # remova este bloco se não usar mkdocstrings
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: false
            show_root_heading: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - tables
  - toc:
      permalink: true

validation:
  links:
    not_found: warn
    anchors: warn
```

Com mkdocstrings, `docs/api.md` referencia módulos pelo caminho de import:

```markdown
# Referência da API

::: meu_projeto.domain.transformations
```

- `paths: [src]` permite ao mkdocstrings encontrar o pacote no src layout.
- `docstring_style: google` deve ser igual à convenção do Ruff (`pydocstyle.convention`).
- `strict: true` e `--strict` transformam avisos (links quebrados, páginas fora do `nav`) em erro.

### 7.4 Comandos

```bash
poetry run mkdocs serve            # servidor local com recarregamento em http://127.0.0.1:8000
poetry run mkdocs build --strict   # validação (obrigatória no CI)
poetry run mkdocs gh-deploy        # [AVALIAR] publicação no GitHub Pages
```

- **[OBRIGATÓRIO]** Adicione `site/` (saída do build) ao `.gitignore`.
- **[RECOMENDADO]** Publique a documentação pelo CI, a partir da branch principal, e não da máquina de um desenvolvedor.

---

## 8. pyproject.toml de referência

**[OBRIGATÓRIO]** O `pyproject.toml` é a fonte central de configuração: metadados, dependências, Ruff, pytest e coverage. Não duplique essas configurações em `setup.cfg`, `pytest.ini`, `.coveragerc`, `ruff.toml` ou `tox.ini`. Fora dele ficam apenas o `mkdocs.yml` (o MkDocs não lê o `pyproject.toml`) e o `.pre-commit-config.yaml`.

Arquivo completo e coerente com as seções anteriores (validado com Poetry 2.5):

```toml
# ── Metadados do projeto (PEP 621) ─────────────────────────────────────────
[project]
name = "meu-projeto"
version = "0.1.0"
description = "Pipeline de dados de resultados de corridas."
readme = "README.md"
requires-python = ">=3.12,<4.0"
authors = [{ name = "Time de Dados", email = "dados@example.com" }]
# Dependências de runtime: gerenciadas com `poetry add <pacote>`
dependencies = [
    "httpx (>=0.28.1,<0.29.0)",  # exemplo; adicione somente o que o projeto usa
]

[project.scripts]
meu-projeto = "meu_projeto.__main__:main"   # [AVALIAR] somente se houver CLI

# ── Configuração específica do Poetry ──────────────────────────────────────
[tool.poetry]
packages = [{ include = "meu_projeto", from = "src" }]
requires-poetry = ">=2.0,<3.0"

# ── Dependências de desenvolvimento (PEP 735, gerenciadas por `poetry add --group`) ──
[dependency-groups]
dev = [
    "ruff (>=0.17.1,<0.18.0)",
    "pytest (>=9.1.1,<10.0.0)",
    "pytest-cov (>=7.1.0,<8.0.0)",
    "pre-commit (>=4.7.0,<5.0.0)",
]
docs = [
    "mkdocs (>=1.6,<2)",
    "mkdocs-material (>=9.7.7,<10.0.0)",
    "mkdocstrings[python] (>=1.0.8,<2.0.0)",
]

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

# ── Ruff ───────────────────────────────────────────────────────────────────
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]
extend-exclude = ["docs", "notebooks"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "D"]
ignore = ["E501", "D104", "D105", "D107", "W191", "D206", "D300"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D"]

[tool.ruff.lint.isort]
known-first-party = ["meu_projeto"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true

# ── pytest ─────────────────────────────────────────────────────────────────
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--import-mode=importlib",
    "-ra",
    "--cov=meu_projeto",
    "--cov-report=term-missing",
]
markers = [
    "integration: testes que dependem de serviços locais (ex.: banco em container)",
    "e2e: testes ponta a ponta do pipeline",
]

# ── Coverage ───────────────────────────────────────────────────────────────
[tool.coverage.run]
branch = true
source = ["meu_projeto"]

[tool.coverage.report]
fail_under = 50
show_missing = true
skip_covered = true
exclude_also = [
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

**Separação de responsabilidades no arquivo:**

| Seção | Conteúdo |
|---|---|
| `[project]` | Metadados e **dependências de runtime** (padrão PEP 621) |
| `[tool.poetry]` | Detalhes exclusivos do Poetry: `packages` (src layout) e `requires-poetry` |
| `[dependency-groups]` | **Dependências de desenvolvimento e documentação**, que não vão para o pacote distribuído |
| `[build-system]` | Backend de build (poetry-core) |
| `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.coverage.*]` | Configuração das ferramentas |

As faixas de versão acima são as que o `poetry add` gerou na validação deste padrão. Em um projeto novo, **não copie as faixas**: rode `poetry add` e deixe o Poetry resolver versões compatíveis no momento.

`.gitignore` mínimo:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.coverage
.coverage.*
htmlcov/
coverage.xml
site/
dist/
.env
.env.*
!.env.example
```

---

## 9. Workflow de desenvolvimento

Fluxo padrão para funcionalidades e correções:

| # | Etapa | Ação / comando |
|---|---|---|
| 1 | Entender requisitos e dependências | Ler a issue, os contratos de dados de origem e destino e o código existente |
| 2 | Identificar os módulos responsáveis | Localizar a camada certa (seção 3.3) |
| 3 | Propor uma solução simples e modular | Menor mudança que resolve; registrar decisões relevantes |
| 4 | Implementar | Respeitando as seções 3 e 4 |
| 5 | Criar ou atualizar testes | Positivo, negativo e limite (seção 6) |
| 6 | Organizar imports | `poetry run ruff check --select I --fix .` |
| 7 | Lint e formatação | `poetry run ruff check --fix .` → revisar diff → `poetry run ruff format .` |
| 8 | Executar os testes | `poetry run pytest` |
| 9 | Validar cobertura mínima | Já incluída no passo 8 (gate de 50%). Confirmar "Required test coverage of 50% reached" |
| 10 | Construir a documentação | `poetry run mkdocs build --strict` |
| 11 | Revisar alterações e efeitos colaterais | `git diff`; impacto em contratos, schemas, consumidores, idempotência; checklist do Apêndice C |

Validação final, equivalente ao CI:

```bash
poetry check --lock
poetry run ruff check .
poetry run ruff format --check .
poetry run pytest
poetry run mkdocs build --strict
```

**[OBRIGATÓRIO]** Nunca declare que testes, lint ou build passaram sem ter executado os comandos e visto a saída. Se uma validação não foi executada, diga isso explicitamente e informe o comando correspondente.

---

## 10. Automação e qualidade contínua

### 10.1 Pre-commit [RECOMENDADO]

Os hooks usam o Ruff **do ambiente Poetry** (`repo: local`), para que as versões locais, do pre-commit e do CI sejam as mesmas do `poetry.lock`, sem um segundo ambiente paralelo.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: poetry run ruff check --fix
        language: system
        types_or: [python, pyi]
      - id: ruff-format
        name: ruff format
        entry: poetry run ruff format
        language: system
        types_or: [python, pyi]
      - id: poetry-check
        name: poetry check
        entry: poetry check --lock
        language: system
        pass_filenames: false
        files: ^(pyproject\.toml|poetry\.lock)$
```

```bash
poetry add --group dev pre-commit
poetry run pre-commit install
poetry run pre-commit run --all-files
```

O hook de lint vem antes do de formatação, porque correções de lint podem exigir reformatação. Nas versões mais novas do pre-commit, `language: system` pode aparecer com o nome `unsupported`. Valide com `poetry run pre-commit validate-config`.

Hooks locais **podem** alterar arquivos (`--fix`, `format`). Isso é aceitável porque o desenvolvedor revisa o diff antes do commit. No CI, nunca.

### 10.2 CI [OBRIGATÓRIO]

Todo pull request passa por uma pipeline de validação. O exemplo usa GitHub Actions, mas qualquer solução equivalente (GitLab CI, Azure Pipelines, Jenkins) serve, desde que execute **as mesmas etapas**.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"   # igual ao limite inferior de requires-python

      - name: Instalar Poetry
        run: pipx install "poetry>=2.0,<3.0"

      - name: Validar pyproject e lock
        run: poetry check --lock

      - name: Instalar dependências
        run: poetry install --no-interaction

      - name: Lint
        run: poetry run ruff check .

      - name: Formatação (somente verificação)
        run: poetry run ruff format --check .

      - name: Testes + cobertura (gate de 50%)
        run: poetry run pytest -m "not integration and not e2e"

      - name: Documentação
        run: poetry run mkdocs build --strict
```

- O Poetry é instalado com `pipx`, que isola a ferramenta do projeto, como recomenda a documentação oficial do Poetry. Isso não é gerenciamento de dependências do projeto com pip.
- **[OBRIGATÓRIO]** O CI **não** executa `--fix` nem `ruff format` sem `--check`. A validação é somente leitura.
- **[OBRIGATÓRIO]** O gate de cobertura vale para o conjunto de testes executado no CI. Se os testes de integração rodarem em um job separado, o gate de 50% precisa ser atingido pelo job de testes unitários.
- **[RECOMENDADO]** Execute os testes de integração em um job separado, com serviços efêmeros (`services:` ou containers), sem credenciais de produção.
- **[RECOMENDADO]** Use cache do ambiente (ex.: `cache: poetry` no `setup-python`, que exige o Poetry instalado antes desse passo) quando o tempo de CI justificar.

### 10.3 Critérios mínimos para bloquear merge [OBRIGATÓRIO]

O merge é bloqueado (branch protection com status checks obrigatórios) quando houver:

1. Falha no lint (`ruff check .`).
2. Código fora do padrão de formatação (`ruff format --check .`).
3. Falha em qualquer teste.
4. Cobertura global abaixo de 50%.
5. Falha no build da documentação em modo estrito (`mkdocs build --strict`).
6. `pyproject.toml` e `poetry.lock` inconsistentes (`poetry check --lock`).

### 10.4 Dependências e vulnerabilidades [RECOMENDADO]

- Atualizações controladas: Dependabot ou Renovate abrindo PRs de atualização do `poetry.lock`, ou um `poetry show --outdated` periódico seguido de `poetry update <pacote>` em PRs pequenos.
- Atualize uma ferramenta de qualidade (Ruff, pytest) por PR, rodando a validação completa.
- Varredura de vulnerabilidades: alertas do provedor (Dependabot security, GitLab dependency scanning) ou uma ferramenta de auditoria adicionada como dependência de dev e executada via `poetry run` no CI.
- Revise novas dependências: manutenção ativa, licença compatível, tamanho da árvore transitiva.

---

## 11. Segurança, robustez e produção

### 11.1 Recomendações gerais

| Tema | Regra |
|---|---|
| Segredos | **[OBRIGATÓRIO]** Nunca versionar senhas, tokens, chaves privadas, `.env` com valores, `credentials.json`, kubeconfigs. Se um segredo vazar no git, **revogue-o**: remover o commit não basta |
| Validação de entrada | **[OBRIGATÓRIO]** Valide dados e contratos na fronteira (origem externa, API pública do módulo): tipos, campos obrigatórios, domínios de valores |
| Tratamento de erros | **[OBRIGATÓRIO]** Não oculte exceções. `except Exception` só no entrypoint, com `logger.exception` e falha explícita (código de saída ≠ 0) |
| Timeouts | **[OBRIGATÓRIO]** Toda chamada de rede (HTTP, banco, storage) tem timeout explícito. Não use os padrões infinitos das bibliotecas |
| Retries | **[RECOMENDADO]** Somente para erros transitórios (timeout, 429, 5xx), com número máximo de tentativas e backoff exponencial com jitter. Nunca repita indefinidamente nem repita erros 4xx de validação |
| Logs | **[OBRIGATÓRIO]** Não registre segredos, tokens, DSNs completos nem PII. Mascare identificadores sensíveis |
| Recursos | **[OBRIGATÓRIO]** Conexões, sessões e arquivos via `with`. Reutilize clientes HTTP e pools em vez de abrir um por requisição |
| SQL | **[OBRIGATÓRIO]** Queries parametrizadas. Nunca monte SQL com f-string a partir de entrada externa |
| Desserialização | **[OBRIGATÓRIO]** Não use `pickle`, `yaml.load` sem `SafeLoader` ou `eval` em dados de origem não confiável |

```python
import httpx

# Timeout explícito e cliente reutilizado
with httpx.Client(base_url=settings.api_base_url, timeout=settings.http_timeout_s) as client:
    response = client.get("/results", params={"date": run_date.isoformat()})
    response.raise_for_status()
```

### 11.2 Requisitos específicos de pipelines de dados

- **[OBRIGATÓRIO] Idempotência de cargas.** Reexecutar um pipeline para a mesma partição não pode duplicar dados. Use `MERGE`/upsert por chave natural, overwrite de partição ou staging + swap atômico. Registre um `run_id` em cada execução.
- **[OBRIGATÓRIO] Transações e integridade.** Cargas que alteram várias tabelas usam transação ou padrão staging → validação → publicação. Valide contagens e chaves antes de publicar.
- **[RECOMENDADO] Reprocessamento.** Pipelines aceitam o intervalo de datas ou a partição como parâmetro (`run_date`), sem depender de "agora". Isso permite backfill e testes determinísticos.
- **[RECOMENDADO] Dados rejeitados.** Registros inválidos são contados e registrados (ou enviados para quarentena), sem derrubar o lote inteiro e sem serem descartados em silêncio. Defina um limiar de rejeição que, quando excedido, falha o pipeline.
- **[RECOMENDADO] Volume e memória.** Para grandes volumes, processe em streaming ou em lotes (geradores, `chunksize`, leitura paginada da API, cursores server-side). Não carregue a tabela inteira em memória. Prefira formatos colunares (Parquet) e projeção de colunas.
- **[AVALIAR] Performance.** Meça antes de otimizar (`cProfile`, tempo por etapa). Adote engines vetorizadas ou distribuídas (Polars, DuckDB, Spark) somente quando o volume ou o SLA exigirem.
- **[RECOMENDADO] Observabilidade.** Cada execução registra início, fim, duração, linhas lidas, gravadas e rejeitadas, e a partição processada.

---

## 12. Como a IA deve aplicar este skill

1. **[OBRIGATÓRIO] Inspecione antes de mudar.** Com acesso ao repositório, leia `pyproject.toml`, a estrutura de `src/` e `tests/`, o `mkdocs.yml` e a configuração de CI antes de criar ou alterar código. Confirme a versão do Poetry (`poetry --version`) e o ambiente ativo (`poetry env info --path`).
2. **[OBRIGATÓRIO] Respeite o que existe.** Siga a arquitetura e as convenções já adotadas. Corrija desvios deste padrão de forma **incremental** e explícita, sem reescrever o projeto sem pedido.
3. **[OBRIGATÓRIO] Não invente.** Não cite arquivos, funções, dependências, comandos ou opções de ferramentas que não existem. Em caso de dúvida sobre uma opção, consulte a documentação oficial ou `--help` antes de apresentá-la como válida.
4. **[OBRIGATÓRIO] Nunca use pip.** Toda dependência entra com `poetry add` (com `--group` quando for de dev ou docs).
5. **[OBRIGATÓRIO] Justifique dependências novas.** Explique por que a biblioteca é necessária e por que a stdlib ou as dependências existentes não bastam.
6. **[OBRIGATÓRIO] Não concentre responsabilidades** em um único arquivo nem crie `utils.py`/`helpers.py` genéricos.
7. **[OBRIGATÓRIO] Testes e docs andam com o código.** Ao adicionar funcionalidade, crie testes e avalie se é preciso atualizar a documentação. Ao modificar funcionalidade, avalie o impacto nos testes existentes e atualize-os, sem enfraquecê-los.
8. **[OBRIGATÓRIO] Não burle a qualidade.** Não desabilite regras de lint, não adicione `noqa`/`pragma: no cover` injustificados, não reduza `fail_under` e não marque testes como `skip` para fazer a validação passar.
9. **[RECOMENDADO] Mudanças pequenas e revisáveis.** Prefira vários passos explícitos a um diff grande.
10. **[OBRIGATÓRIO] Explicite decisões.** Informe decisões arquiteturais relevantes (nova camada, nova dependência, mudança de contrato) e os trade-offs.
11. **[OBRIGATÓRIO] Diferencie executado de recomendado.** Ao reportar, separe:
    - **Executado:** comando + resultado observado (ex.: "`poetry run pytest`: 42 passed, cobertura 63%").
    - **Não executado:** comando que o desenvolvedor deve rodar, e o motivo de não ter rodado.
12. **[OBRIGATÓRIO] Sem execução, sem afirmação.** Se não puder executar comandos, forneça-os sem dizer que foram executados ou que passaram.
13. **[OBRIGATÓRIO] Sinalize conflitos.** Se uma restrição explícita do projeto conflitar com este padrão (ex.: o projeto exige Python 3.10, usa Poetry 1.x ou proíbe uma ferramenta), aponte o conflito e proponha opções **antes** de adotar uma solução que comprometa a qualidade.
14. **[OBRIGATÓRIO] Ambiente correto.** Antes de instalar algo, confirme que `poetry env info --path` aponta para o ambiente do projeto, e não para um Python global herdado via `VIRTUAL_ENV`.

---

## Apêndice A: checklist de conformidade do projeto

Marque cada item com **Sim**, **Não** ou **N/A (com justificativa)**.

**Estrutura `src/`**
- [ ] Código do pacote em `src/<pacote>/` e `packages = [{ include = "<pacote>", from = "src" }]` configurado
- [ ] Não há diretórios ou módulos vazios criados "para o futuro"
- [ ] Testes em `tests/`, fora do pacote

**Poetry e dependências**
- [ ] `pyproject.toml` no formato do Poetry 2.x (`[project]` + `[tool.poetry]` + grupos)
- [ ] `requires-python` e `requires-poetry` declarados
- [ ] `poetry.lock` versionado e `poetry check --lock` passa
- [ ] Runtime em `[project].dependencies`; ferramentas em `dev`; documentação em `docs`
- [ ] Nenhuma ocorrência de `pip install`/`pip freeze`/`python -m pip` em README, docs, scripts, Dockerfile ou CI
- [ ] `mkdocs` restrito a `<2`

**Modularidade**
- [ ] Domínio sem I/O e sem imports de `infrastructure`/`pipelines`
- [ ] Conectores isolados em `infrastructure/`
- [ ] Pipelines finos (montagem + orquestração)
- [ ] Sem imports circulares; sem `utils.py`/`helpers.py` genéricos

**Ruff**
- [ ] Configuração apenas no `pyproject.toml`, com `target-version` coerente com `requires-python`
- [ ] `select` inclui `E`, `F`, `I`, `B`, `UP`, `SIM` (e `D`, se adotado); cada `ignore` tem justificativa
- [ ] `poetry run ruff check .` passa
- [ ] `poetry run ruff format --check .` passa
- [ ] Nenhum `noqa` sem código de regra

**Testes**
- [ ] pytest configurado com `--strict-markers` e markers declarados
- [ ] Unitários sem rede, credenciais ou infraestrutura externa
- [ ] Integração e e2e marcados e separáveis
- [ ] Testes cobrem cenários positivos, negativos e limites das regras de `domain/`

**Cobertura**
- [ ] `fail_under = 50` em `[tool.coverage.report]` e `branch = true`
- [ ] `poetry run pytest` falha abaixo de 50%
- [ ] Sem `omit`/`pragma: no cover` injustificados

**Documentação**
- [ ] `mkdocs.yml` com tema `material` e `strict: true`
- [ ] `docs/` contém index, arquitetura, desenvolvimento e testes (API quando aplicável)
- [ ] `poetry run mkdocs build --strict` passa
- [ ] Variáveis de ambiente documentadas sem valores sensíveis

**Segurança e configuração**
- [ ] Nenhum segredo no repositório; `.env` no `.gitignore`; `.env.example` versionado
- [ ] Configuração centralizada em `config/`, com falha clara para variável ausente
- [ ] Timeouts em todas as chamadas externas
- [ ] Logs sem segredos ou PII
- [ ] Cargas idempotentes

**Automação (CI)**
- [ ] CI executa: `poetry check --lock`, `ruff check`, `ruff format --check`, `pytest` (com gate), `mkdocs build --strict`
- [ ] CI não executa `--fix` nem formatação com escrita
- [ ] Branch protection exige os checks
- [ ] Pre-commit configurado (recomendado)

**Reprodutibilidade**
- [ ] `poetry install` em um clone limpo cria o ambiente sem passos manuais extras
- [ ] Versão de Python do CI igual ao limite inferior de `requires-python`
- [ ] README/`docs/development.md` descrevem o setup do zero

---

## Apêndice B: comandos de referência

```bash
# ── Ambiente ──────────────────────────────────────────────
poetry --version                       # confirmar Poetry 2.x
poetry env use 3.12                    # escolher o interpretador
poetry env info --path                 # confirmar que o ambiente é do projeto
poetry install                         # instalar tudo a partir do lock
poetry sync                            # instalar e remover pacotes fora do lock
poetry install --only main             # somente runtime (produção)
poetry env activate                    # imprimir o comando de ativação do ambiente

# ── Dependências ──────────────────────────────────────────
poetry add <pacote>                    # runtime
poetry add --group dev <pacote>        # desenvolvimento
poetry add --group docs <pacote>       # documentação
poetry remove <pacote>
poetry lock                            # recalcular o lock sem atualizar versões
poetry update [<pacote>]               # atualizar dentro das restrições
poetry check --lock                    # validar pyproject + lock
poetry show --top-level                # dependências diretas
poetry show --outdated                 # dependências desatualizadas

# ── Ruff ──────────────────────────────────────────────────
poetry run ruff check --select I --fix .   # organizar imports
poetry run ruff check --fix .              # correções seguras (revisar diff)
poetry run ruff format .                   # formatar
poetry run ruff format --check .           # verificar formatação (CI)
poetry run ruff check .                    # lint final (CI)

# ── Testes ────────────────────────────────────────────────
poetry run pytest                                          # suíte + cobertura com gate de 50%
poetry run pytest --cov=meu_projeto --cov-report=term-missing
poetry run pytest --cov=meu_projeto --cov-report=html      # relatório em htmlcov/
poetry run pytest -m "not integration and not e2e"         # apenas unitários
poetry run pytest -m integration                           # apenas integração
poetry run pytest tests/unit/domain/test_results.py --no-cov   # execução parcial sem gate
poetry run pytest -x -k "fastest_lap"                      # parar na 1ª falha, filtrar por nome

# ── Documentação ──────────────────────────────────────────
poetry run mkdocs serve
poetry run mkdocs build --strict

# ── Pre-commit ────────────────────────────────────────────
poetry run pre-commit install
poetry run pre-commit run --all-files

# ── Validação completa (equivalente ao CI) ────────────────
poetry check --lock && \
poetry run ruff check . && \
poetry run ruff format --check . && \
poetry run pytest && \
poetry run mkdocs build --strict
```

---

## Apêndice C: checklist de revisão de pull request

**Escopo e desenho**
- [ ] O PR resolve um problema bem definido e tem tamanho revisável
- [ ] As mudanças estão na camada correta (domain / application / infrastructure / pipelines / config)
- [ ] Nenhuma abstração, classe ou interface sem necessidade concreta
- [ ] Sem imports circulares nem dependência de `domain` para `infrastructure`
- [ ] Decisões arquiteturais relevantes estão descritas no PR ou em `docs/architecture.md`

**Dependências**
- [ ] Dependências novas foram adicionadas com `poetry add` (grupo correto) e justificadas
- [ ] `poetry.lock` foi atualizado junto com o `pyproject.toml`
- [ ] Nenhum uso de pip

**Código**
- [ ] Type hints e docstrings (Google) em APIs públicas
- [ ] `pathlib`, context managers e `logging` usados corretamente; sem `print` para observabilidade
- [ ] Exceções específicas, com causa preservada; sem `except` genérico silencioso
- [ ] Sem mutáveis como default; sem código morto ou comentado
- [ ] Sem `noqa`/`pragma: no cover` injustificados

**Dados e produção**
- [ ] Chamadas externas com timeout; retries limitados e só para erros transitórios
- [ ] Cargas idempotentes e transacionais quando aplicável
- [ ] Impacto em schemas, contratos e consumidores downstream avaliado
- [ ] Uso de memória adequado ao volume (lotes/streaming)
- [ ] Sem segredos ou PII em código, testes, logs ou docs

**Testes**
- [ ] Testes novos ou atualizados cobrem cenários positivo, negativo e limite
- [ ] Testes verificam resultados (asserts significativos) e não apenas executam código
- [ ] Mocks apenas nas fronteiras; testes unitários sem rede ou credenciais
- [ ] Nenhum teste removido, enfraquecido ou marcado como `skip` sem justificativa

**Documentação**
- [ ] Documentação atualizada quando muda comportamento, configuração, variáveis de ambiente ou forma de execução

**Validação (com evidência)**
- [ ] `poetry check --lock`: ok
- [ ] `poetry run ruff check .`: ok
- [ ] `poetry run ruff format --check .`: ok
- [ ] `poetry run pytest`: ok, cobertura ≥ 50% (informar o percentual)
- [ ] `poetry run mkdocs build --strict`: ok
- [ ] Pipeline de CI verde
