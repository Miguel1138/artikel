"""Testes do parecer sobre fonte (`avaliar_fonte`) e da recuperação com curadoria (R3).

Usa uma base sintética em memória: a decisão "não consta na base" e o bônus de curadoria
precisam de teste que não dependa da coleta ter rodado.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import periodicos as modulo_periodicos  # noqa: E402
import recuperacao  # noqa: E402


ARTIGO_BOM = {
    "id": "art_001",
    "doi": "10.1590/exemplo",
    "titulo": "Clareamento dental em adultos: revisão",
    "autores": [{"sobrenome": "Silva", "nome": "Ana"}],
    "ano": 2024,
    "periodico": "Brazilian Oral Research",
    "issn": ["1807-3107"],
    "resumo": "Estudo sobre clareamento dental e sensibilidade.",
    "palavras_chave": ["clareamento dental", "sensibilidade"],
    "idioma": "pt",
    "licenca": "cc-by",
    "area": "odontologia",
    "fonte": "scielo",
    "url": "https://doi.org/10.1590/exemplo",
}


def montar_motor(pasta: Path) -> recuperacao.Motor:
    base = pasta / "knowledge_base.json"
    revistas = pasta / "periodicos.json"
    base.write_text(json.dumps([ARTIGO_BOM], ensure_ascii=False), encoding="utf-8")
    revistas.write_text(json.dumps([{
        "titulo": "Brazilian Oral Research",
        "issn": ["1807-3107"],
        "indexacao": ["DOAJ", "SciELO", "MEDLINE"],
        "assuntos": ["DENTISTRY"],
        "revisao": ["dupla_cega"],
        "licenca": "cc-by",
        "url": "https://www.scielo.br/bor",
    }], ensure_ascii=False), encoding="utf-8")
    return recuperacao.Motor(base, revistas)


def test_parecer_de_periodico_conhecido(dir_temporario):
    motor = montar_motor(dir_temporario)
    parecer = modulo_periodicos.avaliar("A revista Brazilian Oral Research é confiável?", motor)
    assert parecer["encontrado"] is True
    assert parecer["tipo"] == "periodico"
    assert "DOAJ" in parecer["indexacao"]
    assert "dupla_cega" in parecer["revisao"]
    assert "indexação" in parecer["explicacao"]


def test_parecer_por_issn(dir_temporario):
    motor = montar_motor(dir_temporario)
    parecer = modulo_periodicos.avaliar("o ISSN 1807-3107 é confiável", motor)
    assert parecer["encontrado"] is True
    assert parecer["titulo"] == "Brazilian Oral Research"


def test_fonte_desconhecida_nao_consta_na_base(dir_temporario):
    motor = montar_motor(dir_temporario)
    parecer = modulo_periodicos.avaliar("A revista Journal of Nothing é confiável?", motor)
    assert parecer["encontrado"] is False
    assert "não consta na base" in parecer["explicacao"].lower()


def test_wikipedia_tem_parecer_proprio(dir_temporario):
    motor = montar_motor(dir_temporario)
    parecer = modulo_periodicos.avaliar("Posso citar a Wikipédia no meu TCC?", motor)
    assert parecer["encontrado"] is True
    assert parecer["tipo"] == "generica"
    assert "revisão por pares" in parecer["explicacao"]


def test_busca_acha_artigo_e_usa_curadoria(dir_temporario):
    motor = montar_motor(dir_temporario)
    candidatos = motor.buscar("clareamento dental", k=5)
    assert candidatos, "a busca deveria encontrar o artigo da base"
    assert candidatos[0].artigo["id"] == "art_001"
    assert candidatos[0].score >= candidatos[0].similaridade      # bônus somou
    assert any("pares" in m for m in candidatos[0].motivos)
    assert any("DOAJ" in m for m in candidatos[0].motivos)


def test_busca_fora_do_tema_nao_traz_candidato(dir_temporario):
    motor = montar_motor(dir_temporario)
    assert motor.buscar("mineração de dados astronômicos", k=5) == []


def test_detetar_area(dir_temporario):
    motor = montar_motor(dir_temporario)
    assert motor.detetar_area("preciso de artigos sobre clareamento dental") == "odontologia"
    assert motor.detetar_area("artigos sobre ansiedade em universitários") == "psicologia"
    assert motor.detetar_area("aprendizado de máquina em saúde") == "computacao"
    assert motor.detetar_area("bom dia") is None


def test_base_ausente_nao_quebra(dir_temporario):
    motor = recuperacao.Motor(dir_temporario / "inexistente.json",
                              dir_temporario / "inexistente2.json")
    assert not motor.pronto
    assert motor.erro and "pipeline" in motor.erro
    assert motor.buscar("qualquer coisa") == []
