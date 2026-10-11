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


def test_cobertura_nao_depende_da_ordem_dos_termos(dir_temporario):
    """A cobertura decide se o artigo passa do limiar, então não pode ter ruído.

    Os termos vêm de um `set`, e a ordem de um set de strings muda a cada processo (hash
    randomization). Somar float nessa ordem dava resultados diferentes para a mesma
    pergunta: a Precisão@5 do relatório oscilava entre 0,657 e 0,743.
    """
    motor = montar_motor(dir_temporario)
    consulta = "queria uma lista de referências sobre clareamento dental"

    # Mesmo conjunto de termos, ordens de iteração diferentes: o valor tem de ser igual.
    valores = {
        motor._cobertura(consulta, ARTIGO_BOM, set(permutacao))
        for permutacao in (["clareamento", "dental"], ["dental", "clareamento"])
    }
    assert len(valores) == 1, f"cobertura variou com a ordem: {valores}"


def test_busca_e_repetivel(dir_temporario):
    """A mesma consulta, na mesma base, devolve exatamente a mesma lista e ordem."""
    motor = montar_motor(dir_temporario)
    primeira = [(c.artigo["id"], c.score) for c in motor.buscar("clareamento dental")]
    for _ in range(5):
        assert [(c.artigo["id"], c.score) for c in motor.buscar("clareamento dental")] == primeira


# ------------------------------------------------------------------ caso reportado
def test_consulta_sem_nenhum_termo_na_base_se_abstem():
    """Computação quântica não existe na base: o correto é não recomendar nada.

    Bug relatado: a busca devolvia artigos de Psicologia e Odontologia. O bônus de
    curadoria (indexado + recente = 0,08) somava por cima de uma similaridade de 0,06 e
    levava o artigo a 0,14, acima do limiar de score — inclusive artigos com **nenhuma**
    palavra da pergunta.
    """
    motor = recuperacao.obter()
    if not motor.pronto:
        pytest.skip("base curada indisponível")

    for consulta in ("preciso de artigos sobre computação quântica",
                     "quero artigos sobre computação quântica",
                     "tem estudos recentes sobre computação quântica?"):
        candidatos = motor.buscar(consulta, k=5)
        assert candidatos == [], (
            f"{consulta!r} devolveu {len(candidatos)} artigo(s): "
            + "; ".join(c.artigo.get("titulo", "")[:50] for c in candidatos)
        )


def test_bonus_de_curadoria_nao_substitui_relevancia():
    """Artigo sem nenhum termo da pergunta não pode passar, por mais indexado que seja."""
    motor = recuperacao.obter()
    if not motor.pronto:
        pytest.skip("base curada indisponível")

    consulta = "astrofísica de neutrinos"
    termos = motor._termos_consulta(consulta)
    candidatos = motor.buscar(consulta, k=5)
    for candidato in candidatos:
        assert motor._cobertura(consulta, candidato.artigo, termos) > 0, (
            "candidato recomendado sem nenhum termo da pergunta: "
            f"{candidato.artigo.get('titulo', '')[:60]} (score {candidato.score})"
        )


def test_termo_curto_nao_casa_com_palavra_de_outro_radical(dir_temporario):
    """'quântica' não pode casar com 'quantitative'.

    O casamento cortava a palavra em 5 letras (`quant`) e aceitava qualquer início de
    palavra: "quantitative methods", num artigo de Psicologia, contava como cobertura de
    computação quântica.
    """
    motor = montar_motor(dir_temporario)
    assert not motor._contem("students using snowball sampling quantitative", "quantica")
    assert not motor._contem("high emotional and high quantitative demands", "quantica")
    assert motor._contem("computacao quantica aplicada", "quantica")
    assert motor._contem("quantum computing", "quantum")


def test_termo_casa_com_flexao_simples(dir_temporario):
    """A flexão de número e gênero continua casando (senão a busca perderia recall)."""
    motor = montar_motor(dir_temporario)
    assert motor._contem("caries infantil", "carie")
    assert motor._contem("caries", "caries")
    assert motor._contem("estudantes universitarios", "universitarios")
    assert motor._contem("estudante universitario", "universitario")
    assert motor._contem("clareamento dental", "dental")
    assert not motor._contem("dentistry", "dental"), "sinônimo é papel de ALIASES, não do radical"
