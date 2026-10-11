"""Parâmetros da coleta do Marco 2. Altere aqui, não nos clientes."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_RAW = RAIZ / "data" / "raw"
ARQ_BASE = RAIZ / "data" / "knowledge_base.json"
ARQ_PERIODICOS = RAIZ / "data" / "periodicos.json"
ARQ_RELATORIO = RAIZ / "data" / "relatorio_coleta.md"

MAILTO = ""  # opcional: e-mail de contato (polite pool do Crossref). Não é chave.

# --- Recorte -----------------------------------------------------------
ANO_INICIO, ANO_FIM = 2020, 2026
IDIOMAS = {"pt", "en"}
ARTIGOS_POR_SEMENTE = 25          # 4 sementes x 25 = 100 por área
CANDIDATOS_POR_CONSULTA = 100     # margem para os filtros
MAX_ARTIGOS_POR_PERIODICO = 300   # SciELO: limita requisições por periódico

# Ordem importa: artigo achado por duas sementes fica com a primeira.
# Sementes marcadas com * vêm das perguntas simuladas (1, 6, 7, 9).
SEMENTES = {
    "computacao": [
        {"pt": "aprendizado de máquina saúde", "en": "machine learning health"},  # *
        {"pt": "processamento de linguagem natural", "en": "natural language processing"},
        {"pt": "segurança da informação", "en": "information security"},
        {"pt": "engenharia de software", "en": "software engineering"},
    ],
    "odontologia": [
        {"pt": "clareamento dental", "en": "tooth whitening"},  # *
        {"pt": "cárie infantil", "en": "early childhood caries"},  # *
        {"pt": "doença periodontal", "en": "periodontal disease"},
        {"pt": "implantes dentários", "en": "dental implants"},
    ],
    "psicologia": [
        {"pt": "ansiedade universitários", "en": "anxiety university students"},  # *
        {"pt": "depressão", "en": "depression"},
        {"pt": "saúde mental trabalho", "en": "workplace mental health"},
        {"pt": "desenvolvimento infantil", "en": "child development"},
    ],
}

# TAP: Europe PMC é complemento só para Odontologia e Psicologia.
FONTES_POR_AREA = {
    "computacao": ["crossref", "scielo", "doaj"],
    "odontologia": ["crossref", "scielo", "europepmc"],
    "psicologia": ["crossref", "scielo", "europepmc"],
}

# --- DOAJ Article Search ------------------------------------------------
# O Crossref não cobre Computação no nível do recorte temático (devolve resultados de
# áreas vizinhas). O DOAJ indexa por assunto LCC e deixa buscar no resumo, então entra
# como fonte complementar só dessa área.
# Cada entrada é a consulta que o cliente monta:
#   bibjson.title:"<termo>" AND bibjson.subject.term:"<assunto>" AND bibjson.year:[ini TO fim]
# O assunto entra entre aspas para o DOAJ casar o termo exato.
DOAJ_ARTIGOS = {
    "computacao": [
        {"termo": "machine learning", "assunto": "Electronic computers. Computer science"},
        {"termo": "artificial intelligence", "assunto": "Electronic computers. Computer science"},
        {"termo": "natural language processing", "assunto": "Electronic computers. Computer science"},
        {"termo": "information security", "assunto": "Electronic computers. Computer science"},
        {"termo": "software engineering", "assunto": "Electronic computers. Computer science"},
    ],
}

# --- Curadoria ---------------------------------------------------------
# CC0 (domínio público) e CC-BY (só exige atribuição). SA/NC/ND ficam de fora.
LICENCAS_ACEITAS = {"cc-by", "cc0"}

# Periódico indexado no MEDLINE (NLM Catalog) também conta como indexação válida.
ACEITAR_MEDLINE = True

# Conferência de área pelo assunto do periódico.
AREA_LCC = {  # códigos LCC do DOAJ
    "computacao": ("QA75", "QA76", "R858"),  # R858 = informática médica
    "odontologia": ("RK",),
    "psicologia": ("BF",),
}
AREA_WOS = {  # áreas WoS dos periódicos SciELO
    "computacao": ("COMPUTER SCIENCE",),
    "odontologia": ("DENTISTRY",),
    "psicologia": ("PSYCHOLOGY",),
}