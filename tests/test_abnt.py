"""Testes das regras ABNT NBR 6023 (objetivo específico 4).

A meta do documento é 90% de referências corretas por conferência manual contra a norma.
Estes testes fixam os casos que a conferência manual já validou, para que uma mudança em
`abnt.py` não quebre o que estava certo.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import abnt  # noqa: E402
import pytest  # noqa: E402


ARTIGO_COMPLETO = {
    "autores": [
        {"sobrenome": "Silva", "nome": "João da"},
        {"sobrenome": "Souza", "nome": "Maria"},
    ],
    "titulo": "Aprendizado de máquina aplicado à saúde pública",
    "periodico": "Revista Brasileira de Informática em Saúde",
    "volume": "12",
    "numero": "3",
    "paginas": "45-67",
    "ano": 2023,
    "doi": "10.1234/rbis.2023.45",
    "url": "https://doi.org/10.1234/rbis.2023.45",
}


def test_referencia_completa():
    ref = abnt.formatar_referencia(ARTIGO_COMPLETO, "2026-10-11")
    assert ref.startswith("SILVA, João da; SOUZA, Maria. Aprendizado de máquina")
    assert "Revista Brasileira de Informática em Saúde, v. 12, n. 3, p. 45-67, 2023." in ref
    assert "DOI: 10.1234/rbis.2023.45." in ref
    assert ref.endswith("Acesso em: 11 out. 2026.")


def test_quatro_autores_usa_et_al():
    artigo = dict(ARTIGO_COMPLETO)
    artigo["autores"] = [
        {"sobrenome": "Alves", "nome": "Ana"},
        {"sobrenome": "Braga", "nome": "Bruno"},
        {"sobrenome": "Costa", "nome": "Caio"},
        {"sobrenome": "Dias", "nome": "Dora"},
    ]
    ref = abnt.formatar_referencia(artigo)
    assert ref.startswith("ALVES, Ana et al. Aprendizado")     # um ponto, não dois
    assert "et al.." not in ref
    assert "BRAGA" not in ref


def test_autor_cujo_nome_termina_em_abreviacao():
    """'SILVA, Matheus Corrêa Batista da.' não pode virar 'da..'."""
    artigo = dict(ARTIGO_COMPLETO)
    artigo["autores"] = [{"sobrenome": "Silva", "nome": "Matheus Corrêa Batista da"}]
    ref = abnt.formatar_referencia(artigo)
    assert "da. Aprendizado" in ref
    assert "da.." not in ref


def test_tres_autores_lista_todos():
    artigo = dict(ARTIGO_COMPLETO)
    artigo["autores"] = [
        {"sobrenome": "Alves", "nome": "Ana"},
        {"sobrenome": "Braga", "nome": "Bruno"},
        {"sobrenome": "Costa", "nome": "Caio"},
    ]
    ref = abnt.formatar_referencia(artigo)
    assert "ALVES, Ana; BRAGA, Bruno; COSTA, Caio." in ref


def test_sem_autor_nao_inventa():
    artigo = {"titulo": "Artigo sem autoria declarada", "periodico": "Revista X", "ano": 2021}
    ref = abnt.formatar_referencia(artigo)
    assert ref.startswith("Artigo sem autoria declarada.")
    assert "et al" not in ref


def test_campos_ausentes_sao_omitidos():
    artigo = {"autores": [{"sobrenome": "Lima", "nome": "Luís"}], "titulo": "Estudo curto",
              "periodico": "Cadernos", "ano": 2020}
    ref = abnt.formatar_referencia(artigo)
    assert "v." not in ref and "n." not in ref and "p." not in ref
    assert "Disponível em" not in ref and "Acesso em" not in ref
    assert ref == "LIMA, Luís. Estudo curto. Cadernos, 2020."


def test_doi_sem_url_nao_gera_disponivel_em():
    artigo = dict(ARTIGO_COMPLETO)
    artigo.pop("url")
    ref = abnt.formatar_referencia(artigo, "2026-10-11")
    assert "Disponível em" not in ref
    assert "Acesso em: 11 out. 2026." in ref


def test_autor_institucional():
    artigo = {"autores": [{"sobrenome": "Organização Mundial da Saúde", "nome": ""}],
              "titulo": "Relatório", "ano": 2022}
    assert abnt.formatar_referencia(artigo).startswith("ORGANIZAÇÃO MUNDIAL DA SAÚDE.")


@pytest.mark.parametrize(
    "iso,esperado",
    [("2026-10-11", "11 out. 2026"), ("2024-01-05", "5 jan. 2024"),
     ("2024-05-31", "31 maio 2024"), ("", ""), (None, ""), ("2024", "")],
)
def test_data_de_acesso(iso, esperado):
    assert abnt.formatar_data_acesso(iso) == esperado


def test_citacao_no_texto():
    assert abnt.formatar_curta(ARTIGO_COMPLETO) == "(SILVA, 2023)"
    artigo = dict(ARTIGO_COMPLETO)
    artigo["autores"] = artigo["autores"] * 3    # 6 autores
    assert abnt.formatar_curta(artigo) == "(SILVA et al., 2023)"


def test_autores_como_texto_simples():
    artigo = {"autores": ["Silva, João"], "titulo": "T", "ano": 2020}
    assert abnt.formatar_referencia(artigo).startswith("Silva, João. T.")
