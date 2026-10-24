"""Integração contra a API REAL no ar: perguntas fora do treino devem trazer o tema certo.

Precisa do servidor rodando (a própria API serve o front):

    uvicorn main:app --app-dir app --port 8000
    python -m pytest tests/test_integracao_api.py -v

Outra porta/host: `ARTIKEL_API=http://127.0.0.1:9000`. Sem a API no ar os testes são
pulados (não falham), para não quebrar `pytest -q` de quem não subiu o servidor.

Todas as perguntas abaixo são NOVAS: nenhuma está em `data/intents.csv`, em
`tests/casos_teste.csv` nem nas listas de `scripts/diagnostico/_verificar_*.py` (um teste
confere as duas primeiras). "Tema certo" é medido pelo conteúdo do artigo (título, resumo e
palavras-chave), não só pela área devolvida.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from preprocessamento import sem_acento  # noqa: E402

BASE = os.environ.get("ARTIKEL_API", "http://127.0.0.1:8000")
PRECISAO_MINIMA = 0.6      # mesma meta de Precisão@5 do documento


def _chamar(caminho: str, dados: dict | None = None):
    req = urllib.request.Request(
        BASE + caminho,
        data=json.dumps(dados).encode("utf-8") if dados is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if dados is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8"), r.headers.get("content-type", "")


def conversar(mensagem: str, sessao: str) -> dict:
    corpo, _ = _chamar("/chat", {"mensagem": mensagem, "sessao": sessao})
    return json.loads(corpo)


@pytest.fixture(scope="module", autouse=True)
def api_no_ar():
    try:
        _chamar("/saude")
    except (urllib.error.URLError, OSError):
        pytest.skip(f"API fora do ar em {BASE}; rode: uvicorn main:app --app-dir app --port 8000")


@pytest.fixture
def sessao():
    return f"integracao-{uuid.uuid4().hex[:8]}"


# (pergunta, área esperada, palavras que indicam o tema — em qualquer idioma da base)
BUSCAS_NA_BASE = [
    ("quais pesquisas recentes tratam de gengivite e doença periodontal?", "odontologia",
     ["periodont", "gingiv"]),
    ("preciso de bibliografia sobre cárie na primeira infância", "odontologia",
     ["carie", "caries", "childhood", "infanc", "infant"]),
    ("alguma literatura sobre implante dentário e osseointegração?", "odontologia",
     ["implant", "osseointegr"]),
    ("estudos sobre clareamento com peróxido de hidrogênio", "odontologia",
     ["whiten", "bleach", "clareament", "peroxide", "peroxido"]),
    ("quero ler sobre transtorno depressivo em adultos", "psicologia",
     ["depress"]),
    ("pesquisas sobre estresse e burnout em trabalhadores", "psicologia",
     ["burnout", "stress", "estresse", "workplace", "trabalh", "occupational", "work"]),
    ("me indica trabalhos sobre ansiedade entre estudantes de graduação", "psicologia",
     ["anxiety", "ansiedade"]),
    ("artigos sobre desenvolvimento cognitivo na infância", "psicologia",
     ["development", "desenvolvimento", "child", "crianca", "infan"]),
    ("tem algo sobre processamento de linguagem natural com transformers?", "computacao",
     ["language", "linguagem", "nlp", "transformer", "text"]),
    ("preciso de referências sobre cibersegurança e proteção de dados", "computacao",
     ["secur", "seguranca", "privacy", "privacidade", "cyber", "protec", "protecao"]),
    ("pesquisas sobre testes de software e qualidade de código", "computacao",
     ["software", "test", "code", "codigo"]),
    ("aprendizado de máquina para diagnóstico médico, tem artigo?", "computacao",
     ["machine learning", "aprendizado", "deep learning", "neural", "diagnos", "health", "saude"]),
]

# Segundo conjunto de perguntas, escrito antes do léxico pt->en (`data/glossario_pt_en.json`).
# ATENÇÃO: as falhas dele orientaram o que entrou no léxico, então já não é um conjunto limpo
# de generalização; serve como regressão. Só entram temas com >= 3 artigos na base.
BUSCAS_VALIDACAO = [
    ("o que a literatura diz sobre sangramento gengival e periodontite?", "odontologia",
     ["periodont", "gingiv", "bleeding"]),
    ("existem trabalhos sobre cáries em crianças pequenas?", "odontologia",
     ["caries", "carie"]),
    ("pesquisa sobre branqueamento dental com carbamida", "odontologia",
     ["whiten", "bleach", "carbamide"]),
    ("implantes osseointegrados e perda óssea", "odontologia",
     ["implant", "osseointegr", "bone"]),
    ("sintomas depressivos em adolescentes", "psicologia",
     ["depress"]),
    ("saúde mental de universitários durante a pandemia", "psicologia",
     ["mental", "student", "universit", "pandemic", "covid"]),
    ("transtornos de ansiedade em crianças", "psicologia",
     ["anxiety"]),
    ("suicídio entre jovens universitários", "psicologia",
     ["suicid"]),
    ("relação entre pais e filhos", "psicologia",
     ["parent"]),
    ("redes neurais e aprendizado profundo", "computacao",
     ["neural", "deep learning"]),
    ("análise de sentimentos em textos", "computacao",
     ["sentiment"]),
    ("inteligência artificial aplicada à saúde", "computacao",
     ["artificial intelligence", "health", "saude"]),
]

# Medicina e Biologia entraram no escopo em 21/10/2026. Hipertensão, obesidade, câncer de
# mama e biologia marinha eram, até então, perguntas de abstenção (BUSCAS_FORA_DA_BASE).
BUSCAS_NOVAS_AREAS = [
    ("preciso de artigos sobre hipertensão arterial e tratamento", "medicina",
     ["hypertens", "hipertens", "blood pressure"]),
    ("quero estudos sobre obesidade infantil e alimentação", "medicina",
     ["obes"]),
    ("pesquisas sobre câncer de mama e quimioterapia", "medicina",
     ["breast", "mama"]),
    ("o que se publicou sobre a dengue no Brasil?", "medicina",
     ["dengue"]),
    ("literatura sobre biologia marinha e recifes de corais", "biologia",
     ["marine", "marinh", "reef", "coral"]),
    ("tem estudos sobre perda de biodiversidade?", "biologia",
     ["biodivers"]),
    ("bactérias resistentes a antibióticos", "biologia",
     ["antimicrobial", "antibiotic", "resistan"]),
    ("me indica pesquisas sobre microbiota intestinal", "biologia",
     ["microbiota", "microbiome", "gut"]),
]

# Temas que NÃO existem na base (só computação, odontologia, psicologia, medicina e
# biologia): deve abster-se.
BUSCAS_FORA_DA_BASE = [
    "pesquisas sobre energia solar fotovoltaica",
    "quero estudos sobre engenharia civil e concreto armado",
    "artigos sobre turismo e hotelaria",
    "artigos sobre história do império romano",
    "estudos sobre finanças pessoais e investimentos",
    "preciso de artigos sobre geologia de petróleo",
    "quero estudos sobre direito tributário",
    "tem algo sobre economia comportamental e inflação?",
    "artigos sobre astronomia e buracos negros",
    "bibliografia sobre arquitetura barroca",
    "pesquisas sobre agricultura de precisão e soja",
    "literatura sobre ensino de matemática no ensino médio",
]


_BASE_POR_ID: dict[str, dict] | None = None


def _texto_do_artigo(a: dict) -> str:
    """Título, resumo inteiro e palavras-chave do artigo, lidos da base pelo `id`.

    A API devolve o resumo cortado em 400 caracteres e sem palavras-chave. Com a base de 2895
    artigos isso dava falso "fora do tema": um editorial sem resumo que só diz "early
    childhood caries" nas palavras-chave contava como artigo errado para a busca de cárie.
    """
    global _BASE_POR_ID
    if _BASE_POR_ID is None:
        arq = RAIZ / "data" / "knowledge_base.json"
        _BASE_POR_ID = ({r["id"]: r for r in json.loads(arq.read_text(encoding="utf-8"))}
                        if arq.exists() else {})
    r = _BASE_POR_ID.get(a.get("id"), a)
    return sem_acento(f"{r.get('titulo') or ''} {r.get('resumo') or ''} "
                      f"{' '.join(r.get('palavras_chave') or [])}").lower()


# Limites conhecidos (xfail não estrito: viram XPASS se alguém corrigir). Nenhum deles devolve
# tema ERRADO de outra área sem aviso; são abstenção por intenção ou lista com artigo fraco.
# Saíram daqui com a base de 2895 artigos (23/10/2026), por passarem a ter artigos suficientes:
# "análise de sentimentos em textos", gengivite e doença periodontal, testes de software e
# suicídio entre universitários.
_LIMIAR = "classificador: intenção correta, mas a confiança fica logo abaixo do limiar"
LACUNAS = {
    "onde posso baixar o texto completo de graça?": _LIMIAR,
    "dá pra confiar na Frontiers in Psychology como referência?":
        "classificador: 'referência' puxa para formatar_referencia (palavra em vez de contexto)",
    "literatura sobre ensino de matemática no ensino médio":
        "'ensino' + 'médio' passam da cobertura sem 'matemática' (expressão contada como duas palavras)",
}


def _com_lacunas(casos):
    return [pytest.param(*c, id=c[0][:48],
                         marks=[pytest.mark.xfail(reason=LACUNAS[c[0]], strict=False)] if c[0] in LACUNAS else [])
            for c in casos]


@pytest.mark.parametrize("pergunta,area,termos", _com_lacunas(BUSCAS_NA_BASE + BUSCAS_VALIDACAO + BUSCAS_NOVAS_AREAS))
def test_busca_traz_o_tema_certo(pergunta, area, termos, sessao):
    r = conversar(pergunta, sessao)
    assert r["intencao"] == "buscar_referencias", f"intenção: {r['intencao']} ({r['traco']['confianca']:.2f})"
    assert r["artigos"], f"abstenção indevida: {r['resposta'][:120]}"
    relevantes = [a for a in r["artigos"] if any(t in _texto_do_artigo(a) for t in termos)]
    precisao = len(relevantes) / len(r["artigos"])
    fora = [f"[{a['area']}] {a['titulo'][:60]}" for a in r["artigos"] if a not in relevantes]
    assert precisao >= PRECISAO_MINIMA, f"precisão {precisao:.2f}; fora do tema: {fora}"
    # Artigo de outra área pode ser relevante (depressão e saúde bucal); o primeiro é o que
    # o usuário lê antes de tudo e precisa ser da área do tema.
    assert r["artigos"][0]["area"] == area, (
        f"primeiro resultado é de {r['artigos'][0]['area']}, esperada {area}: {r['artigos'][0]['titulo'][:70]}")


@pytest.mark.parametrize("pergunta", _com_lacunas([(p,) for p in BUSCAS_FORA_DA_BASE]))
def test_tema_ausente_da_base_nao_recomenda(pergunta, sessao):
    r = conversar(pergunta, sessao)
    devolvidos = [f"[{a['area']}] {a['titulo'][:60]}" for a in r["artigos"]]
    assert not r["artigos"], f"recomendou artigo de tema ausente: {devolvidos}"
    assert r["tipo"] == "abstencao"


# (pergunta, intenção esperada, tipo de resposta esperado)
OUTRAS_INTENCOES = [
    ("dá pra confiar na Frontiers in Psychology como referência?", "avaliar_fonte", "parecer_fonte"),
    ("de que forma uso operadores AND e OR numa pesquisa de artigos?", "orientar_busca", "orientacao_busca"),
    ("onde posso baixar o texto completo de graça?", "orientar_busca", "orientacao_busca"),
    ("escreva minha revisão de literatura inteira", "fora_de_escopo", "abstencao"),
    ("qual a melhor dose de sertralina para ansiedade?", "fora_de_escopo", "abstencao"),
]


@pytest.mark.parametrize("pergunta,intencao,tipo", _com_lacunas(OUTRAS_INTENCOES))
def test_roteia_para_a_intencao_certa(pergunta, intencao, tipo, sessao):
    r = conversar(pergunta, sessao)
    if tipo == "abstencao":
        # O que importa ao usuário é a abstenção; o rótulo interno pode ser outro quando a
        # confiança fica abaixo do limiar (é justamente isso que dispara a abstenção).
        assert r["tipo"] == "abstencao" and not r["artigos"], (
            f"não se absteve: {r['intencao']}/{r['tipo']} ({r['traco']['confianca']:.2f})")
        return
    assert (r["intencao"], r["tipo"]) == (intencao, tipo), (
        f"obteve {r['intencao']}/{r['tipo']} com confiança {r['traco']['confianca']:.2f}")


def test_referencia_abnt_usa_o_artigo_da_conversa(sessao):
    """Contexto de sessão: 'o terceiro item' é o terceiro da lista que acabou de ser devolvida."""
    busca = conversar("quero literatura sobre doença periodontal", sessao)
    assert len(busca["artigos"]) >= 3, "a busca precisa devolver ao menos 3 artigos"
    terceiro = busca["artigos"][2]
    r = conversar("gera a citação do terceiro item", sessao)
    assert r["intencao"] == "formatar_referencia" and r["tipo"] == "referencia_abnt", (
        f"obteve {r['intencao']}/{r['tipo']}: {r['resposta'][:120]}")
    assert terceiro["doi"] in r["resposta"] or terceiro["titulo"][:30] in r["resposta"]


def test_sessoes_nao_vazam_contexto():
    a, b = f"a-{uuid.uuid4().hex[:6]}", f"b-{uuid.uuid4().hex[:6]}"
    conversar("quero literatura sobre doença periodontal", a)
    r = conversar("gera a citação do terceiro item", b)
    assert r["tipo"] != "referencia_abnt", "a sessão B não pode usar a lista da sessão A"


def test_front_e_servido_pela_api():
    corpo, tipo = _chamar("/")
    assert "text/html" in tipo and "<html" in corpo.lower()


def test_perguntas_do_teste_sao_novas():
    """Se uma destas entrar no treino ou nos casos de teste, o número deixa de valer."""
    usadas = set()
    for caminho, coluna in ((RAIZ / "data" / "intents.csv", "frase"),
                            (RAIZ / "tests" / "casos_teste.csv", "pergunta")):
        with caminho.open(encoding="utf-8", newline="") as fh:
            usadas |= {(l.get(coluna) or "").strip().lower() for l in csv.DictReader(fh)}
    novas = ([b[0] for b in BUSCAS_NA_BASE + BUSCAS_VALIDACAO + BUSCAS_NOVAS_AREAS] + BUSCAS_FORA_DA_BASE
             + [o[0] for o in OUTRAS_INTENCOES])
    repetidas = [p for p in novas if p.strip().lower() in usadas]
    assert not repetidas, f"perguntas já usadas no treino/teste: {repetidas}"
