"""Regra do tema solto: uma palavra de assunto ("depressão") é uma busca.

O classificador decide pela palavra e, para um substantivo sem verbo, errava: "ansiedade" e
"cárie" iam para fora_de_escopo porque aparecem em perguntas clínicas do treino. A regra usa
a evidência da base (o tema existe em vários artigos) e tem travas para não transformar em
busca o vocabulário do próprio sistema ("scielo"), pedidos fora de escopo ("faz minha
introdução sobre cárie") ou menções incidentais.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import fluxo  # noqa: E402
import recuperacao  # noqa: E402
from config import ARQ_BASE  # noqa: E402

pytestmark = pytest.mark.skipif(not ARQ_BASE.exists(), reason="base ausente")


def buscar(mensagem):
    return fluxo.responder(mensagem, "tema-solto-teste")


@pytest.mark.parametrize("tema", ["depressão", "ansiedade", "cárie", "periodontia", "clareamento", "suicídio", "pandemia"])
def test_tema_solto_da_base_vira_busca(tema):
    r = buscar(tema)
    assert r.artigos, f"{tema!r} deveria buscar (intenção do modelo: {r.traco.intencao_prevista})"
    assert "tema solto" in r.traco.regra or r.traco.intencao_prevista == "buscar_referencias"


@pytest.mark.parametrize("palavra", ["scielo", "pubmed", "capes", "abnt", "periódico", "revista", "wikipedia"])
def test_palavra_do_sistema_nao_vira_busca(palavra):
    """O risco de uma regra de tema solto: 'scielo' está em 8 artigos, mas é outra ação."""
    assert not buscar(palavra).artigos


@pytest.mark.parametrize("pedido", ["e a do terceiro", "e a do segundo", "e a do quarto", "e a do último"])
def test_ordinal_de_artigo_indicado_nao_vira_busca(pedido):
    """Regressão: com 2895 artigos, 'terceiro' aparece em vários resumos e virava tema solto."""
    assert not recuperacao.obter().so_tema(pedido)
    assert "tema solto" not in buscar(pedido).traco.regra


@pytest.mark.parametrize("pedido", [
    "faz minha introdução sobre cárie",
    "escreve sobre depressão",
    "qual remédio tomar para ansiedade",
    "me diz se ansiedade tem cura",
    "resuma depressão",
])
def test_pedido_fora_de_escopo_com_tema_continua_abstendo(pedido):
    r = buscar(pedido)
    assert not r.artigos and r.tipo == "abstencao"


@pytest.mark.parametrize("assunto", ["astronomia", "futebol", "geologia", "física quântica", "xadrez", "direito penal"])
def test_assunto_fora_da_base_nao_busca(assunto):
    assert not buscar(assunto).artigos


def test_mencao_unica_nao_e_tema():
    """'psicólogo' e 'religião' aparecem em um só artigo (incidental): não viram busca.

    'música' era o exemplo até a base crescer para 5 áreas; hoje está em mais de um artigo.
    """
    motor = recuperacao.obter()
    assert not motor.so_tema("psicólogo")
    assert not motor.so_tema("religião")
    assert motor.so_tema("depressão")


def test_mensagem_longa_ou_vazia_de_tema_nao_e_tema_solto():
    motor = recuperacao.obter()
    assert not motor.so_tema("")
    assert not motor.so_tema("de que em para")                      # só palavras funcionais
    assert not motor.so_tema("depressão ansiedade cárie periodontia implantes")   # acima de MAX_TERMOS_TEMA


def test_acao_confiante_do_modelo_prevalece():
    """Pedido claro de outra ação não é reinterpretado como busca só por citar um tema."""
    r = buscar("como faço a referência ABNT do artigo sobre depressão?")
    assert "tema solto" not in r.traco.regra
    assert r.intencao == r.traco.intencao_prevista
