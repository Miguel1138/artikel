"""Pergunta de esclarecimento: na faixa de confiança baixa o bot pergunta antes de agir.

Entre LIMIAR_ESCLARECIMENTO e LIMIAR_CONFIANCA a resposta é "você quer X?", com as ações
como opções; a ação só roda depois do "sim" (ou do botão), sobre a pergunta original. Abaixo
da faixa, ou sem ação plausível para oferecer, a abstenção continua valendo.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))
sys.path.insert(0, str(RAIZ / "tests"))

import abstencao  # noqa: E402
import contexto  # noqa: E402
import fluxo  # noqa: E402
import intencoes  # noqa: E402
import recuperacao  # noqa: E402
from config import LIMIAR_CONFIANCA, LIMIAR_ESCLARECIMENTO  # noqa: E402
from test_fluxo import ARTIGOS, ClassificadorFalso, ambiente  # noqa: E402,F401


class ClassificadorIndeciso:
    """Devolve sempre as mesmas probabilidades, para posicionar a mensagem na faixa."""

    carregado = True

    def __init__(self, **probs):
        self.probs = {"buscar_referencias": 0.0, "avaliar_fonte": 0.0, "formatar_referencia": 0.0,
                      "orientar_busca": 0.0, "fora_de_escopo": 0.0, **probs}

    def prever(self, texto):
        intencao = max(self.probs, key=self.probs.get)
        return intencao, self.probs[intencao]

    def probabilidades(self, texto):
        return dict(self.probs)


@pytest.fixture
def indeciso(ambiente, monkeypatch):
    def usar(**probs):
        monkeypatch.setattr(intencoes, "obter", lambda: ClassificadorIndeciso(**probs))
    return usar


def test_confianca_na_faixa_pergunta_antes_de_buscar(indeciso):
    indeciso(buscar_referencias=0.45, fora_de_escopo=0.30)
    r = fluxo.responder("clareamento dental em adultos jovens", sessao="e1")
    assert r.tipo == "esclarecimento"
    assert not r.artigos, "o esclarecimento não pode recomendar antes do sim"
    assert "clareamento dental em adultos jovens" in r.resposta
    assert r.sugestoes == ["Procurar artigos sobre isso", abstencao.NAO_E_ISSO]
    assert r.traco.acao == "esclarecimento" and r.traco.confianca_abaixo_do_limiar


@pytest.mark.parametrize("confirmacao", ["sim", "Sim!", "isso mesmo", "pode ser", "1", "Procurar artigos sobre isso"])
def test_sim_executa_a_busca_da_pergunta_original(indeciso, confirmacao):
    indeciso(buscar_referencias=0.45, fora_de_escopo=0.30)
    fluxo.responder("clareamento dental em adultos jovens", sessao="e2")
    r = fluxo.responder(confirmacao, sessao="e2")
    assert r.tipo == "recomendacao" and r.artigos
    assert {a.id for a in r.artigos} <= {a["id"] for a in ARTIGOS}
    assert "confirmado pelo usuário" in r.traco.regra
    assert r.traco.contexto_usado


def test_duas_acoes_proximas_viram_duas_opcoes(indeciso):
    indeciso(buscar_referencias=0.50, orientar_busca=0.40)
    r = fluxo.responder("palavras-chave para achar artigos de clareamento", sessao="e3")
    assert r.tipo == "esclarecimento"
    assert r.sugestoes == ["Procurar artigos sobre isso", "Dicas de como buscar", abstencao.NAO_E_ISSO]
    escolhida = fluxo.responder("Dicas de como buscar", sessao="e3")
    assert escolhida.intencao == "orientar_busca"
    assert escolhida.tipo in ("orientacao_busca", "abstencao")   # depende da FAQ sintética
    assert "confirmado pelo usuário" in escolhida.traco.regra


def test_segunda_opcao_fraca_nao_entra(indeciso):
    indeciso(buscar_referencias=0.50, orientar_busca=0.15, fora_de_escopo=0.35)
    r = fluxo.responder("clareamento em adultos", sessao="e4")
    assert r.sugestoes == ["Procurar artigos sobre isso", abstencao.NAO_E_ISSO]


def test_nao_recusa_sem_agir(indeciso):
    indeciso(buscar_referencias=0.45, fora_de_escopo=0.30)
    fluxo.responder("clareamento dental em adultos jovens", sessao="e5")
    r = fluxo.responder("não", sessao="e5")
    assert r.tipo == "abstencao" and not r.artigos
    assert r.resposta == abstencao.RECUSA_ESCLARECIMENTO
    assert r.traco.regra == "esclarecimento recusado pelo usuário"


def test_pergunta_nova_descarta_o_esclarecimento(indeciso, monkeypatch):
    indeciso(buscar_referencias=0.45, fora_de_escopo=0.30)
    fluxo.responder("clareamento dental em adultos jovens", sessao="e6")
    monkeypatch.setattr(intencoes, "obter", lambda: ClassificadorFalso())
    r = fluxo.responder("a revista Brazilian Oral Research é confiável?", sessao="e6")
    assert r.tipo == "parecer_fonte"
    # e o "sim" seguinte já não confirma a busca antiga
    assert contexto.sessoes.obter("e6").esclarecimento is None


def test_esclarecimento_vale_uma_mensagem_so(indeciso):
    indeciso(buscar_referencias=0.45, fora_de_escopo=0.30)
    fluxo.responder("clareamento dental em adultos jovens", sessao="e7")
    fluxo.responder("sim", sessao="e7")
    assert contexto.sessoes.obter("e7").esclarecimento is None


def test_abaixo_da_faixa_continua_abstendo(indeciso):
    indeciso(buscar_referencias=LIMIAR_ESCLARECIMENTO - 0.05, fora_de_escopo=0.20)
    r = fluxo.responder("zorblax quântico", sessao="e8")
    assert r.tipo == "abstencao"
    assert contexto.sessoes.obter("e8").esclarecimento is None


def test_acima_do_limiar_age_direto(indeciso):
    indeciso(buscar_referencias=LIMIAR_CONFIANCA + 0.05)
    r = fluxo.responder("preciso de artigos sobre clareamento dental", sessao="e9")
    assert r.tipo == "recomendacao"


@pytest.mark.parametrize("busca", [0.20, 0.48])
def test_fora_de_escopo_previsto_nunca_pergunta(indeciso, busca):
    """Mesmo com a busca logo atrás ("escreve sobre depressão": 0,51 x 0,48), pedido de escrita se abstém."""
    indeciso(fora_de_escopo=0.51, buscar_referencias=busca)
    r = fluxo.responder("escreve sobre clareamento dental", sessao=f"e10-{busca}")
    assert r.tipo == "abstencao" and not r.artigos


def test_referencia_so_e_oferecida_com_artigo_na_lista(indeciso, monkeypatch):
    """Sem lista, "sim" levaria a outra abstenção: melhor abster direto."""
    indeciso(formatar_referencia=0.45, fora_de_escopo=0.40)
    r = fluxo.responder("e a do terceiro", sessao="e12")
    assert r.tipo == "abstencao"

    monkeypatch.setattr(intencoes, "obter", lambda: ClassificadorFalso())
    fluxo.responder("preciso de artigos sobre clareamento dental", sessao="e13")
    indeciso(formatar_referencia=0.45, fora_de_escopo=0.40)
    r = fluxo.responder("e a do segundo", sessao="e13")
    assert r.tipo == "esclarecimento"
    assert r.sugestoes[0] == "Referência ABNT do artigo 2"
    ref = fluxo.responder("sim", sessao="e13")
    assert ref.tipo == "referencia_abnt"


def test_limpar_sessao_apaga_o_esclarecimento(indeciso):
    indeciso(buscar_referencias=0.45, fora_de_escopo=0.30)
    fluxo.responder("clareamento dental em adultos jovens", sessao="e14")
    contexto.sessoes.obter("e14").limpar()
    r = fluxo.responder("sim", sessao="e14")
    assert r.tipo == "abstencao" and r.resposta == abstencao.SEM_PERGUNTA_PENDENTE


@pytest.mark.parametrize("mensagem", ["sim", "ok", "não", "pode ser"])
def test_sim_sem_pergunta_em_aberto_nao_vira_busca(ambiente, monkeypatch, mensagem):
    """Na base real "sim" aparece em vários artigos: sem esta trava virava tema solto."""
    monkeypatch.setattr(recuperacao.obter(), "so_tema", lambda texto: True, raising=False)
    r = fluxo.responder(mensagem, sessao="e15")
    assert not r.artigos and r.traco.regra == "resposta curta sem pergunta em aberto"


def test_pedido_que_comeca_com_quero_continua_sendo_pedido(ambiente):
    assert not contexto.resposta_curta("quero artigos sobre clareamento dental")
    r = fluxo.responder("quero artigos sobre clareamento dental", sessao="e16")
    assert r.tipo == "recomendacao"


@pytest.mark.parametrize("mensagem,assunto", [
    ("Que palavras-chave uso para achar artigos sobre cárie infantil?", "cárie infantil"),
    ("bactérias resistentes a antibióticos", "bactérias resistentes a antibióticos"),
    ("quais bases de dados são melhores para psicologia?", None),
])
def test_assunto_citado_na_pergunta(mensagem, assunto):
    assert fluxo._assunto(mensagem) == assunto


@pytest.mark.parametrize("mensagem,esperado", [
    ("sim", "buscar_referencias"),
    ("s", "buscar_referencias"),
    ("2", "orientar_busca"),
    ("Dicas de como buscar", "orientar_busca"),
    ("nao", ""),
    ("Não, é outra coisa", ""),
    ("sim, por favor", "buscar_referencias"),
    ("não é isso", ""),
    ("sim, mas sobre crianças com cárie", None),   # mensagem com conteúdo é pergunta nova
    ("quero artigos sobre cárie", None),
    ("não sei", None),
    ("cárie", None),
    ("3", None),
])
def test_resolver_resposta_curta(mensagem, esperado):
    pendente = contexto.Esclarecimento(
        "x", [("buscar_referencias", "Procurar artigos sobre isso"), ("orientar_busca", "Dicas de como buscar")], 0.5)
    assert pendente.resolver(mensagem) == esperado
