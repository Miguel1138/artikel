"""Referência ABNT NBR 6023 por regras próprias, sem LLM (R3, objetivo 4).

Formato de artigo de periódico:

    SOBRENOME, Nome; SOBRENOME, Nome. Título do artigo. **Título do periódico**,
    v. 12, n. 3, p. 45-67, 2023. DOI: 10.xxxx/yyyy. Disponível em: URL.
    Acesso em: 11 out. 2026.

Regras implementadas (e testadas em `tests/test_abnt.py`):
- até 3 autores: todos; 4 ou mais: o primeiro seguido de "et al."
- autores separados por ponto e vírgula
- subtítulo depois dos dois-pontos mantém a grafia original
- local ausente não é inventado (NBR 6023 dispensa local para artigo de periódico)
- "Disponível em" só aparece quando há URL; "Acesso em" só quando há data de acesso
- o que falta é omitido, nunca preenchido com texto inventado
"""
from __future__ import annotations

import re

MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.",
         "jul.", "ago.", "set.", "out.", "nov.", "dez."]

MAX_AUTORES = 3


def _limpar(texto: str | None) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip())


def formatar_autores(autores: list[dict] | list[str] | None) -> str:
    """SOBRENOME, Nome; SOBRENOME, Nome. ... com 'et al.' a partir de 4 autores.

    Sem ponto final: quem fecha o bloco de autoria é `formatar_referencia`, para não
    produzir "et al.." na junção.
    """
    if not autores:
        return ""

    def um(a) -> str:
        if isinstance(a, str):
            return _limpar(a)
        sobrenome = _limpar(a.get("sobrenome"))
        nome = _limpar(a.get("nome"))
        if sobrenome and nome:
            return f"{sobrenome.upper()}, {nome}"
        return (sobrenome or nome).upper()

    partes = [um(a) for a in autores if um(a)]
    if not partes:
        return ""
    if len(partes) > MAX_AUTORES:
        return f"{partes[0]} et al"
    return "; ".join(partes)


def formatar_data_acesso(iso: str | None) -> str:
    """'2026-10-11' -> '11 out. 2026'."""
    if not iso:
        return ""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso)
    if not m:
        return ""
    ano, mes, dia = m.group(1), int(m.group(2)), int(m.group(3))
    if not 1 <= mes <= 12:
        return ""
    return f"{dia} {MESES[mes - 1]} {ano}"


def _com_ponto(texto: str) -> str:
    """Fecha o bloco com ponto, sem duplicar o que já termina em ponto ou vírgula."""
    texto = texto.strip()
    if not texto:
        return ""
    return texto if texto.endswith((".", ",", ";")) else texto + "."


def formatar_referencia(artigo: dict, data_acesso: str | None = None) -> str:
    """Monta a referência NBR 6023 de um registro da base."""
    partes: list[str] = []

    autores = formatar_autores(artigo.get("autores"))
    titulo = _limpar(artigo.get("titulo"))
    periodico = _limpar(artigo.get("periodico"))

    # ABNT: "SOBRENOME, Nome. Título." — o ponto entre blocos vem do separador.
    inicio = ". ".join(p for p in (autores, titulo) if p)
    if inicio:
        partes.append(_com_ponto(inicio))

    # periódico + dados de volume/ano
    detalhes: list[str] = []
    if periodico:
        detalhes.append(periodico)
    if artigo.get("volume"):
        detalhes.append(f"v. {_limpar(str(artigo['volume']))}")
    if artigo.get("numero"):
        detalhes.append(f"n. {_limpar(str(artigo['numero']))}")
    if artigo.get("paginas"):
        detalhes.append(f"p. {_limpar(str(artigo['paginas']))}")
    if artigo.get("ano"):
        detalhes.append(str(artigo["ano"]))
    if detalhes:
        partes.append(_com_ponto(", ".join(detalhes)))

    if artigo.get("doi"):
        partes.append(f"DOI: {_limpar(artigo['doi'])}.")
    if artigo.get("url"):
        partes.append(f"Disponível em: {_limpar(artigo['url'])}.")
    acesso = formatar_data_acesso(data_acesso)
    if acesso:
        partes.append(f"Acesso em: {acesso}.")

    return " ".join(partes).strip()


def formatar_curta(artigo: dict) -> str:
    """Citação no texto: (SOBRENOME, ano) ou (SOBRENOME et al., ano)."""
    autores = artigo.get("autores") or []
    ano = artigo.get("ano") or "s.d."
    if not autores:
        return f"({ano})"
    primeiro = autores[0]
    if isinstance(primeiro, str):
        sobrenome = primeiro
    else:
        sobrenome = primeiro.get("sobrenome") or primeiro.get("nome") or ""
    sobrenome = _limpar(sobrenome).upper()
    if len(autores) > MAX_AUTORES:
        return f"({sobrenome} et al., {ano})"
    return f"({sobrenome}, {ano})"
