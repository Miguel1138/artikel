# Pendências conhecidas

Registro do que ficou aberto ao final da implementação dos pontos já tratados do documento
unificado do projeto (11/10/2026). Dois tipos: pendências **de conteúdo** (dependem da
equipe ou do professor) e pendências **de infraestrutura** (do ambiente onde o projeto foi
montado, não do código).

## Bugs de re-execução da coleta — corrigidos

Duas falhas reais apareceram quando o pipeline foi rodado pela segunda vez, depois de o
cache de `data/raw/` já estar populado. As duas estavam escondidas na primeira execução e
foram corrigidas com teste de regressão em `tests/test_pipeline_coleta.py`.

### 1. `TypeError` ao ler o cache do DOAJ (quebrava a execução)

```
File "scripts/coleta/doaj.py", line 143, in periodicos_computacao_cc
    return {p["issn"]: p for p in cache}
TypeError: cannot use 'list' as a dict key (unhashable type: 'list')
```

**Causa:** cada periódico tem **uma lista** de ISSNs (impresso e eletrônico); o caminho de
escrita montava o índice num laço interno, o de leitura usava a lista direto como chave. A
primeira execução gravava o cache e nunca passava por ali — o erro só aparecia na segunda.

**Correção:** `doaj._indexar_por_issn`, usada nos dois caminhos.

### 2. Re-rodar uma área apagava a área da base (perda de dados)

**Sintoma:** `python scripts/coleta/pipeline.py --area computacao` numa base que já tinha os
47 artigos de Computação gravava **0 artigos** — a área sumia.

**Causa:** para recolher uma área, o `main` removia os artigos dela antes de recoletar. Se a
recoleta não trouxesse nada (cache, rede, filtro), o dado antigo já tinha sido descartado.

**Correção:** `pipeline.main` guarda os artigos anteriores de cada área e, se a recoleta
voltar vazia, mantém o que já estava na base, com aviso no console. E o merge passou a ser
testável sem rede (`main(..., arquivos=..., coletar=...)`), o que permitiu fixar o
comportamento: primeira execução grava, re-execução preserva, re-execução com artigos novos
substitui pelo mesmo DOI sem duplicar.

**Como saber se a sua execução foi afetada:** a base deve ter **246 artigos** e nenhuma área
zerada. Confira com:

```bash
python -c "import json,collections;b=json.load(open('data/knowledge_base.json',encoding='utf-8'));print(len(b),collections.Counter(a['area'] for a in b))"
```

Se alguma área aparecer com 0, basta rodar o pipeline daquela área de novo (agora ele não
apaga mais nada).

### 3. A coleta não é idempotente — o número varia um pouco

**Sintoma:** rodar a coleta completa duas vezes seguidas dá resultados ligeiramente
diferentes (246 e 247 artigos, em duas medições). Não é bug: cada execução reconsulta as
APIs e revalida cada DOI no Crossref, então uma resposta instável (429, timeout, DOI que
deixou de resolver) tira um artigo do recorte. O que **não** varia: nenhuma área é zerada, o
recorte (período, idioma, licença) é sempre aplicado e todo artigo tem DOI e licença
registrada.

**Consequência para o trabalho:** números da base citados no relatório devem vir de uma
execução única e identificada, com a data em `data/relatorio_coleta.md`. Para reproduzir
exatamente um número antigo, restaure o `knowledge_base.json` versionado em vez de rodar a
coleta de novo.

## Interface: de React via CDN para JavaScript local

A primeira versão da interface usava React 18 + Babel carregados de `unpkg.com`, e **ficava
em branco** na máquina da equipe: `unpkg.com`, `cdn.jsdelivr.net`,
`cdnjs.cloudflare.com`, `esm.sh` e o registro npm estão inacessíveis, e não há cópia local
de React. Como os scripts não carregavam, o `div#raiz` nunca era preenchido — sem mensagem
de erro, apenas a página vazia.

**Correção:** `web/app.js` reescrito em JavaScript puro, sem dependência externa, com a
própria API servindo a pasta `web/` em `/` (um servidor só, mesma origem, sem CORS). O
contrato da API e o que a interface mostra não mudaram — está tudo em
[`web/README.md`](../web/README.md).

**Se a equipe quiser React no Marco 4:** usar `npm create vite@latest` com a rede liberada.
O cliente muda; o contrato de `/chat` continua igual.

**Como isso passa a ser verificado** (antes não era):

```bash
node web/_verificar_interface.js                       # roda o app.js num DOM mínimo
node web/_verificar_contrato.js http://127.0.0.1:8000  # API real contra o que o front lê
```

## De conteúdo — dependem da equipe

| # | Pendência | Onde | Marco |
|---|---|---|---|
| 1 | Distribuir os quatro papéis entre os integrantes (o TAP ainda diz "a definir") | `docs/contribuicoes.md` | 2 |
| 2 | Colher as assinaturas de aprovação do TAP (professor e gerente) | TAP | 2 |
| 3 | Avisar o professor que a coleta usa APIs públicas só de leitura, fora do chatbot | conversa com o professor | 2 |
| 4 | Confirmar o DOAJ Article Search como fonte complementar de Computação e registrar a decisão | `docs/especificacao.md`, seção 7 | 3 |
| 5 | Revisar os limiares de confiança e de score com a distribuição real de scores | `app/config.py` | 3 |
| 6 | Desenhar o `docs/fluxograma.png` a partir de `docs/fluxograma.md` (Mermaid) | `docs/` | 3 |
| 7 | Levar Computação de 46 para perto de 100 artigos (ampliar sementes ou fontes) | `scripts/coleta/config_coleta.py` | 2–3 |
| 8 | Ampliar a amostra julgada da Precisão@5 (hoje 7 dos 30 casos) com dois juízes | `tests/casos_teste.csv` | 5–6 |
| 9 | Escrever o relatório de 6+ páginas e o roteiro da demonstração de 8 minutos | `docs/` | 6 |
| 10 | Preencher a declaração de uso de IA generativa | `docs/contribuicoes.md` | 6 |

## De infraestrutura — do ambiente, não do código

### Diretórios temporários que não podem ser apagados

Sobraram na raiz do repositório quatro diretórios **vazios**, criados durante a
implementação e que o Windows recusa apagar:

```
.tmp_acl_9p1092tv/
.tmp_pytest/
.tmp_testes/
.tmp_teste_r4tt4wjp/
```

**Causa:** o controle de acesso dessas pastas herda uma negação de
`DeleteSubdirectoriesAndFiles` para "Todos". A ferramenta de diagnóstico de permissões do
ambiente rodou sobre a raiz do projeto
(`diagnose-windows-sandbox-acl.ps1`) e concluiu `NOT_THIS_CLASS`: as permissões do projeto
estão corretas (`WRITE_DAC` e `WRITE_OWNER` disponíveis, nenhuma entrada de pacote
estranho), e a negação observada é esperada nesse ambiente — não é um problema de ACL que o
script repare. Também apareceram `pytest-cache-files-*` pelo mesmo motivo.

**Efeito:** nenhum no funcionamento do projeto. O `.gitignore` já ignora `.tmp_*/` e
`*.pyc`, então esses diretórios não entram no Git.

**Como limpar (manual, com o Windows):**

```powershell
cd D:\Users\Lenovo\Documents\projetos\PycharmProjects\artikel
Remove-Item -Recurse -Force .tmp_acl_*, .tmp_pytest, .tmp_testes, .tmp_teste_*, pytest-cache-files-*
```

Se continuar negado, apague pelo Explorer: selecione as pastas, `Shift+Delete` e confirme a
elevação de administrador.

### Consequência nos testes

Por causa dessa restrição, `pytest` não consegue usar o diretório temporário do sistema nem
o `tmp_path` padrão. Os testes que precisam escrever arquivos usam a fixture
`dir_temporario` (`conftest.py`), que cria `tests/_temporario/` dentro do repositório e
apaga no fim de cada teste. **Não troque por `tmp_path`**: os testes passam a falhar com
`PermissionError` neste ambiente.

```bash
python -m pytest -q      # 70 testes
```
