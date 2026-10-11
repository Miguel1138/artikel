"""Testes do relatório de avaliação gerado por `tests/avaliar.py --md`.

Existem por causa de um problema real: o gerador escrevia o arquivo inteiro, então rodar
`avaliar.py --md docs/avaliacao.md` apagava a "Análise de 3 falhas" — que é exigência do
Marco 5 — sem avisar ninguém.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))
sys.path.insert(0, str(RAIZ / "tests"))

import avaliar  # noqa: E402

RESULTADO_MINIMO = {
    "total_casos": 30,
    "acuracia": 0.9,
    "precisao_at_5": 0.7,
    "abstencao_fora_de_escopo": 1.0,
    "citacoes_inventadas": 0,
    "casos_com_busca": 7,
    "fora_de_escopo_total": 6,
    "matriz_confusao": {i: {j: 0 for j in avaliar.INTENCOES} for i in avaliar.INTENCOES},
    "registros": [],
}


def test_relatorio_tem_os_marcadores():
    texto = avaliar.relatorio_md(dict(RESULTADO_MINIMO))
    assert avaliar.INICIO_GERADO in texto
    assert avaliar.FIM_GERADO in texto
    assert texto.index(avaliar.INICIO_GERADO) < texto.index(avaliar.FIM_GERADO)


def test_relatorio_traz_as_quatro_metricas():
    texto = avaliar.relatorio_md(dict(RESULTADO_MINIMO))
    for esperado in ("Acurácia de intenções", "Precisão@5 da recuperação",
                     "Abstenção correta fora de escopo", "Citações inventadas",
                     "Matriz de confusão"):
        assert esperado in texto


def test_gerador_preserva_o_texto_fora_dos_marcadores(dir_temporario):
    """O caso real: análise escrita à mão abaixo do trecho gerado tem de sobreviver."""
    caminho = dir_temporario / "avaliacao.md"
    analise = "\n## Análise de 3 falhas\n\nTexto escrito à mão que não pode sumir.\n"
    caminho.write_text(avaliar.relatorio_md(dict(RESULTADO_MINIMO)) + analise, encoding="utf-8")

    novo = avaliar.relatorio_md({**RESULTADO_MINIMO, "total_casos": 31})
    avaliar.gravar_md(str(caminho), novo)

    salvo = caminho.read_text(encoding="utf-8")
    assert "Texto escrito à mão que não pode sumir." in salvo
    assert "**31**" in salvo, "o trecho gerado precisa ser atualizado"
    assert salvo.count(avaliar.INICIO_GERADO) == 1
    assert salvo.count(avaliar.FIM_GERADO) == 1


def test_gerador_preserva_texto_antes_dos_marcadores(dir_temporario):
    caminho = dir_temporario / "avaliacao.md"
    antes = "# Preâmbulo escrito à mão\n\n"
    caminho.write_text(antes + avaliar.relatorio_md(dict(RESULTADO_MINIMO)), encoding="utf-8")
    avaliar.gravar_md(str(caminho), avaliar.relatorio_md({**RESULTADO_MINIMO, "total_casos": 32}))
    salvo = caminho.read_text(encoding="utf-8")
    assert salvo.startswith(antes)
    assert "**32**" in salvo


def test_arquivo_sem_marcadores_nao_e_sobrescrito(dir_temporario, capsys):
    """Arquivo antigo, escrito antes dos marcadores: não apaga, gera um .novo ao lado."""
    caminho = dir_temporario / "avaliacao.md"
    original = "# Relatório antigo, sem marcadores\n\nconteúdo que não pode ser perdido\n"
    caminho.write_text(original, encoding="utf-8")

    avaliar.gravar_md(str(caminho), avaliar.relatorio_md(dict(RESULTADO_MINIMO)))

    assert caminho.read_text(encoding="utf-8") == original
    assert Path(str(caminho) + ".novo").exists()
    assert "ATENÇÃO" in capsys.readouterr().out


def test_arquivo_novo_e_criado_com_marcadores(dir_temporario):
    caminho = dir_temporario / "novo.md"
    avaliar.gravar_md(str(caminho), avaliar.relatorio_md(dict(RESULTADO_MINIMO)))
    assert avaliar.INICIO_GERADO in caminho.read_text(encoding="utf-8")


def test_o_documento_do_repositorio_tem_a_analise_exigida():
    """O Marco 5 pede a análise de 3 falhas: ela precisa estar no arquivo versionado."""
    texto = (RAIZ / "docs" / "avaliacao.md").read_text(encoding="utf-8")
    assert "Análise de 3 falhas" in texto
    assert avaliar.INICIO_GERADO in texto, "rode avaliar.py --md para gerar o trecho"
