"""Gera `data/glossario_pt_en.json`: ponte pt -> en usada pela recuperação.

A base é 84% inglês e as perguntas são em português; sem uma ponte, "gengivite" não casa
com "gingivitis". O corpus não tem texto paralelo (nem Keras/TensorFlow trazem um), então a
ponte vem do **Open Multilingual WordNet** (NLTK).

Por que há uma lista de aprovação (`APROVADOS`) e não "tudo que o OMW propõe":
  * o OMW é de língua geral e polissêmico: "pais" -> country, "teste" -> run,
    "terraplenagem" -> mining (!). Um par errado faz uma pergunta FORA do tema devolver
    artigo de outro assunto, que é exatamente o erro que a recuperação precisa evitar;
  * falta vocabulário técnico (periodontite, cibersegurança, implante): entra como manual.

Fluxo: o OMW propõe (`--candidatos`), uma pessoa aprova em `APROVADOS`, e este script
grava o JSON conferindo que (1) o lado inglês existe no texto da base e (2) cada par é
marcado como vindo do OMW ou manual. A API só lê o JSON; não importa NLTK.

Uso (uma vez, ou quando a base mudar):
    pip install nltk
    python -c "import nltk; nltk.download('omw-2.0', download_dir='.tmp_nltk_data'); \
nltk.download('wordnet', download_dir='.tmp_nltk_data')"
    python scripts/gerar_glossario.py --candidatos   # o que o OMW propõe (para revisar)
    python scripts/gerar_glossario.py                # grava data/glossario_pt_en.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARQ_BASE = RAIZ / "data" / "knowledge_base.json"
ARQ_SAIDA = RAIZ / "data" / "glossario_pt_en.json"
NLTK_DATA = RAIZ / ".tmp_nltk_data"

MIN_DF = 2            # a palavra inglesa precisa aparecer em >= 2 artigos para ser proposta
MAX_SENTIDOS = 3      # WordNet ordena os sentidos por frequência; os seguintes são ruído
TAM_MIN = 4           # igual a `Motor._termos_consulta`: termos com menos de 4 letras são ignorados

# pt (sem acento) -> equivalentes em inglês, na grafia que aparece na base.
# Regra do `ALIASES` de recuperacao.py: só SINÔNIMOS que podem trocar de lugar numa busca.
# "dental" NÃO é equivalente de "clareamento"; "relacionado" não vale como sinônimo.
# Termo inglês igual ao português (software, neural, anxiety...) não precisa de entrada.
APROVADOS: dict[str, list[str]] = {
    # --- odontologia
    "bucal": ["oral"],
    "branqueamento": ["whitening", "bleaching"],
    "clareamento": ["whitening", "bleaching"],
    "carie": ["caries"],
    "dente": ["tooth", "teeth"], "dentes": ["tooth", "teeth"],
    "dentario": ["dental"], "dentina": ["dentin"], "esmalte": ["enamel"],
    "dentifricio": ["dentifrices", "toothpaste", "toothpastes"],
    "dentifrico": ["dentifrices", "toothpaste", "toothpastes"],
    "fluoreto": ["fluoride"], "peroxido": ["peroxide"], "hidrogenio": ["hydrogen"],
    "carbamida": ["carbamide"],
    "gengival": ["gingival"], "gengivite": ["gingivitis"],
    "periodontite": ["periodontitis", "periodontal"],
    "sangramento": ["bleeding"],
    "implante": ["implant"], "implantes": ["implants"],
    "osseointegracao": ["osseointegration"], "osseointegrado": ["osseointegrated", "osseointegration"],
    "osso": ["bone"], "osseo": ["bone"], "ossea": ["bone"], "perda": ["loss"],
    "polpa": ["pulp"], "resina": ["resin"], "protese": ["prosthesis"], "titanio": ["titanium"],
    "restauracao": ["restoration", "restorations"],
    "cirurgia": ["surgery"], "ortodontia": ["orthodontic", "orthodontics"],
    # --- psicologia e saúde
    "depressao": ["depression"], "depressivo": ["depressive", "depression"],
    "sintoma": ["symptoms"], "sintomas": ["symptoms"], "sofrimento": ["distress"],
    "suicida": ["suicidal"], "suicidio": ["suicide", "suicidal"],
    "adolescente": ["adolescent", "adolescents"], "adolescencia": ["adolescence"],
    "bebe": ["infant", "infants"], "infancia": ["childhood", "early childhood"],
    "jovem": ["young", "youth"], "jovens": ["young", "youth"],
    "filho": ["child", "children", "offspring"], "filhos": ["child", "children", "offspring"],
    "pais": ["parents", "parent"], "pai": ["parent", "father"], "mae": ["parent", "mother"],
    "familia": ["family"], "familiar": ["family"],
    "universitario": ["university", "college", "undergraduate"],
    "universitarios": ["university", "college", "undergraduate"],
    "universidade": ["university"],
    "pandemia": ["pandemic", "covid"],
    "comportamento": ["behavior", "behaviour"], "comportamental": ["behavioral"],
    "cognitivo": ["cognitive"], "emocional": ["emotional"], "psicologico": ["psychological"],
    "psicologia": ["psychology"],
    "estresse": ["stress"], "tensao": ["stress"], "esgotamento": ["burnout", "exhaustion"],
    "vicio": ["addiction"], "dependencia": ["addiction"],
    "tabagismo": ["smoking", "tobacco"], "alcool": ["alcohol"],
    "trabalhador": ["workers", "employees"], "trabalhadores": ["workers", "employees"],
    "doenca": ["disease", "diseases"], "doencas": ["disease", "diseases"],
    "transtorno": ["disorder", "disorders"], "transtornos": ["disorder", "disorders"],
    "envelhecimento": ["aging"], "autismo": ["autism"], "obesidade": ["obesity"],
    # --- computação
    "inteligencia": ["intelligence"],
    "ciberseguranca": ["cybersecurity", "cyber", "security"],
    "protecao": ["protection"], "requisito": ["requirements"], "requisitos": ["requirements"],
    "agil": ["agile"], "algoritmo": ["algorithm"], "algoritmos": ["algorithms"],
    "rede": ["network", "networks"], "redes": ["network", "networks"],
    "profundo": ["deep"], "sentimento": ["sentiment"], "sentimentos": ["sentiment"],
    "texto": ["text"], "textos": ["text"], "classificacao": ["classification"],
    "previsao": ["prediction"], "deteccao": ["detection"], "mineracao": ["mining"], "aplicativo": ["app", "apps", "application"],
    "aplicativos": ["app", "apps", "applications"], "midia": ["media"],
    # --- palavras comuns na base. O peso na cobertura é a raridade do CONJUNTO de variantes
    # (recuperacao.Motor._peso), então estas contam pouco; sem entrada, ficariam sem
    # correspondência e com peso máximo.
    "analise": ["analysis"], "cuidado": ["care"], "codigo": ["code"], "crianca": ["child", "children"],
    "criancas": ["child", "children"], "adulto": ["adult", "adults"], "adultos": ["adult", "adults"],
    "dados": ["data"], "diagnostico": ["diagnosis"], "escola": ["school"], "estudante": ["students"],
    "medico": ["medical"], "modelo": ["model", "models"], "modelos": ["model", "models"],
    "prevencao": ["prevention"], "prevalencia": ["prevalence"], "profissional": ["professionals", "workers"],
    "profissionais": ["professionals", "workers"], "qualidade": ["quality"], "relacao": ["relationship"],
    "relacionamento": ["relationship"], "risco": ["risk"], "tecnologia": ["technology", "technologies"],
    "terapia": ["therapy"], "teste": ["testing", "test", "tests"], "testes": ["testing", "test", "tests"],
    "tratamento": ["treatment"],
    "transformador": ["transformer"], "transformadores": ["transformer", "transformers"], "processamento": ["processing"],
}


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()


def palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z]+", sem_acento(texto)) if len(p) >= TAM_MIN}


def texto_do_artigo(a: dict) -> str:
    return f"{a.get('titulo') or ''} {' '.join(a.get('palavras_chave') or [])} {a.get('resumo') or ''}"


def vocabulario(artigos: list[dict]) -> Counter:
    """Em quantos artigos cada palavra aparece (título, palavras-chave e resumo)."""
    df: Counter = Counter()
    for a in artigos:
        df.update(palavras(texto_do_artigo(a)))
    return df


def contem_expressao(artigos_normalizados: list[str], expressao: str) -> bool:
    return any(expressao in t for t in artigos_normalizados)


def propostas_omw(vocab: Counter) -> dict[str, dict[str, int]]:
    """pt -> {en: df}: o que o OMW propõe para as palavras inglesas frequentes da base."""
    import nltk

    nltk.data.path.insert(0, str(NLTK_DATA))
    from nltk.corpus import wordnet as wn

    pares: dict[str, dict[str, int]] = defaultdict(dict)
    for en, df in sorted(vocab.items()):
        if df < MIN_DF:
            continue
        for sinset in wn.synsets(en, lang="eng")[:MAX_SENTIDOS]:
            for lema in sinset.lemma_names("por"):
                pt = sem_acento(lema)
                if pt.isalpha() and len(pt) >= TAM_MIN and pt != en:
                    pares[pt][en] = df
    return pares


def montar(artigos: list[dict]) -> tuple[dict[str, list[str]], dict]:
    textos = [sem_acento(texto_do_artigo(a)) for a in artigos]
    vocab = vocabulario(artigos)
    omw = propostas_omw(vocab)

    glossario, ausentes, origem = {}, [], Counter()
    for pt, ens in sorted(APROVADOS.items()):
        mantidos = []
        for en in ens:
            presente = (vocab[en] if " " not in en else sum(en in t for t in textos)) > 0
            if not presente:
                ausentes.append(f"{pt} -> {en}")
                continue
            mantidos.append(en)
            origem["omw" if en in omw.get(pt, {}) else "manual"] += 1
        if mantidos:
            glossario[pt] = mantidos
    return glossario, {"ausentes": ausentes, "origem": origem}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--candidatos", action="store_true", help="só imprime a proposta do OMW")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    artigos = json.loads(ARQ_BASE.read_text(encoding="utf-8"))
    if args.candidatos:
        pares = propostas_omw(vocabulario(artigos))
        for pt in sorted(pares):
            print(f"{pt:<22} -> " + ", ".join(f"{en}({df})" for en, df in sorted(pares[pt].items())))
        return

    glossario, info = montar(artigos)
    ARQ_SAIDA.write_text(json.dumps(glossario, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(glossario)} termos pt gravados em {ARQ_SAIDA.relative_to(RAIZ)} "
          f"| pares: {info['origem']['omw']} do OMW, {info['origem']['manual']} manuais")
    if info["ausentes"]:
        print(f"descartados (lado inglês ausente da base): {', '.join(info['ausentes'])}")


if __name__ == "__main__":
    main()
