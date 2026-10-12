"""API do Artikel (FastAPI) — também serve a interface.

Como rodar (da raiz do repositório, com a venv ativa):

    uvicorn main:app --app-dir app --reload

Depois abra **http://127.0.0.1:8000/** — a interface é servida pela própria API, na mesma
origem, então não há CORS nem um segundo servidor para subir.

Endpoints:
    GET  /           interface (web/)
    GET  /saude      estado da base, do modelo e dos limiares
    POST /chat       fluxo completo com o traço da decisão
    GET  /artigos    consulta direta à base curada
    GET  /periodicos lista curada usada no parecer de fonte
    POST /sessao/{id}/limpar  limpa o contexto da sessão
"""
from __future__ import annotations

import faq as modulo_faq
import fluxo
import intencoes
import recuperacao
from config import (ANO_FIM, ANO_INICIO, DIR_WEB, LIMIAR_CONFIANCA, LIMIAR_SCORE,
                    TITULO_API, VERSAO_API)
from contexto import sessoes
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from schemas import Mensagem, Resposta, Saude

app = FastAPI(title=TITULO_API, version=VERSAO_API)

# CORS liberado para o caso de a equipe rodar a interface num servidor separado
# (ex.: `python -m http.server 5173 --directory web`, ou o Vite no Marco 4).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/saude", response_model=Saude)
def saude() -> Saude:
    motor = recuperacao.obter()
    base = modulo_faq.obter()
    stats = motor.estatisticas()
    return Saude(
        status="ok" if motor.pronto else "base_ausente",
        artigos_na_base=stats["artigos"],
        periodicos_na_base=stats["periodicos"],
        entradas_faq=len(base.entradas),
        modelo_carregado=intencoes.obter().carregado,
        limiar_confianca=LIMIAR_CONFIANCA,
        limiar_score=LIMIAR_SCORE,
        recorte_anos=[ANO_INICIO, ANO_FIM],
        areas=stats["areas"],
        avisos=intencoes.obter().avisos,
    )


@app.post("/chat", response_model=Resposta)
def chat(mensagem: Mensagem) -> Resposta:
    return fluxo.responder(mensagem.mensagem, mensagem.sessao)


@app.post("/sessao/{sessao}/limpar")
def limpar_sessao(sessao: str) -> dict:
    sessoes.limpar(sessao)
    return {"sessao": sessao, "contexto": "limpo"}


@app.get("/artigos")
def listar_artigos(
    area: str | None = None,
    ano: int | None = None,
    limite: int = Query(default=20, ge=1, le=200),
) -> dict:
    motor = recuperacao.obter()
    if not motor.pronto:
        raise HTTPException(status_code=503, detail=motor.erro or "base indisponível")
    itens = [
        a for a in motor.artigos
        if (area is None or a.get("area") == area) and (ano is None or a.get("ano") == ano)
    ]
    return {"total": len(itens), "artigos": itens[:limite]}


@app.get("/periodicos")
def listar_periodicos() -> dict:
    motor = recuperacao.obter()
    if not motor.pronto:
        raise HTTPException(status_code=503, detail=motor.erro or "base indisponível")
    return {"total": len(motor.periodicos()), "periodicos": motor.periodicos()}


# --- interface ---------------------------------------------------------
# Montado por último: as rotas da API têm prioridade sobre os arquivos estáticos.
if DIR_WEB.exists():
    app.mount("/", StaticFiles(directory=DIR_WEB, html=True), name="web")
else:
    @app.get("/")
    def sem_interface() -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": f"interface ausente em {DIR_WEB}; a API continua em /saude e /chat"},
        )
