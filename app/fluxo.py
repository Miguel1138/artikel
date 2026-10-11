"""Orquestrador do fluxo (R4).

Único ponto que encadeia os módulos: entrada -> normalização -> intenção -> busca/regra ->
resposta ou abstenção, sempre com o traço da decisão. Nenhum outro módulo decide limiar.

O bot **nunca** gera texto livre com referências: o que aparece na resposta vem da base
curada (`recuperacao`), da lista de periódicos (`periodicos`), da FAQ (`faq`) ou das regras
ABNT (`abnt`).
"""
from __future__ import annotations

from datetime import date

from config import (
    FORA_DE_ESCOPO,
    LIMIAR_CONFIANCA,
    LIMIAR_SCORE,
    TOP_K,
)
import abstencao
import abnt
import faq as modulo_faq
import intencoes
import periodicos as modulo_periodicos
import recuperacao
from contexto import sessoes
from schemas import Resposta, RespostaArtigo, Traco


def _motivo_texto(candidato: recuperacao.Candidato) -> str:
    partes = []
    if candidato.similaridade >= 0.35:
        partes.append("alta similaridade com a sua busca")
    elif candidato.similaridade >= 0.18:
        partes.append("similaridade razoável com a sua busca")
    else:
        partes.append("similaridade baixa, mas melhor que o limiar")
    partes += candidato.motivos
    return "; ".join(partes)


def _resposta_artigo(candidato: recuperacao.Candidato, posicao: int, data_acesso: str) -> RespostaArtigo:
    a = candidato.artigo
    return RespostaArtigo(
        posicao=posicao,
        id=a["id"],
        titulo=a.get("titulo") or "(sem título)",
        autores=abnt.formatar_autores(a.get("autores")) or "Autoria não informada",
        ano=a.get("ano"),
        periodico=a.get("periodico"),
        doi=a.get("doi"),
        url=a.get("url"),
        score=recuperacao.normalizar_score(candidato.score),
        motivo=_motivo_texto(candidato),
        referencia_abnt=abnt.formatar_referencia(a, data_acesso),
        resumo=(a.get("resumo") or "")[:400] or None,
        licenca=a.get("licenca"),
        area=a.get("area"),
    )


def _texto_busca(resposta_artigos: list[RespostaArtigo], termos_area: str | None) -> str:
    if not resposta_artigos:
        return abstencao.CURTA
    cabecalho = (
        f"Separei {len(resposta_artigos)} "
        f"{'artigo' if len(resposta_artigos) == 1 else 'artigos'} da base curada"
    )
    if termos_area:
        cabecalho += f" em {termos_area}"
    cabecalho += (
        ". Todos têm DOI ou link verificável e licença de acesso aberto registrada. "
        "O motivo de cada um aparece abaixo; peça a referência ABNT pelo número "
        "(por exemplo: \"referência ABNT do segundo artigo\")."
    )
    return cabecalho


def _abster(mensagem: str, traco: Traco, tipo: str = "abstencao") -> Resposta:
    return Resposta(
        resposta=mensagem,
        intencao=traco.intencao_prevista,  # type: ignore[arg-type]
        tipo=tipo,  # type: ignore[arg-type]
        artigos=[],
        fontes=[],
        sugestoes=abstencao.SUGESTOES,
        traco=traco,
    )


# ------------------------------------------------------------------ ações
def _acao_buscar(pergunta: str, ctx, traco: Traco) -> Resposta:
    motor = recuperacao.obter()
    if not motor.pronto:
        traco.acao, traco.regra = "abstencao", "base_ausente"
        return _abster(abstencao.SEM_BASE, traco)

    area = motor.detetar_area(pergunta)
    candidatos = motor.buscar(pergunta, k=TOP_K, area=area)
    traco.n_candidatos = len(candidatos)
    acima = [c for c in candidatos if c.score >= LIMIAR_SCORE]
    traco.score_maximo = candidatos[0].score if candidatos else None
    traco.limiar_score = LIMIAR_SCORE
    traco.termos = [t for t in pergunta.split() if len(t) > 3][:6]
    traco.regra = f"similaridade+curadoria >= {LIMIAR_SCORE}"

    if not acima:
        traco.acao = "abstencao"
        return _abster(abstencao.CURTA, traco)

    ctx.ultima_busca = pergunta
    ctx.abstencao_aos_seguidos = 0
    data_acesso = date.today().isoformat()
    artigos = [_resposta_artigo(c, i, data_acesso) for i, c in enumerate(acima, 1)]
    # guarda os artigos crus para resolver "o segundo artigo" depois
    ctx.guardar_artigos([c.artigo for c in acima], pergunta)
    traco.acao = "recomendar"
    return Resposta(
        resposta=_texto_busca(artigos, area),
        intencao="buscar_referencias",
        tipo="recomendacao",
        artigos=artigos,
        fontes=sorted({a.area for a in artigos if a.area}),
        sugestoes=[
            "Me dá a referência ABNT do primeiro artigo",
            "Tem algo mais recente sobre esse tema?",
            "Como procuro mais artigos no SciELO?",
        ],
        traco=traco,
    )


def _acao_avaliar(pergunta: str, traco: Traco) -> Resposta:
    motor = recuperacao.obter()
    parecer = modulo_periodicos.avaliar(pergunta, motor)
    traco.acao, traco.regra = "parecer", "lista curada de periódicos"
    if not parecer["encontrado"]:
        fontes = ["Não consta na base curada do Artikel"]
    elif parecer["tipo"] == "generica":
        fontes = [f"Fonte avaliada: {parecer['titulo']}"]
    else:
        fontes = [f"{parecer['titulo']}"]
        if parecer["indexacao"]:
            fontes.append("Indexação: " + ", ".join(parecer["indexacao"]))
        if parecer["issns"]:
            fontes.append("ISSN: " + ", ".join(parecer["issns"]))

    return Resposta(
        resposta=parecer["explicacao"],
        intencao="avaliar_fonte",
        tipo="parecer_fonte",
        artigos=[],
        fontes=fontes,
        sugestoes=[
            "Preciso de artigos sobre esse tema",
            "Como procuro artigos no SciELO?",
            "A revista é indexada no DOAJ?",
        ],
        traco=traco,
    )


def _acao_formatar(pergunta: str, ctx, traco: Traco) -> Resposta:
    traco.acao, traco.regra = "referencia_abnt", "NBR 6023 por regras"
    artigo = ctx.artigo_citado(pergunta) if ctx.tem_artigos else None
    traco.contexto_usado = artigo is not None

    if artigo is None:
        if ctx.tem_artigos and ctx.cita_lista(pergunta):
            # citou posição fora do intervalo (ex.: "o nono artigo")
            mensagem = (
                f"A última lista tem {len(ctx.artigos)} artigos. "
                "Peça de 1 a " + str(len(ctx.artigos)) + " ou faça uma nova busca."
            )
            traco.acao = "abstencao"
            traco.regra = "posição fora da lista"
            return _abster(mensagem, traco)
        traco.acao = "abstencao"
        traco.regra = "sem contexto de lista"
        return _abster(abstencao.SEM_CONTEXTO, traco)

    data_acesso = date.today().isoformat()
    referencia = abnt.formatar_referencia(artigo, data_acesso)
    citacao = abnt.formatar_curta(artigo)
    posicao = ctx.posicao(pergunta) or 1

    texto = (
        f"Referência ABNT (NBR 6023) do artigo {posicao}:\n\n{referencia}\n\n"
        f"Na citação no texto: {citacao}. Confira a pontuação com a norma antes de entregar "
        "o trabalho; a referência foi montada só com os campos registrados na base."
    )
    ctx.abstencao_aos_seguidos = 0
    return Resposta(
        resposta=texto,
        intencao="formatar_referencia",
        tipo="referencia_abnt",
        artigos=[_resposta_artigo(recuperacao.Candidato(artigo, 1.0, 1.0), posicao, data_acesso)],
        fontes=["Base curada do Artikel"],
        sugestoes=[
            "Formata o primeiro artigo também",
            "Como fica a referência de artigo com vários autores?",
            "Preciso de mais artigos sobre esse tema",
        ],
        traco=traco,
    )


def _acao_orientar(pergunta: str, traco: Traco) -> Resposta:
    motor = recuperacao.obter()
    area = motor.detetar_area(pergunta)
    base = modulo_faq.obter()
    if not base.pronto:
        traco.acao, traco.regra = "abstencao", "faq_ausente"
        return _abster(abstencao.SEM_FAQ, traco)

    entrada, score = base.responder(pergunta, area)
    traco.acao, traco.regra = "orientar", "FAQ de busca"
    traco.score_maximo = round(score, 4)
    if entrada is None or score < 0.08:
        traco.acao = "abstencao"
        traco.regra = "FAQ sem entrada próxima"
        resposta = Resposta(
            resposta=abstencao.SEM_FAQ,
            intencao="orientar_busca",
            tipo="abstencao",
            sugestoes=base.titulos()[:3],
            traco=traco,
        )
        return resposta

    passos = "\n".join(f"{i}. {p}" for i, p in enumerate(entrada.get("passos", []), 1))
    texto = entrada["resposta"] + (f"\n\nEm três passos:\n{passos}" if passos else "")
    return Resposta(
        resposta=texto,
        intencao="orientar_busca",
        tipo="orientacao_busca",
        artigos=[],
        fontes=[f"FAQ de busca: {entrada['titulo']}"],
        sugestoes=[
            "Preciso de artigos sobre esse tema",
            "A revista X é confiável?",
            "Que palavras-chave uso para achar artigos?",
        ],
        traco=traco,
    )


def _acao_fora_de_escopo(ctx, traco: Traco) -> Resposta:
    ctx.abstencao_aos_seguidos += 1
    traco.acao, traco.regra = "abstencao", "intenção fora de escopo"
    return _abster(abstencao.mensagem_fora_de_escopo(ctx.abstencao_aos_seguidos), traco)


# ------------------------------------------------------------------ porta de entrada
def responder(mensagem: str, sessao: str = "default") -> Resposta:
    """Fluxo completo de uma mensagem. Sempre devolve `Resposta` com traço."""
    ctx = sessoes.obter(sessao)
    classificador = intencoes.obter()
    intencao, confianca = classificador.prever(mensagem)

    traco = Traco(
        intencao_prevista=intencao,
        confianca=round(confianca, 4),
        limiar_confianca=LIMIAR_CONFIANCA,
        acao="",
        regra="",
    )

    if not classificador.carregado:
        traco.acao, traco.regra = "abstencao", "modelo ausente"
        return _abster(abstencao.SEM_BASE, traco)

    # Confiança baixa: o caminho mais seguro é a abstenção, não um palpite.
    if intencao != FORA_DE_ESCOPO and confianca < LIMIAR_CONFIANCA:
        traco.confianca_abaixo_do_limiar = True
        traco.acao, traco.regra = "abstencao", f"confiança {confianca:.2f} < {LIMIAR_CONFIANCA}"
        ctx.abstencao_aos_seguidos += 1
        return _abster(abstencao.CURTA, traco)

    if intencao == "buscar_referencias":
        return _acao_buscar(mensagem, ctx, traco)
    if intencao == "avaliar_fonte":
        ctx.abstencao_aos_seguidos = 0
        return _acao_avaliar(mensagem, traco)
    if intencao == "formatar_referencia":
        return _acao_formatar(mensagem, ctx, traco)
    if intencao == "orientar_busca":
        ctx.abstencao_aos_seguidos = 0
        return _acao_orientar(mensagem, traco)
    return _acao_fora_de_escopo(ctx, traco)
