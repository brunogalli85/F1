"""Configurações da aplicação carregadas do ambiente."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.openf1.org/v1"
DEFAULT_DB_PATH = Path("data/f1.duckdb")


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuração imutável da aplicação."""

    openf1_base_url: str = DEFAULT_BASE_URL
    db_path: Path = DEFAULT_DB_PATH
    http_timeout_s: float = 30.0
    min_request_interval_s: float = 0.5

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Cria as configurações a partir de variáveis de ambiente.

        Variáveis ausentes ou vazias usam o valor padrão.

        Args:
            environ: Mapeamento de variáveis; por padrão, `os.environ`.

        Raises:
            ValueError: Se uma variável tiver valor inválido.
        """
        env = os.environ if environ is None else environ
        return cls(
            openf1_base_url=env.get("OPENF1_BASE_URL") or DEFAULT_BASE_URL,
            db_path=Path(env.get("F1_DB_PATH") or DEFAULT_DB_PATH),
            http_timeout_s=_positive_float(env, "HTTP_TIMEOUT_S", 30.0, allow_zero=False),
            min_request_interval_s=_positive_float(
                env, "OPENF1_MIN_INTERVAL_S", 0.5, allow_zero=True
            ),
        )


def _positive_float(
    env: Mapping[str, str], name: str, default: float, *, allow_zero: bool
) -> float:
    raw = env.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} precisa ser um número, recebido {raw!r}") from exc
    if value < 0 or (value == 0 and not allow_zero):
        limit = ">= 0" if allow_zero else "> 0"
        raise ValueError(f"{name} precisa ser {limit}, recebido {raw!r}")
    return value
