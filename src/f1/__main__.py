"""Entrypoint da CLI: `f1 ...` ou `python -m f1 ...`."""

import logging
import sys
from collections.abc import Sequence

import duckdb

from f1 import cli
from f1.infrastructure.openf1_client import OpenF1Error
from f1.pipelines.sync import SyncError

logger = logging.getLogger("f1")


def main(argv: Sequence[str] | None = None) -> int:
    """Configura o logging, executa a CLI e converte erros em código de saída."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    # O httpx registra cada requisição em INFO; os logs do cliente já cobrem o que importa.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        return cli.main(argv)
    except (cli.CliError, OpenF1Error, SyncError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    except duckdb.IOException as exc:
        logger.error("não foi possível abrir o banco DuckDB: %s", exc)
        return 1
    except Exception:
        logger.exception("erro inesperado")
        return 1


if __name__ == "__main__":
    sys.exit(main())
