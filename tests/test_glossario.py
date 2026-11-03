"""Testes do glossário pt<->en (OMW) e do que ele muda na recuperação. Rodam offline."""
import json
import math
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import glossario  # noqa: E402
import recuperacao  # noqa: E402
from config import ARQ_BASE, ARQ_GLOSSARIO  # noqa: E402
from preprocessamento import sem_acento  # noqa: E402


def test_equivalentes_basicos():
    assert "gingivitis" in glossario.equivalentes("gengivite")
    assert "whitening" in glossario.equivalentes("branqueamento")


def test_indice_e_simetrico():
    """Pergunta em inglês também acha o equivalente em português (há 40 artigos em pt)."""
    assert "gengivite" in glossario.equivalentes("gingivitis")


def test_plural_e_feminino_caem_na_forma_base():
    assert "testing" in glossario.equivalentes("testes")           # plural
    assert "depression" in glossario.equivalentes("depressiva")    # feminino
    assert "symptoms" in glossario.equivalentes("sintomas")
    assert "implant" in glossario.equivalentes("implante")


def test_termo_desconhecido_e_vazio():
    assert glossario.equivalentes("astrofisica") == frozenset()


def test_nao_traz_pares_de_polissemia_do_wordnet():
    """'pais' é país no WordNet; aqui só pode valer como 'pais e filhos'."""
    todos = {e for ens in json.loads(ARQ_GLOSSARIO.read_text(encoding="utf-8")).values() for e in ens}
    assert not {"country", "nation", "state", "run", "land"} & todos
    assert "country" not in glossario.equivalentes("pais")


def test_todo_lado_ingles_existe_na_base():
    """Se a base mudar, rode scripts/gerar_glossario.py: ele descarta o que sumiu."""
    if not ARQ_BASE.exists():
        pytest.skip("base ausente")
    texto = sem_acento(ARQ_BASE.read_text(encoding="utf-8")).lower()
    ausentes = [(pt, en) for pt, ens in json.loads(ARQ_GLOSSARIO.read_text(encoding="utf-8")).items()
                for en in ens if en not in texto]
    assert not ausentes, ausentes


def test_tema_que_a_base_nao_tem_fica_fora_do_glossario():
    """Par aprovado cujo lado inglês não está na base é descartado pelo gerador.

    O exemplo era 'obesidade', que saiu da lista quando Medicina entrou na base (21/10/2026).
    'aplicativo -> app' continua aprovado, mas "app" não aparece como palavra na base.
    """
    assert "app" not in glossario.equivalentes("aplicativo")
    assert glossario.equivalentes("obesidade") == frozenset({"obesity"})


# --- recuperação com uma base mínima, sem depender da base real -----------------------
def _artigo(i, texto):
    return {"id": f"a{i}", "doi": f"10.1/{i}", "titulo": f"Artigo {i}", "resumo": texto,
            "palavras_chave": [], "ano": 2024, "area": "teste", "issn": []}


@pytest.fixture
def motor(dir_temporario):
    textos = (
        ["comum zebrina quimera"] * 3                  # a0-a2: cobrem os dois termos
        + ["comum zebrina"]                            # a3: só o termo raro
        + [f"comum quimera outro{i}" for i in range(7)]  # a4-a10: só o termo comum
        + ["comum gingivitis"]                         # a11: só a forma em inglês do glossário
    )
    arq = dir_temporario / "base.json"
    arq.write_text(json.dumps([_artigo(i, t) for i, t in enumerate(textos)]), encoding="utf-8")
    return recuperacao.Motor(arq, dir_temporario / "sem_periodicos.json")


def test_peso_do_conceito_conta_os_artigos_com_qualquer_variante(motor):
    """'gengivite' (pt) e 'gingivitis' (en) são um conceito: o df é a união, não o máximo."""
    n = len(motor.artigos)
    assert motor._peso("gengivite") == pytest.approx(math.log((1 + n) / (1 + 1)) + 1)
    # termo sem equivalente: mesmo valor de antes (idf da própria palavra)
    assert motor._peso("zebrina") == pytest.approx(motor._idf["zebrina"])


def test_termo_inexistente_tem_peso_maximo(motor):
    assert motor._peso("astrofisica") == max(motor._idf.values())


def test_glossario_faz_a_pergunta_em_pt_achar_o_artigo_em_ingles(motor):
    ids = [c.artigo["id"] for c in motor.buscar("artigos sobre gengivite")]
    assert ids == ["a11"]


def test_cobertura_parcial_so_preenche_quando_faltam_completos(motor, monkeypatch):
    # com 3 artigos que cobrem os dois termos (a0-a2), o que só tem o termo raro (a3) sai
    monkeypatch.setattr(recuperacao, "MIN_COBERTURA_COMPLETA", 3)
    ids = {c.artigo["id"] for c in motor.buscar("zebrina quimera")}
    assert ids == {"a0", "a1", "a2"}
    # exigindo 4 completos (não há), a cobertura parcial volta a valer
    monkeypatch.setattr(recuperacao, "MIN_COBERTURA_COMPLETA", 4)
    ids = {c.artigo["id"] for c in motor.buscar("zebrina quimera")}
    assert {"a0", "a1", "a2", "a3"} <= ids


def test_palavra_funcional_e_de_enchimento_nao_entram_nos_termos():
    termos = recuperacao.Motor._termos_consulta("relação entre pais e filhos, pesquisas pequenas")
    assert "entre" not in termos and "pequenas" not in termos and "pesquisas" not in termos
    assert {"relacao", "pais", "filhos"} <= termos
