"""Testes do pipeline de coleta — o merge entre execuções.

Estes testes existem por causa de dois bugs reais de re-execução:

1. `doaj.periodicos_computacao_cc()` quebrava ao ler o próprio cache
   (`TypeError: unhashable type: 'list'`), porque o ISSN de um periódico é uma **lista**;
   o caminho de escrita funcionava e o de leitura, não. Só aparecia na segunda execução.
2. Re-rodar uma área apagava a área da base: os artigos antigos eram removidos antes de
   recolher, e quando a recoleta não trazia nada (cache, rede, filtro), o resultado era
   uma base vazia naquela área.

O teste roda o `main` com uma coleta injetada (`coletar`), então não usa rede e não toca
em `data/`.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "coleta"))

import doaj  # noqa: E402
import pipeline  # noqa: E402


# ------------------------------------------------------------------ cache do DOAJ
def test_indexar_por_issn_aceita_lista_de_issns():
    lista = [
        {"titulo": "Logical Methods", "issn": ["1860-5974", "1860-5982"]},
        {"titulo": "Big Data", "issn": ["2096-0654"]},
    ]
    indice = doaj._indexar_por_issn(lista)
    assert set(indice) == {"1860-5974", "1860-5982", "2096-0654"}
    assert indice["1860-5982"]["titulo"] == "Logical Methods"


def test_indexar_por_issn_ignora_periodico_sem_issn():
    assert doaj._indexar_por_issn([{"titulo": "Sem ISSN", "issn": []}]) == {}


def test_periodicos_computacao_cc_le_o_cache(dir_temporario, monkeypatch):
    """O caminho de leitura do cache — o que quebrava na segunda execução."""
    cache = dir_temporario / "periodicos_computacao_cc.json"
    cache.write_text(json.dumps([
        {"titulo": "Logical Methods in Computer Science", "issn": ["1860-5974"],
         "licenca": "cc-by"},
    ]), encoding="utf-8")
    monkeypatch.setattr(doaj, "ler_raw", lambda fonte, nome: json.loads(
        cache.read_text(encoding="utf-8")))
    indice = doaj.periodicos_computacao_cc()
    assert indice["1860-5974"]["titulo"] == "Logical Methods in Computer Science"


def test_periodicos_computacao_cc_nao_usa_rede_com_cache(monkeypatch):
    monkeypatch.setattr(doaj, "ler_raw", lambda fonte, nome: [{"titulo": "X", "issn": ["1"]}])
    monkeypatch.setattr(doaj, "get_json", lambda *a, **k: pytest.fail("não deve ir à rede"))
    assert doaj.periodicos_computacao_cc()["1"]["titulo"] == "X"


# ------------------------------------------------------------------ merge por área
def artigo(id_, area, doi):
    return {"id": id_, "area": area, "doi": doi, "titulo": f"T {id_}",
            "autores": [], "ano": 2024, "issn": [], "palavras_chave": [],
            "fonte": "teste", "data_coleta": "2026-10-11"}


def coletor_fixo(por_area):
    """Devolve um `coletar` que finge a coleta de cada área."""
    def coletar(area, vistos, funil, scielo_por_issn, periodicos):
        registros = [dict(r) for r in por_area.get(area, [])]
        novos = [r for r in registros if r.get("doi") not in vistos]
        vistos.update(r["doi"] for r in novos if r.get("doi"))
        return novos
    return coletar


@pytest.fixture
def arquivos(dir_temporario):
    """Redireciona as três saídas do Load para a pasta de apoio do teste."""
    base = dir_temporario / "knowledge_base.json"
    revistas = dir_temporario / "periodicos.json"
    relatorio = dir_temporario / "relatorio_coleta.md"
    revistas.write_text("[]", encoding="utf-8")
    return base, revistas, relatorio


def ler(base):
    return json.loads(base.read_text(encoding="utf-8"))


def test_primeira_execucao_grava_a_area(arquivos):
    base, revistas, relatorio = arquivos
    pipeline.main(areas=["computacao"], arquivos=(base, revistas, relatorio),
                  coletar=coletor_fixo({"computacao": [artigo("a", "computacao", "10.1/a")]}))
    assert [a["area"] for a in ler(base)] == ["computacao"]
    assert relatorio.exists()


def test_re_execucao_preserva_a_area(arquivos):
    """Recoleta vazia + base com artigos = base intacta (o bug de perda de dados)."""
    base, revistas, relatorio = arquivos
    base.write_text(json.dumps([artigo("a", "computacao", "10.1/a"),
                               artigo("b", "odontologia", "10.1/b")]), encoding="utf-8")
    pipeline.main(areas=["computacao"], arquivos=(base, revistas, relatorio),
                  coletar=coletor_fixo({"computacao": []}))
    resultado = ler(base)
    areas = Counter(a["area"] for a in resultado)
    assert areas["computacao"] == 1, "a área não pode ser apagada por uma recoleta vazia"
    assert areas["odontologia"] == 1, "a outra área não pode ser tocada"


def test_merge_nao_duplica_a_area_recoletada(arquivos):
    base, revistas, relatorio = arquivos
    base.write_text(json.dumps([artigo("a", "computacao", "10.1/a")]), encoding="utf-8")
    pipeline.main(areas=["computacao"], arquivos=(base, revistas, relatorio),
                  coletar=coletor_fixo({"computacao": [
                      artigo("novo", "computacao", "10.1/a"),
                      artigo("novo2", "computacao", "10.1/c")]}))
    doises = [a["doi"] for a in ler(base)]
    assert sorted(doises) == ["10.1/a", "10.1/c"]


def test_merge_soma_area_nova_as_existentes(arquivos):
    base, revistas, relatorio = arquivos
    base.write_text(json.dumps([artigo("a", "odontologia", "10.1/a")]), encoding="utf-8")
    pipeline.main(areas=["computacao"], arquivos=(base, revistas, relatorio),
                  coletar=coletor_fixo({"computacao": [artigo("b", "computacao", "10.1/b")]}))
    assert Counter(a["area"] for a in ler(base)) == Counter({"odontologia": 1, "computacao": 1})


def test_ids_sao_renumerados_e_unicos(arquivos):
    base, revistas, relatorio = arquivos
    base.write_text(json.dumps([artigo("a", "odontologia", "10.1/a"),
                               artigo("b", "psicologia", "10.1/b")]), encoding="utf-8")
    pipeline.main(areas=["computacao"], arquivos=(base, revistas, relatorio),
                  coletar=coletor_fixo({"computacao": [artigo("c", "computacao", "10.1/c")]}))
    ids = [a["id"] for a in ler(base)]
    assert len(ids) == len(set(ids)) == 3
    assert ids[0] == "art_001"


def test_campos_internos_nao_vazam_para_a_base(arquivos):
    base, revistas, relatorio = arquivos
    registro = artigo("a", "computacao", "10.1/a")
    registro["_data"] = "2024-01-01"      # campo interno do pipeline
    pipeline.main(areas=["computacao"], arquivos=(base, revistas, relatorio),
                  coletar=coletor_fixo({"computacao": [registro]}))
    assert "_data" not in ler(base)[0]


def test_artigo_reaproveitado_recebe_data_para_ordenacao():
    """Registro vindo do JSON já gravado não tem `_data`; sem isso ele cai para o fim."""
    interno = pipeline.recuperar_interno({"ano": 2023, "titulo": "X"})
    assert interno["_data"] == "2023-01-01"
    assert "_data" not in {k: v for k, v in interno.items() if k == "titulo"}


def test_base_da_area_separa_o_que_sera_recoletado():
    regs = [artigo("a", "computacao", "1"), artigo("b", "odontologia", "2"),
            artigo("c", "computacao", "3")]
    outras, anteriores = pipeline.base_da_area(regs, ["computacao"])
    assert [r["id"] for r in outras] == ["b"]
    assert [r["id"] for r in anteriores["computacao"]] == ["a", "c"]


def test_area_desconhecida_falha_antes_de_qualquer_coisa(arquivos):
    base, revistas, relatorio = arquivos
    with pytest.raises(SystemExit):
        pipeline.main(areas=["astronomia"], arquivos=(base, revistas, relatorio),
                      coletar=coletor_fixo({}))
    assert not base.exists()


# ------------------------------------------------------------------ área e período
def test_medicina_nao_absorve_odontologia_nem_informatica_medica():
    """O prefixo LCC "R" de Medicina contém RK (Odontologia) e R858 (informática médica)."""
    assert pipeline.lcc_da_area("medicina", ["RC254-282"])
    assert pipeline.lcc_da_area("medicina", ["R"])
    assert not pipeline.lcc_da_area("medicina", ["RK1-715"])
    assert not pipeline.lcc_da_area("medicina", ["R858-859.7"])
    assert pipeline.lcc_da_area("odontologia", ["RK1-715"])
    assert pipeline.lcc_da_area("biologia", ["QH301-705.5"])
    assert not pipeline.lcc_da_area("biologia", ["QA75.5-76.95"])


def test_area_wos_de_odontologia_nao_conta_como_medicina():
    """'DENTISTRY, ORAL SURGERY & MEDICINE' contém MEDICINE e SURGERY."""
    import comum
    assert not comum.wos_da_area("medicina", ["DENTISTRY, ORAL SURGERY & MEDICINE"])
    assert comum.wos_da_area("odontologia", ["DENTISTRY, ORAL SURGERY & MEDICINE"])
    assert comum.wos_da_area("medicina", ["MEDICINE, GENERAL & INTERNAL"])
    assert comum.wos_da_area("biologia", ["MARINE & FRESHWATER BIOLOGY"])
    assert not comum.wos_da_area("biologia", ["PSYCHOLOGY, BIOLOGICAL"])


def test_intercalar_anos_espalha_a_cota_pelo_periodo():
    """Validar do mais recente para trás enchia a cota com os últimos dois anos."""
    regs = [{"doi": f"{ano}/{n}", "ano": ano, "_data": f"{ano}-0{n}-01"}
            for ano in (2016, 2025, 2026) for n in (1, 2)]
    ordem = [r["ano"] for r in pipeline.intercalar_anos(regs)]
    assert ordem == [2026, 2025, 2016, 2026, 2025, 2016]
    assert pipeline.intercalar_anos([]) == []
