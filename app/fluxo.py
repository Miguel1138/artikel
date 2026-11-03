"""Orquestrador do fluxo (R4).

Único ponto que encadeia os módulos: entrada -> normalização -> intenção -> busca/regra ->
resposta ou abstenção, sempre com o traço da decisão. Nenhum outro módulo decide limiar.

O bot **nunca** gera texto livre com referências: o que aparece na resposta vem da base
curada (`recuperacao`), da lista de periódicos (`periodicos`), da FAQ (`faq`) ou das regras
ABNT (`abnt`).
"""
from __future__ import annotations

import re
from datetime import date

from config import (
    FORA_DE_ESCOPO,
    LIMIAR_CONFIANCA,
    LIMIAR_ESCLARECIMENTO,
    LIMIAR_SCORE,
    MIN_SEGUNDA_OPCAO,
    TOP_K,
)
import abstencao
import abnt
import faq as modulo_faq
import intencoes
import periodicos as modulo_periodicos
import recuperacao
from contexto import Esclarecimento, resposta_curta, sessoes
from schemas import Resposta, RespostaArtigo, Traco

# Intenções que, com confiança, prevalecem sobre a regra do tema solto.
ACOES_COM_CONFIANCA = {"avaliar_fonte", "formatar_referencia", "orientar_busca"}


def _resposta(traco: Traco, intencao: str, tipo: str, texto: str, sugestoes: list[str],
              artigos: list[RespostaArtigo] | None = None, fontes: list[str] | None = None) -> Resposta:
    return Resposta(
        resposta=texto, intencao=intencao, tipo=tipo, artigos=artigos or [],
        fontes=fontes or [], sugestoes=sugestoes, traco=traco,
    )  # type: ignore[arg-type]


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
    return _resposta(traco, traco.intencao_prevista, tipo, mensagem, abstencao.SUGESTOES)


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
    return _resposta(
        traco, "buscar_referencias", "recomendacao", _texto_busca(artigos, area),
        [
            "Me dá a referência ABNT do primeiro artigo",
            "Tem algo mais recente sobre esse tema?",
            "Como procuro mais artigos no SciELO?",
        ],
        artigos=artigos, fontes=sorted({a.area for a in artigos if a.area}),
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
        fontes = [parecer["titulo"]]
        if parecer["indexacao"]:
            fontes.append("Indexação: " + ", ".join(parecer["indexacao"]))
        if parecer["issns"]:
            fontes.append("ISSN: " + ", ".join(parecer["issns"]))

    return _resposta(
        traco, "avaliar_fonte", "parecer_fonte", parecer["explicacao"],
        [
            "Preciso de artigos sobre esse tema",
            "Como procuro artigos no SciELO?",
            "A revista é indexada no DOAJ?",
        ],
        fontes=fontes,
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
                f"Peça de 1 a {len(ctx.artigos)} ou faça uma nova busca."
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
    return _resposta(
        traco, "formatar_referencia", "referencia_abnt", texto,
        [
            "Formata o primeiro artigo também",
            "Como fica a referência de artigo com vários autores?",
            "Preciso de mais artigos sobre esse tema",
        ],
        artigos=[_resposta_artigo(recuperacao.Candidato(artigo, 1.0, 1.0), posicao, data_acesso)],
        fontes=["Base curada do Artikel"],
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
        return _resposta(traco, "orientar_busca", "abstencao", abstencao.SEM_FAQ, base.titulos()[:3])

    passos = "\n".join(f"{i}. {p}" for i, p in enumerate(entrada.get("passos", []), 1))
    texto = entrada["resposta"] + (f"\n\nEm três passos:\n{passos}" if passos else "")
    return _resposta(
        traco, "orientar_busca", "orientacao_busca", texto,
        [
            "Preciso de artigos sobre esse tema",
            "A revista X é confiável?",
            "Que palavras-chave uso para achar artigos?",
        ],
        fontes=[f"FAQ de busca: {entrada['titulo']}"],
    )


def _acao_fora_de_escopo(ctx, traco: Traco) -> Resposta:
    ctx.abstencao_aos_seguidos += 1
    traco.acao, traco.regra = "abstencao", "intenção fora de escopo"
    return _abster(abstencao.mensagem_fora_de_escopo(ctx.abstencao_aos_seguidos), traco)


def _executar(intencao: str, mensagem: str, ctx, traco: Traco) -> Resposta:
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


# ------------------------------------------------------------------ esclarecimento
def _tema(mensagem: str, limite: int = 80) -> str:
    tema = mensagem.strip().rstrip("?!.: ")
    return tema if len(tema) <= limite else tema[:limite].rsplit(" ", 1)[0] + "…"


_SOBRE = re.compile(r".*\bsobre\s+(.+)$", re.I | re.S)


def _assunto(mensagem: str) -> str | None:
    """O que citar entre aspas na pergunta: o trecho depois do último "sobre" ou a mensagem
    curta inteira ("bactérias resistentes a antibióticos"). Pergunta longa sem "sobre" fica
    sem aspas: repetir a frase toda soa como eco, não como pergunta."""
    texto = mensagem.strip().rstrip("?!.: ")
    m = _SOBRE.match(texto)
    if m:
        return _tema(m.group(1))
    if len(texto.split()) <= 6 and "?" not in mensagem:
        return _tema(texto)
    return None


def _descrever_opcao(intencao: str, mensagem: str, ctx) -> tuple[str, str] | None:
    """(rótulo do botão, descrição para a pergunta), ou None quando a ação não se aplica."""
    if intencao == "buscar_referencias":
        assunto = _assunto(mensagem)
        descricao = (f"que eu procure artigos sobre \"{assunto}\" na base curada" if assunto
                     else "que eu procure artigos sobre isso na base curada")
        return "Procurar artigos sobre isso", descricao
    if intencao == "orientar_busca":
        return "Dicas de como buscar", "dicas de como buscar isso em bases acadêmicas"
    if intencao == "avaliar_fonte":
        return "Avaliar se a fonte é confiável", "saber se essa fonte é confiável para o TCC"
    if intencao == "formatar_referencia":
        # Sem um artigo da lista identificado, confirmar só levaria a outra abstenção.
        artigo = ctx.artigo_citado(mensagem)
        if artigo is None:
            return None
        posicao = ctx.posicao(mensagem)
        titulo = _tema(artigo.get("titulo") or "sem título", 60)
        return f"Referência ABNT do artigo {posicao}", f"a referência ABNT do artigo {posicao} (\"{titulo}\")"
    return None


def _esclarecer(mensagem: str, ctx, classificador, intencao: str, confianca: float,
                traco: Traco) -> Resposta | None:
    """Pergunta "você quer X?" na faixa de confiança baixa, ou None (segue para a abstenção).

    O bot ainda não age: a ação escolhida roda na mensagem seguinte, sobre a pergunta original
    guardada no contexto. Oferece até duas ações, na ordem das probabilidades do classificador.
    """
    if intencao == FORA_DE_ESCOPO or confianca < LIMIAR_ESCLARECIMENTO:
        return None
    probabilidades = getattr(classificador, "probabilidades", None)
    probs = probabilidades(mensagem) if probabilidades else {intencao: confianca}
    acoes = [(i, p) for i, p in sorted(probs.items(), key=lambda kv: -kv[1]) if i != FORA_DE_ESCOPO]

    opcoes = []
    for posicao, (candidata, p) in enumerate(acoes[:2]):
        if posicao == 1 and p < MIN_SEGUNDA_OPCAO:
            break
        descrita = _descrever_opcao(candidata, mensagem, ctx)
        if descrita is not None:
            opcoes.append((candidata, *descrita))
    if not opcoes:
        return None

    descricoes = [d for _, _, d in opcoes]
    if len(opcoes) == 1:
        texto = f"{abstencao.ESCLARECER_UMA.format(a=descricoes[0])}\n\n{abstencao.ESCLARECER_RODAPE_UMA}"
    else:
        texto = (f"{abstencao.ESCLARECER_DUAS.format(a=descricoes[0], b=descricoes[1])}\n\n"
                 f"{abstencao.ESCLARECER_RODAPE_DUAS}")
    ctx.esclarecimento = Esclarecimento(mensagem, [(i, r) for i, r, _ in opcoes], confianca)

    traco.confianca_abaixo_do_limiar = True
    traco.acao = "esclarecimento"
    traco.regra = (f"confiança {confianca:.2f} entre {LIMIAR_ESCLARECIMENTO} e {LIMIAR_CONFIANCA}: "
                   "pergunta antes de agir")
    return _resposta(traco, intencao, "esclarecimento", texto,
                     [r for _, r, _ in opcoes] + [abstencao.NAO_E_ISSO])


def _responder_esclarecimento(pendente: Esclarecimento, escolha: str, ctx) -> Resposta:
    """Resposta à pergunta de esclarecimento: executa a ação escolhida ou aceita o "não"."""
    traco = Traco(
        intencao_prevista=escolha or FORA_DE_ESCOPO,
        confianca=round(pendente.confianca, 4),
        limiar_confianca=LIMIAR_CONFIANCA,
        acao="",
        regra="",
        contexto_usado=True,
    )
    if not escolha:
        traco.acao, traco.regra = "abstencao", "esclarecimento recusado pelo usuário"
        return _abster(abstencao.RECUSA_ESCLARECIMENTO, traco)
    resposta = _executar(escolha, pendente.pergunta, ctx, traco)
    resposta.traco.regra += f" · confirmado pelo usuário (\"{_tema(pendente.pergunta, 60)}\")"
    return resposta


# ------------------------------------------------------------------ porta de entrada
def responder(mensagem: str, sessao: str = "default") -> Resposta:
    """Fluxo completo de uma mensagem. Sempre devolve `Resposta` com traço."""
    ctx = sessoes.obter(sessao)
    # Resposta curta à pergunta de esclarecimento anterior ("sim", o botão, "não"). Qualquer
    # outra mensagem descarta a pergunta e segue o fluxo normal.
    pendente = ctx.tomar_esclarecimento()
    escolha = pendente.resolver(mensagem) if pendente else None
    if escolha is not None:
        return _responder_esclarecimento(pendente, escolha, ctx)

    classificador = intencoes.obter()
    if resposta_curta(mensagem):
        traco = Traco(intencao_prevista=FORA_DE_ESCOPO, confianca=0.0, limiar_confianca=LIMIAR_CONFIANCA,
                      acao="abstencao", regra="resposta curta sem pergunta em aberto")
        return _abster(abstencao.SEM_PERGUNTA_PENDENTE, traco)
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

    # Um assunto solto ("depressão") é uma busca. O classificador decide pela palavra e, para
    # um substantivo sem verbo, erra (aprendeu "ansiedade" nas perguntas clínicas fora de
    # escopo). A evidência melhor é a base reconhecer o tema. A trava: se ele está CONFIANTE
    # de que é outra ação ("scielo" -> avaliar fonte), a decisão dele vale.
    acao_confiante = intencao in ACOES_COM_CONFIANCA and confianca >= LIMIAR_CONFIANCA
    if intencao != "buscar_referencias" or confianca < LIMIAR_CONFIANCA:
        if not acao_confiante and recuperacao.obter().so_tema(mensagem):
            traco.regra = "tema solto reconhecido pela base"
            resposta = _acao_buscar(mensagem, ctx, traco)
            resposta.traco.regra += f" · tema solto (modelo: {intencao} {confianca:.2f})"
            return resposta

    # Confiança baixa: perguntar antes de agir; sem uma ação plausível para oferecer, a
    # abstenção continua sendo o caminho mais seguro, não um palpite.
    if intencao != FORA_DE_ESCOPO and confianca < LIMIAR_CONFIANCA:
        pergunta = _esclarecer(mensagem, ctx, classificador, intencao, confianca, traco)
        if pergunta is not None:
            return pergunta
        traco.confianca_abaixo_do_limiar = True
        traco.acao, traco.regra = "abstencao", f"confiança {confianca:.2f} < {LIMIAR_CONFIANCA}"
        ctx.abstencao_aos_seguidos += 1
        return _abster(abstencao.CURTA, traco)

    return _executar(intencao, mensagem, ctx, traco)
