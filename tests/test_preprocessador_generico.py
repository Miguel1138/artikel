"""Testes do pré-processador genérico (arquivo único, reutilizável em outros projetos)."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

import preprocessador_generico as pg  # noqa: E402
from preprocessador_generico import Preprocessador  # noqa: E402


def test_limpa_url_html_acento_e_pontuacao():
    pre = Preprocessador()
    texto = "Veja <b>Referência</b> em https://doi.org/10.1/x, ou www.scielo.br!"
    assert pre(texto) == "veja referencia em ou"


def test_html_nao_cola_palavras():
    assert Preprocessador()("a<br>b") == "a b"


def test_numeros_mantidos_ou_removidos():
    assert Preprocessador()("NBR 6023 de 2018") == "nbr 6023 de 2018"
    assert Preprocessador(remover_numeros=True)("NBR 6023 de 2018") == "nbr de"


def test_acento_preservado_quando_pedido():
    assert Preprocessador(remover_acentos=False)("Referência, ação!") == "referência ação"


def test_none_e_nan_viram_vazio():
    pre = Preprocessador()
    assert pre(None) == "" and pre(float("nan")) == "" and pre("") == ""


def test_stopwords_acentuadas_casam_com_texto_sem_acento():
    """Regressão: lista com 'não' não pode ficar inerte porque o token vira 'nao'."""
    pre = Preprocessador(stopwords={"não", "Você"})
    assert pre("você não sabe") == "sabe"


def test_preservar_vence_stopword_tamanho_e_reducao():
    pre = Preprocessador(
        stopwords={"de", "como"}, preservar={"como", "x"}, tamanho_minimo=3,
        reducao=lambda t: t[:3],
    )
    assert pre("como fazer de x") == "como faz x"


def test_tokenizar_sem_remover_stopwords():
    pre = Preprocessador(stopwords={"de"})
    assert pre.tokenizar("artigo de revista", remover_stopwords=False) == ["artigo", "de", "revista"]


def test_instancia_e_serializavel():
    import joblib
    import io

    pre = Preprocessador(stopwords=pg.obter_stopwords("pt"), preservar={"artigo"})
    buf = io.BytesIO()
    joblib.dump(pre, buf)
    buf.seek(0)
    assert joblib.load(buf)("o artigo de teste") == pre("o artigo de teste") == "artigo teste"


def test_obter_stopwords_junta_idiomas_e_extras():
    s = pg.obter_stopwords("pt", "en", extras=["etc"])
    assert {"de", "the", "etc"} <= s
    assert "como" not in s and "não" not in s        # palavras de intenção ficam de fora


def test_obter_stopwords_idioma_desconhecido():
    with pytest.raises(ValueError):
        pg.obter_stopwords("xx")


def test_nltk_ausente_cai_nas_embutidas():
    assert pg.obter_stopwords("pt", usar_nltk=True) >= pg.STOPWORDS_PT


# --- Bag of Words --------------------------------------------------------------------
FRASES = ["busca busca artigo", "artigo artigo artigo", "fonte confiavel"]


def test_bow_conta_repeticoes():
    vetor = pg.criar_vetorizador("bow", Preprocessador())
    X = vetor.fit_transform(FRASES).toarray()
    vocab = vetor.vocabulary_
    assert X[0][vocab["busca"]] == 2 and X[1][vocab["artigo"]] == 3


def test_bow_binario_ignora_repeticao():
    vetor = pg.criar_vetorizador("bow_binario", Preprocessador())
    X = vetor.fit_transform(FRASES).toarray()
    assert X.max() == 1


def test_tfidf_tem_pesos_fracionarios():
    X = pg.criar_vetorizador("tfidf", Preprocessador()).fit_transform(FRASES).toarray()
    assert 0 < X[0].max() < 1.0          # linha com dois termos: pesos fracionários, norma L2 = 1


def test_ngramas_capturam_pares_vizinhos():
    vetor = pg.criar_vetorizador("bow", Preprocessador(), ngramas=(1, 2))
    vetor.fit(["busca booleana avancada"])
    assert "busca booleana" in vetor.vocabulary_ and "booleana avancada" in vetor.vocabulary_


def test_vetorizador_usa_o_preprocessador_na_inferencia():
    pre = Preprocessador(stopwords={"de"})
    vetor = pg.criar_vetorizador("bow", pre)
    vetor.fit(["artigo de revista"])
    assert "de" not in vetor.vocabulary_
    assert vetor.transform(["ARTIGO, de Revista!"]).toarray().sum() == 2


def test_vetorizador_aceita_funcao_qualquer_como_preprocessador():
    vetor = pg.criar_vetorizador("bow", lambda t: t.lower().replace("-", " "))
    vetor.fit(["Palavra-Chave"])
    assert set(vetor.vocabulary_) == {"palavra", "chave"}


def test_tipo_invalido():
    with pytest.raises(ValueError):
        pg.criar_vetorizador("word2vec")


# --- Utilidades de dataset -----------------------------------------------------------
def test_juntar_campos_ignora_vazios():
    assert pg.juntar_campos("Titulo", None, float("nan"), "  ", "corpo") == "Titulo corpo"


def test_descartar_curtos_mantem_alinhamento():
    textos, rotulos = pg.descartar_curtos(["curto", "um texto bem mais longo"], [0, 1], minimo=10)
    assert textos == ["um texto bem mais longo"] and rotulos == [1]


def test_estatisticas_tamanho():
    est = pg.estatisticas_tamanho(["a b", "a b c d", "a"])
    assert est["minimo"] == 1 and est["maximo"] == 4 and est["mediana"] == 2
    assert pg.estatisticas_tamanho([]) == {}


def test_arquivo_nao_depende_do_restante_do_projeto():
    """Para copiar para outro projeto, só pode importar biblioteca padrão no topo."""
    import ast

    arvore = ast.parse((RAIZ / "app" / "preprocessador_generico.py").read_text(encoding="utf-8"))
    topo = {n.module.split(".")[0] if isinstance(n, ast.ImportFrom) else a.name.split(".")[0]
            for n in arvore.body if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert topo <= {"__future__", "re", "unicodedata", "dataclasses", "functools", "typing"}
