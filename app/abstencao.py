"""Textos e regras de abstenção.

O documento é explícito: "toda resposta aponta para um registro real da base, com DOI ou
link verificado; sem registro adequado, o bot se abstém em vez de inventar". Este módulo
concentra as mensagens para que sejam revisadas em um lugar só.
"""
from __future__ import annotations

from config import ABSTENCOES_ANTES_DE_REPETIR

CURTA = (
    "Ainda não tenho um registro verificado na base para responder isso. "
    "Posso procurar artigos sobre o tema, avaliar uma fonte ou montar a referência ABNT "
    "de um artigo que eu já tenha indicado."
)

COMPLETA = (
    "Isso está fora do escopo do Artikel. Eu recomendo artigos de uma base curada, avalio "
    "fontes pela indexação, monto referências ABNT e oriento a busca em bases acadêmicas. "
    "Não escrevo, corrijo nem resumo o seu texto, e não dou orientação clínica. "
    "Para o texto do TCC, procure o orientador; para acesso a artigos e normas, a biblioteca."
)

SEM_BASE = (
    "A base curada ainda não foi gerada ou está vazia, então não posso recomendar nada com "
    "segurança. Rode `python scripts/coleta/pipeline.py` para montar `data/knowledge_base.json`."
)

SEM_CONTEXTO = (
    "Para montar a referência eu preciso saber qual artigo. Faça uma busca primeiro "
    "(por exemplo: \"preciso de artigos sobre clareamento dental\") e depois peça a "
    "referência do primeiro, do segundo e assim por diante."
)

SEM_FAQ = (
    "Não encontrei na FAQ de busca uma orientação para essa pergunta. Tente dizer a base "
    "que quer usar (SciELO, Google Acadêmico, PubMed) e o tema, que eu indico os termos."
)

SUGESTOES = [
    "Preciso de artigos sobre aprendizado de máquina na saúde",
    "A revista X é confiável?",
    "Me dá a referência ABNT do segundo artigo",
    "Como procuro artigos no SciELO?",
]


def mensagem_fora_de_escopo(repeticoes: int) -> str:
    """A primeira abstenção é curta; a completa volta depois de várias seguidas."""
    if repeticoes >= ABSTENCOES_ANTES_DE_REPETIR:
        return COMPLETA
    return CURTA


ENCAMINHAMENTOS = {
    "orientador": "Leve a dúvida ao orientador: a decisão sobre o texto e sobre o tema é dele.",
    "biblioteca": "A biblioteca da instituição resolve acesso a artigo pago e normas da ABNT.",
    "clinica": "Para conduta clínica, procure um profissional de saúde habilitado.",
}
