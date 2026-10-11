"""Configuração comum do pytest.

- Coloca `app/` no caminho de importação (é assim que a API e os scripts importam).
- Define a fixture `dir_temporario`: diretório de apoio dentro de `tests/`, já que o
  diretório temporário do sistema não é utilizável neste ambiente. Os arquivos são
  apagados no fim de cada teste.
"""
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent

for caminho in (RAIZ, RAIZ / "app", RAIZ / "scripts", RAIZ / "scripts" / "coleta"):
    if str(caminho) not in sys.path:
        sys.path.insert(0, str(caminho))

DIR_APOIO = RAIZ / "tests" / "_temporario"


@pytest.fixture
def dir_temporario():
    """Pasta de apoio por teste, dentro do repositório e sempre limpa no final."""
    if DIR_APOIO.exists():
        shutil.rmtree(DIR_APOIO, ignore_errors=True)
    DIR_APOIO.mkdir(parents=True, exist_ok=True)
    try:
        yield DIR_APOIO
    finally:
        shutil.rmtree(DIR_APOIO, ignore_errors=True)
