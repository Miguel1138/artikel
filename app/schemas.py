"""Contratos da API (pydantic) e formato dos dados internos.

Nada de lógica aqui: são os tipos que `fluxo.py` devolve e que a interface React consome.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Intencao = Literal[
    "buscar_referencias",
    "avaliar_fonte",
    "formatar_referencia",
    "orientar_busca",
    "fora_de_escopo",
]


# ---------------------------------------------------------------- base interna
class Autor(BaseModel):
    sobrenome: str = ""
    nome: str = ""


class Artigo(BaseModel):
    id: str
    doi: str | None = None
    titulo: str
    autores: list[Autor] = Field(default_factory=list)
    ano: int | None = None
    periodico: str | None = None
    issn: list[str] = Field(default_factory=list)
    volume: str | None = None
    numero: str | None = None
    paginas: str | None = None
    resumo: str | None = None
    palavras_chave: list[str] = Field(default_factory=list)
    idioma: str | None = None
    licenca: str | None = None
    area: str | None = None
    fonte: str | None = None
    url: str | None = None
    data_coleta: str | None = None

    # campos calculados na resposta (não vêm do JSON da base)
    score: float | None = None
    motivo: str | None = None
    referencia_abnt: str | None = None


class Periodico(BaseModel):
    titulo: str
    issn: list[str] = Field(default_factory=list)
    indexacao: list[str] = Field(default_factory=list)
    assuntos: list[str] = Field(default_factory=list)
    revisao: list[str] = Field(default_factory=list)
    url: str | None = None
    licenca: str | None = None


class Traco(BaseModel):
    """Traço da decisão (R4): o caminho que o fluxo percorreu e por quê."""

    intencao_prevista: str
    confianca: float
    limiar_confianca: float
    acao: str
    regra: str
    termos: list[str] = Field(default_factory=list)
    n_candidatos: int = 0
    score_maximo: float | None = None
    limiar_score: float | None = None
    contexto_usado: bool = False
    confianca_abaixo_do_limiar: bool = False


# ---------------------------------------------------------------- API
class Mensagem(BaseModel):
    mensagem: str = Field(min_length=1, max_length=1000)
    sessao: str = Field(default="default", max_length=64)


class RespostaArtigo(BaseModel):
    posicao: int
    id: str
    titulo: str
    autores: str
    ano: int | None
    periodico: str | None
    doi: str | None
    url: str | None
    score: float
    motivo: str
    referencia_abnt: str
    resumo: str | None = None
    licenca: str | None = None
    area: str | None = None


class Resposta(BaseModel):
    resposta: str
    intencao: Intencao
    tipo: Literal[
        "recomendacao",
        "parecer_fonte",
        "referencia_abnt",
        "orientacao_busca",
        "abstencao",
    ]
    artigos: list[RespostaArtigo] = Field(default_factory=list)
    fontes: list[str] = Field(default_factory=list)
    sugestoes: list[str] = Field(default_factory=list)
    traco: Traco


class Saude(BaseModel):
    status: str
    artigos_na_base: int
    periodicos_na_base: int
    entradas_faq: int
    modelo_carregado: bool
    limiar_confianca: float
    limiar_score: float
    recorte_anos: list[int]
    areas: list[str]
    avisos: list[str] = Field(default_factory=list)
