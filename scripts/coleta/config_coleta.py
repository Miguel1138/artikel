"""Parâmetros da coleta do Marco 2. Altere aqui, não nos clientes."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_RAW = RAIZ / "data" / "raw"
ARQ_BASE = RAIZ / "data" / "knowledge_base.json"
ARQ_PERIODICOS = RAIZ / "data" / "periodicos.json"
ARQ_RELATORIO = RAIZ / "data" / "relatorio_coleta.md"

MAILTO = ""  # opcional: e-mail de contato (polite pool do Crossref). Não é chave.

# --- Recorte -----------------------------------------------------------
# Janela de 10 anos contados a partir de 21/10/2026, no nível de ano (as APIs filtram por
# ano de publicação). A base de 246 artigos em 2020–2026 dava underfitting.
ANO_INICIO, ANO_FIM = 2016, 2026
IDIOMAS = {"pt", "en"}
ARTIGOS_POR_SEMENTE = 75          # 8 sementes x 75 = 600 por área, ~3000 na base
CANDIDATOS_POR_CONSULTA = 500     # margem para os filtros (o fora_do_tema descarta a maioria)
MAX_ARTIGOS_POR_PERIODICO = 300   # SciELO: limita requisições por periódico

# Ordem importa: artigo achado por duas sementes fica com a primeira.
# Sementes marcadas com * vêm das perguntas simuladas (1, 6, 7, 9).
SEMENTES = {
    "computacao": [
        {"pt": "aprendizado de máquina saúde", "en": "machine learning health"},  # *
        {"pt": "processamento de linguagem natural", "en": "natural language processing"},
        {"pt": "segurança da informação", "en": "information security"},
        {"pt": "engenharia de software", "en": "software engineering"},
        {"pt": "inteligência artificial", "en": "artificial intelligence"},
        {"pt": "visão computacional", "en": "computer vision"},
        {"pt": "internet das coisas", "en": "internet of things"},
        {"pt": "mineração de dados", "en": "data mining"},
    ],
    "odontologia": [
        {"pt": "clareamento dental", "en": "tooth whitening"},  # *
        {"pt": "cárie infantil", "en": "early childhood caries"},  # *
        {"pt": "doença periodontal", "en": "periodontal disease"},
        {"pt": "implantes dentários", "en": "dental implants"},
        {"pt": "ortodontia", "en": "orthodontics"},
        {"pt": "endodontia", "en": "endodontics"},
        {"pt": "câncer bucal", "en": "oral cancer"},
        {"pt": "saúde bucal", "en": "oral health"},
    ],
    "psicologia": [
        {"pt": "ansiedade universitários", "en": "anxiety university students"},  # *
        {"pt": "depressão", "en": "depression"},
        {"pt": "saúde mental trabalho", "en": "workplace mental health"},
        {"pt": "desenvolvimento infantil", "en": "child development"},
        {"pt": "autismo", "en": "autism"},
        {"pt": "terapia cognitivo-comportamental", "en": "cognitive behavioral therapy"},
        {"pt": "trauma psicológico", "en": "psychological trauma"},
        {"pt": "violência doméstica", "en": "domestic violence"},
    ],
    "medicina": [
        {"pt": "hipertensão arterial", "en": "hypertension"},
        {"pt": "diabetes mellitus", "en": "diabetes mellitus"},
        {"pt": "câncer de mama", "en": "breast cancer"},
        {"pt": "covid-19", "en": "covid-19"},
        {"pt": "doenças cardiovasculares", "en": "cardiovascular disease"},
        {"pt": "obesidade", "en": "obesity"},
        {"pt": "tuberculose", "en": "tuberculosis"},
        {"pt": "dengue", "en": "dengue"},
    ],
    "biologia": [
        {"pt": "biodiversidade", "en": "biodiversity"},
        {"pt": "ecologia", "en": "ecology"},
        {"pt": "genética de populações", "en": "population genetics"},
        {"pt": "microbiota", "en": "microbiota"},
        {"pt": "resistência antimicrobiana", "en": "antimicrobial resistance"},
        {"pt": "ecossistemas marinhos", "en": "marine ecosystems"},
        {"pt": "evolução", "en": "evolution"},
        {"pt": "plantas medicinais", "en": "medicinal plants"},
    ],
}

# TAP: Europe PMC é complemento das áreas de saúde e vida (não cobre Computação).
FONTES_POR_AREA = {
    "computacao": ["crossref", "scielo", "doaj"],
    "odontologia": ["crossref", "scielo", "europepmc"],
    "psicologia": ["crossref", "scielo", "europepmc"],
    "medicina": ["crossref", "scielo", "europepmc"],
    "biologia": ["crossref", "scielo", "europepmc"],
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
        {"termo": termo, "assunto": "Electronic computers. Computer science"}
        for termo in ("machine learning", "artificial intelligence", "natural language processing",
                      "information security", "software engineering", "computer vision",
                      "internet of things", "data mining", "deep learning")
    ],
}

# --- Curadoria ---------------------------------------------------------
# CC0 (domínio público) e CC-BY (só exige atribuição). SA/NC/ND ficam de fora.
LICENCAS_ACEITAS = {"cc-by", "cc0"}

# Periódico indexado no MEDLINE (NLM Catalog) também conta como indexação válida.
ACEITAR_MEDLINE = True

# Conferência de área pelo assunto do periódico (prefixo do código).
AREA_LCC = {  # códigos LCC do DOAJ
    "computacao": ("QA75", "QA76", "R858"),  # R858 = informática médica
    "odontologia": ("RK",),
    "psicologia": ("BF",),
    "medicina": ("R",),
    # QH biologia geral, QK botânica, QL zoologia, QM anatomia, QP fisiologia, QR microbiologia
    "biologia": ("QH", "QK", "QL", "QM", "QP", "QR"),
}
AREA_WOS = {  # áreas WoS dos periódicos SciELO (trecho do nome)
    "computacao": ("COMPUTER SCIENCE",),
    "odontologia": ("DENTISTRY",),
    "psicologia": ("PSYCHOLOGY",),
    "medicina": ("MEDICINE", "PUBLIC, ENVIRONMENTAL", "PEDIATRICS", "SURGERY", "CARDIAC",
                 "ONCOLOGY", "INFECTIOUS DISEASES", "OBSTETRICS", "ENDOCRINOLOGY",
                 "CLINICAL NEUROLOGY", "PSYCHIATRY", "HEALTH CARE SCIENCES", "GASTROENTEROLOGY",
                 "UROLOGY", "OPHTHALMOLOGY", "ORTHOPEDICS", "DERMATOLOGY", "RESPIRATORY",
                 "RHEUMATOLOGY", "HEMATOLOGY", "PATHOLOGY", "RADIOLOGY", "GERIATRICS",
                 "OTORHINOLARYNGOLOGY", "ANESTHESIOLOGY", "TROPICAL"),
    "biologia": ("BIOLOGY", "ECOLOGY", "ZOOLOGY", "PLANT SCIENCES", "GENETICS", "BIODIVERSITY",
                 "ENTOMOLOGY", "EVOLUTIONARY", "BIOCHEMISTRY", "PARASITOLOGY", "MYCOLOGY"),
}
# Códigos/áreas que contêm o prefixo de uma área mas pertencem a outra: "R" pegaria RK
# (Odontologia) e R858 (informática médica); "MEDICINE" e "SURGERY" pegariam
# "DENTISTRY, ORAL SURGERY & MEDICINE"; "PATHOLOGY" pegaria "PLANT PATHOLOGY".
AREA_LCC_EXCLUI = {"medicina": ("RK", "R858")}
AREA_WOS_EXCLUI = {"medicina": ("DENTISTRY", "PLANT", "VETERINARY")}
