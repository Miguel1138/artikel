"""Testes do contexto de conversa (R1: memória da última lista exibida)."""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import contexto  # noqa: E402


def tres_artigos():
    return [{"id": f"art_{i:03d}", "titulo": f"Artigo {i}"} for i in (1, 2, 3)]


def test_posicao_por_ordinal_e_digito():
    ctx = contexto.Contexto()
    ctx.guardar_artigos(tres_artigos())
    assert ctx.posicao("me dá a referência do segundo artigo") == 2
    assert ctx.posicao("formata a do 3") == 3
    assert ctx.posicao("o primeiro da lista") == 1
    assert ctx.posicao("qualquer outra coisa") is None


def test_ultimo_e_penultimo_dependem_do_tamanho():
    ctx = contexto.Contexto()
    ctx.guardar_artigos(tres_artigos())
    assert ctx.posicao("referência do último artigo") == 3
    assert ctx.posicao("referência do penúltimo artigo") == 2


def test_artigo_citado_resolve_posicao():
    ctx = contexto.Contexto()
    ctx.guardar_artigos(tres_artigos())
    assert ctx.artigo_citado("a referência do segundo artigo")["id"] == "art_002"


def test_posicao_fora_da_lista_devolve_none():
    ctx = contexto.Contexto()
    ctx.guardar_artigos(tres_artigos())
    assert ctx.artigo_citado("referência do nono artigo") is None


def test_sem_lista_nao_resolve():
    ctx = contexto.Contexto()
    assert ctx.artigo_citado("referência do segundo artigo") is None
    assert not ctx.tem_artigos


def test_contexto_expira():
    ctx = contexto.Contexto()
    ctx.guardar_artigos(tres_artigos())
    assert ctx.tem_artigos
    ctx.atualizado_em = time.time() - contexto.TTL - 1
    assert ctx.expirado()
    assert not ctx.tem_artigos
    assert ctx.artigo_citado("o segundo artigo") is None


def test_frase_sem_referencia_a_lista():
    ctx = contexto.Contexto()
    ctx.guardar_artigos(tres_artigos())
    assert not ctx.cita_lista("preciso de artigos sobre cárie")
    assert ctx.cita_lista("e a do terceiro")


def test_sessoes_sao_isoladas():
    sessoes = contexto.Sessoes()
    a, b = sessoes.obter("a"), sessoes.obter("b")
    a.guardar_artigos(tres_artigos())
    assert a.tem_artigos and not b.tem_artigos
    sessoes.limpar("a")
    assert not sessoes.obter("a").tem_artigos


def test_limite_de_sessoes_descarta_a_mais_antiga():
    sessoes = contexto.Sessoes(maximo=3)
    for nome in ("a", "b", "c"):
        sessoes.obter(nome).atualizado_em = time.time()
    sessoes.obter("a").atualizado_em = time.time() - 100   # "a" é a mais antiga
    sessoes.obter("d")
    assert "a" not in sessoes._dados
    assert "d" in sessoes._dados
