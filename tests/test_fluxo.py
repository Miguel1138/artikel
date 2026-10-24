"""Testes de ponta a ponta do fluxo (R4) com base e modelo sintéticos.

Aqui o objetivo não é medir qualidade (isso é `tests/avaliar.py`), e sim garantir os
invariantes que o documento exige: abstenção no lugar de invenção, contexto de "o segundo
artigo" e traço da decisão em toda resposta.
"""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import contexto  # noqa: E402
import faq as modulo_faq  # noqa: E402
import fluxo  # noqa: E402
import intencoes  # noqa: E402
import recuperacao  # noqa: E402
from config import ABSTENCOES_ANTES_DE_REPETIR  # noqa: E402


class ClassificadorFalso:
    """Devolve a intenção por palavra-chave, com confiança controlada pelo teste."""

    carregado = True

    def __init__(self, confianca=0.9):
        self.confianca = confianca
        # Ordem importa: as chaves mais específicas vêm antes ("referência ABNT do segundo
        # artigo" contém "artigo" e precisa ser lida como pedido de referência).
        self.mapa = {
            "abnt": "formatar_referencia",
            "referencia": "formatar_referencia",
            "revista": "avaliar_fonte",
            "confiavel": "avaliar_fonte",
            "scielo": "orientar_busca",
            "palavras-chave": "orientar_busca",
            "procuro": "orientar_busca",
            "introducao": "fora_de_escopo",
            "escreve": "fora_de_escopo",
            "artigo": "buscar_referencias",
        }

    def prever(self, texto):
        import preprocessamento

        t = preprocessamento.sem_acento(texto).lower()
        for chave, intencao in self.mapa.items():
            if chave in t:
                return intencao, self.confianca
        return "fora_de_escopo", self.confianca


ARTIGOS = [
    {
        "id": "art_001", "doi": "10.1/a", "titulo": "Clareamento dental em adultos",
        "autores": [{"sobrenome": "Silva", "nome": "Ana"}], "ano": 2024,
        "periodico": "Brazilian Oral Research", "issn": ["1807-3107"],
        "resumo": "Clareamento dental e sensibilidade.", "palavras_chave": ["clareamento"],
        "idioma": "pt", "licenca": "cc-by", "area": "odontologia", "fonte": "scielo",
        "url": "https://doi.org/10.1/a",
    },
    {
        "id": "art_002", "doi": "10.1/b", "titulo": "Clareamento dental caseiro supervisionado",
        "autores": [{"sobrenome": "Souza", "nome": "Bruno"}], "ano": 2022,
        "periodico": "Brazilian Oral Research", "issn": ["1807-3107"],
        "resumo": "Clareamento dental caseiro e efeitos na sensibilidade.",
        "palavras_chave": ["clareamento dental"],
        "idioma": "pt", "licenca": "cc-by", "area": "odontologia", "fonte": "scielo",
        "url": "https://doi.org/10.1/b",
    },
    {
        "id": "art_003", "doi": "10.1/c", "titulo": "Fluoretação e saúde bucal coletiva",
        "autores": [{"sobrenome": "Lima", "nome": "Carla"}], "ano": 2021,
        "periodico": "Brazilian Oral Research", "issn": ["1807-3107"],
        "resumo": "Fluoretação da água e saúde bucal.", "palavras_chave": ["flúor"],
        "idioma": "pt", "licenca": "cc-by", "area": "odontologia", "fonte": "scielo",
        "url": "https://doi.org/10.1/c",
    },
]

PERIODICOS = [{
    "titulo": "Brazilian Oral Research", "issn": ["1807-3107"],
    "indexacao": ["DOAJ", "SciELO"], "assuntos": ["DENTISTRY"],
    "revisao": ["dupla_cega"], "licenca": "cc-by", "url": "https://www.scielo.br/bor",
}]

FAQ = {
    "versao": "teste",
    "entradas": [{
        "id": "faq_scielo", "titulo": "Como procuro artigos no SciELO",
        "perguntas": ["como procuro artigos no scielo"],
        "areas": ["todas"], "tags": ["scielo", "busca"],
        "resposta": "Use search.scielo.org com termos em português.",
        "passos": ["Digite os termos", "Filtre por ano"],
    }],
}


@pytest.fixture
def ambiente(dir_temporario, monkeypatch):
    base = dir_temporario / "knowledge_base.json"
    revistas = dir_temporario / "periodicos.json"
    faq = dir_temporario / "faq_busca.json"
    base.write_text(json.dumps(ARTIGOS, ensure_ascii=False), encoding="utf-8")
    revistas.write_text(json.dumps(PERIODICOS, ensure_ascii=False), encoding="utf-8")
    faq.write_text(json.dumps(FAQ, ensure_ascii=False), encoding="utf-8")

    motor = recuperacao.Motor(base, revistas)
    base_faq = modulo_faq.Faq(faq)
    monkeypatch.setattr(recuperacao, "obter", lambda: motor)
    monkeypatch.setattr(modulo_faq, "obter", lambda: base_faq)
    monkeypatch.setattr(intencoes, "obter", lambda: ClassificadorFalso())
    monkeypatch.setattr(contexto, "sessoes", contexto.Sessoes())
    monkeypatch.setattr(fluxo, "sessoes", contexto.sessoes)
    return motor


def test_busca_recomenda_apenas_registros_da_base(ambiente):
    r = fluxo.responder("preciso de artigos sobre clareamento dental", sessao="t1")
    assert r.tipo == "recomendacao"
    assert r.artigos, "deveria recomendar pelo menos um artigo"
    ids_base = {a["id"] for a in ARTIGOS}
    assert all(a.id in ids_base for a in r.artigos)
    assert r.traco.acao == "recomendar"
    assert r.artigos[0].referencia_abnt.startswith("SILVA, Ana.")


def test_busca_fora_do_tema_se_abstem(ambiente):
    """Nenhum artigo do tema pedido: a resposta correta é abster, não recomendar o que sobrou."""
    r = fluxo.responder("preciso de artigos sobre astrofísica de neutrinos", sessao="t2")
    assert r.tipo == "abstencao"
    assert not r.artigos
    assert r.traco.regra in ("similaridade+curadoria >= 0.1", "cobertura temática mínima")


def test_contexto_resolve_segundo_artigo(ambiente):
    fluxo.responder("preciso de artigos sobre clareamento dental", sessao="t3")
    r = fluxo.responder("me dá a referência ABNT do segundo artigo", sessao="t3")
    assert r.tipo == "referencia_abnt"
    assert r.traco.contexto_usado is True
    assert r.artigos[0].id == ARTIGOS[1]["id"]


def test_referencia_sem_contexto_se_abstem(ambiente):
    r = fluxo.responder("me dá a referência ABNT do segundo artigo", sessao="t4")
    assert r.tipo == "abstencao"
    assert r.traco.regra == "sem contexto de lista"


def test_parecer_de_fonte_conhecida(ambiente):
    r = fluxo.responder("a revista Brazilian Oral Research é confiável?", sessao="t5")
    assert r.tipo == "parecer_fonte"
    assert any("DOAJ" in f for f in r.fontes)


def test_parecer_de_fonte_desconhecida(ambiente):
    r = fluxo.responder("a revista Journal of Nothing é confiável?", sessao="t6")
    assert r.tipo == "parecer_fonte"
    assert "não consta na base" in r.fontes[0].lower()


def test_orientacao_de_busca_vem_da_faq(ambiente):
    r = fluxo.responder("como procuro artigos no SciELO?", sessao="t7")
    assert r.tipo == "orientacao_busca"
    assert "search.scielo.org" in r.resposta
    assert "1. Digite os termos" in r.resposta


def test_fora_de_escopo_se_abstem_e_encaminha(ambiente):
    r = fluxo.responder("escreve minha introdução", sessao="t8")
    assert r.tipo == "abstencao"
    assert r.traco.regra == "intenção fora de escopo"
    assert r.sugestoes, "a abstenção precisa oferecer o que o bot sabe fazer"
    # A primeira abstenção é curta; a mensagem completa (com o encaminhamento ao
    # orientador) volta depois de ABSTENCOES_ANTES_DE_REPETIR seguidas.
    for _ in range(ABSTENCOES_ANTES_DE_REPETIR):
        r = fluxo.responder("escreve minha introdução", sessao="t8")
    assert "orientador" in r.resposta
    assert "escopo" in r.resposta


def test_toda_resposta_tem_traco(ambiente):
    for pergunta in ("preciso de artigos sobre clareamento",
                     "a revista X é confiável?",
                     "escreve minha introdução"):
        r = fluxo.responder(pergunta, sessao="t9")
        assert r.traco.intencao_prevista
        assert r.traco.acao
        assert r.traco.regra


def test_confianca_baixa_vira_abstencao(ambiente, monkeypatch):
    """Mensagem com palavra que a base não conhece não é "só um tema": vale o limiar."""
    monkeypatch.setattr(intencoes, "obter", lambda: ClassificadorFalso(confianca=0.1))
    r = fluxo.responder("preciso de artigos sobre zorblax", sessao="t10")
    assert r.tipo == "abstencao"
    assert r.traco.confianca_abaixo_do_limiar is True


def test_confianca_baixa_com_tema_reconhecido_pela_base_busca(ambiente, monkeypatch):
    """Tema solto: o classificador hesita, mas a base conhece o assunto (ver test_tema_solto.py)."""
    monkeypatch.setattr(intencoes, "obter", lambda: ClassificadorFalso(confianca=0.1))
    r = fluxo.responder("preciso de artigos sobre clareamento dental", sessao="t10b")
    assert r.tipo == "recomendacao" and r.artigos
    assert "tema solto" in r.traco.regra


def test_termos_do_traco_e_limiar_registrados(ambiente):
    r = fluxo.responder("preciso de artigos sobre clareamento dental", sessao="t11")
    assert r.traco.limiar_score is not None
    assert r.traco.score_maximo is not None
    assert r.traco.n_candidatos >= 1
