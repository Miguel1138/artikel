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

### 4. A avaliação não era determinística (Precisão@5 oscilava entre 0,657 e 0,743)

**Sintoma:** duas execuções de `tests/avaliar.py`, com a mesma base e o mesmo modelo, davam
Precisão@5 diferentes. Um número que muda sozinho não serve para o relatório.

**Causa:** o caso 13 ("queria uma lista de referências sobre depressão em adolescentes")
devolvia 3 artigos numa rodada e 5 na outra. A cobertura temática somava os pesos dos termos
iterando um `set`; a ordem de um `set` de strings muda a cada processo (hash randomization),
e somar `float` em ordem diferente dá resultado diferente. Dois artigos ficavam exatamente
no limiar, então o ruído de ponto flutuante decidia se entravam.

**Correção:** a soma passou a ser feita em ordem fixa (termos ordenados) e o valor que
decide o corte é arredondado antes da comparação. Coberto por dois testes em
`tests/test_recuperacao_periodicos.py`, e há um diagnóstico dedicado:
`python scripts/diagnostico/_diag_determinismo.py 8` (roda a avaliação 8 vezes e acusa
variação). Resultado depois da correção: 0,743 em 8 de 8 rodadas.

### 5. Busca de tema ausente devolvia artigo de outra área (relatado pelo usuário)

**Sintoma:** "preciso de artigos sobre computação quântica" devolvia 5 artigos de
**Psicologia e Odontologia**. O mesmo acontecia com física quântica, criptografia quântica,
direito penal, engenharia civil e medicina veterinária — nenhum desses temas existe na base.

**Causa:** duas falhas somadas.

1. O casamento de termo cortava a palavra em 5 letras e aceitava qualquer início de palavra.
   "quântica" virava `quant`, que casava com **"quantitative"** — então um artigo de
   Psicologia que diz "quantitative methods" contava como cobertura de computação quântica.
2. O bônus de curadoria (indexado + recente = 0,08) era somado **depois** da guarda temática,
   por cima de uma similaridade de 0,06. O artigo chegava a 0,14 e passava do limiar de
   score — inclusive artigos sem **nenhuma** palavra da pergunta ("termos presentes: NENHUM"
   com score 0,14). O bônus de desempate estava funcionando como se fosse relevância.

**Correção:** o casamento passou a exigir palavra inteira ou flexão simples (e sinônimo
declarado em `ALIASES`); o bônus só é aplicado quando o artigo cobre algum termo da pergunta;
o limiar de cobertura subiu de 0,34 para **0,60**; e verbos/moldes de pergunta ("cadê",
"acha", "manda", "quero"…) saíram da conta de cobertura.

O valor 0,60 não foi escolhido por intuição:
`python scripts/diagnostico/_diag_limiar_cobertura.py` compara 10 perguntas que devem achar
artigo com 6 fora do recorte, em cinco limiares. Em 0,34 e 0,5 ainda passavam duas perguntas
fora do tema; em 0,6 nenhuma passa e nenhuma pergunta legítima fica sem resposta.

**Como verificar:** `python scripts/diagnostico/_verificar_retornos.py` (fala com a API real
e confere 6 perguntas de dentro e 8 de fora do escopo) e quatro testes em
`tests/test_recuperacao_periodicos.py`.

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
python -m pytest -q      # 83 testes
```

## Busca por paráfrase e roteamento de intenção — estado em 12/10/2026

A base é 84% inglês (206 de 246 artigos) e as perguntas são em português. A busca era lexical
com um `ALIASES` escrito à mão; paráfrase fora dele ("gengivite", "doença", "cibersegurança")
resultava em abstenção, de forma segura mas errada.

**O que foi feito:** `data/glossario_pt_en.json` (131 termos, gerado por
`scripts/gerar_glossario.py` a partir do Open Multilingual WordNet do NLTK, com aprovação
manual — o WordNet sozinho traduz "pais" por *country*); peso da cobertura pela união das
variantes pt/en; cobertura parcial só preenche quando há menos de 3 artigos completos;
palavras de enchimento ("bibliografia", "pequenas", "aplicada") fora dos termos temáticos.
`tests/test_integracao_api.py` mede com 24 perguntas fora do treino: **8/24 → 18/24**, 0 de 14
temas ausentes vazaram, e as métricas oficiais ficaram iguais (Precisão@5 0,743; abstenção
1,000). Ressalva: as 12 perguntas de `BUSCAS_VALIDACAO` foram escritas antes do léxico, mas as
falhas delas orientaram o que entrou nele (ex.: carbamida, suicídio, sentimento) e a lista de
palavras de enchimento. Não são mais um conjunto limpo; para medir generalização, escreva
perguntas novas.

**Segue aberto** (marcado `xfail` nos testes, com o motivo):

1. **Intenção sem verbo de pedido.** "Relação entre pais e filhos", "análise de sentimentos em
   textos" e "o que a literatura diz sobre…" caem em `fora_de_escopo`: `data/intents.csv` não
   tem frases só com o tema. Precisa de exemplos novos no dataset (não reutilizar as frases
   do teste).
2. **"Referência" puxa para `formatar_referencia`.** "Dá pra confiar na Frontiers in Psychology
   como referência?" é um parecer de fonte. O classificador decide pela palavra, não pelo
   contexto; Bag of Words não resolve (medido em `scripts/diagnostico/_diag_vetorizador.py`).
3. **Cobertura parcial fraca** quando poucos artigos cobrem todos os termos ("suicídio entre
   jovens universitários" traz 1 artigo certo e 3 que só falam de universitários).
4. **Stopwords com acento nunca casam** em `app/preprocessamento.py` ("não", "você", "também",
   "até"): o token já saiu sem acento. Corrigir é inócuo (CV 0,849 → 0,848), mas muda o modelo.

## Classificador de intenções com encoder local e limiar 0,60 — estado em 12/10/2026

**O que é:** votação entre dois ramos treinados pela equipe sobre `data/intents.csv`:
(1) TF-IDF de palavras 1–3 e caracteres 2–5, sem remover stopwords + regressão logística (peso 0,7);
(2) vetores de um **encoder de sentenças local** (`paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0,
ONNX quantizado, ~118 MB em `models/encoder/`, CPU, sem rede em tempo de uso) + regressão logística
(peso 0,3). O encoder só produz vetores; a decisão é da regressão da equipe, sem LLM nem API
(R3). `LIMIAR_CONFIANCA = 0,60`. Sem o encoder o bot cai no ramo de n-gramas e avisa em `/saude`.

| Medida | só TF-IDF antigo | n-gramas + contexto | votação (atual) |
|---|---|---|---|
| Validação cruzada (treino) | 0,889 | 0,955 | 0,960 |
| Teste oficial (30 casos), acurácia | 1,000 | 0,967 | 0,933 |
| 40 paráfrases novas, intenção correta | — | 36 | 37 |
| ...corretas e aceitas no limiar 0,60 | — | 31 | 34 |
| 24 buscas de tema novo, corretas de ponta a ponta (0,60) | 17 | 17 | 18 |

**Ressalvas honestas:**
* O ganho do encoder é **modesto**: +1 a +4 casos conforme o conjunto. O encoder sozinho não
  vence o n-grama neste dataset (199 frases, vocabulário de domínio: "formata", "abnt", "busca");
  ele ganha em paráfrase e tema novo. Por isso a votação, e não a troca.
* O teste oficial **piorou** de 0,967 para 0,933 (ainda acima da meta 0,85): comandos curtos que
  dependem de vocabulário do domínio ("Que palavras-chave uso para achar artigos…").
* Limiar: a confiança é maior para frases parecidas com o treino e menor para tema novo.
  Curva de ponta a ponta nas 24 buscas (limiar 0,35/0,50/0,60/0,70/0,80): 20/19/18/16/14 corretas.
  O 0,80 abstinha de busca legítima; o 0,60 perde 2 em relação ao 0,35 e corta mais erro.
* O conjunto `tests/parafrases_intencao.csv` (40 frases) foi escrito antes de comparar os modelos,
  mas a escolha do peso 0,7 foi feita olhando-o: já não é um conjunto limpo para esse parâmetro.

**Segue aberto** (marcado `xfail` em `tests/test_integracao_api.py`, com o motivo):

1. Frases só com o tema ("relação entre pais e filhos") e comandos como "onde posso baixar o texto
   completo de graça?" chegam a 0,42–0,57, logo abaixo do limiar.
2. "Referência" em pedido de parecer ("confiar na Frontiers… como referência") vai para
   `formatar_referencia`: o ramo semântico ainda não separa isso com 40 exemplos por classe.
3. Cobertura parcial fraca na recuperação quando poucos artigos cobrem todos os termos.
4. Stopwords com acento nunca casam em `app/preprocessamento.py` ("não", "você", "também", "até");
   hoje só afeta a recuperação, pois as intenções agora mantêm as stopwords.

O que mais ajudaria agora é **mais dados rotulados** com variação de vocabulário (principalmente
`orientar_busca` x `buscar_referencias` e `avaliar_fonte`): o encoder reduz essa necessidade, não a elimina.

## Tema solto: palavra de assunto sem verbo é busca — 12/10/2026

**Sintoma:** "depressão" não trazia artigos, "artigos sobre depressão" trazia 5. O classificador
mandava "depressão" (0,47), "ansiedade" (0,71) e "cárie" (0,70) para `fora_de_escopo`: essas
palavras aparecem nas perguntas clínicas fora de escopo do `intents.csv` ("qual remédio tomar para
ansiedade"), então o modelo aprendeu a palavra, não a frase. A base tinha os artigos.

**Correção sem ampliar o CSV:** `Motor.so_tema` (recuperacao.py) + um passo em `fluxo.responder`.
A mensagem é "só um tema" quando, tiradas as palavras de enchimento e funcionais, restam de 1 a 4
palavras e todas existem em pelo menos 2 artigos (ou têm equivalente pt/en neles) e nenhuma é
vocabulário de outra ação (`TERMOS_DO_SISTEMA`: scielo, pubmed, capes, introdução...). Nesse caso
busca, a menos que o modelo esteja confiante (>= limiar) de que é avaliar fonte, formatar ou orientar.

**Efeito medido** (com a regra ligada e desligada, ~330 frases rotuladas): 0 mudanças no treino, no
teste oficial, nas paráfrases, nos temas ausentes e nas outras intenções. Mudou: 9 temas soltos
passaram a buscar (depressão, ansiedade, cárie, periodontia, clareamento, suicídio, pandemia,
autismo, estresse) e 2 buscas de integração que ficavam logo abaixo do limiar.

**O que a regra NÃO cobre (de propósito):**
* Tema que aparece em **um só artigo** ("burnout"): é menção incidental ("faz" e "psicólogo" também
  aparecem em um artigo). Esses seguem a decisão do classificador.
* Palavras do vocabulário do sistema: `TERMOS_DO_SISTEMA` é uma lista mantida à mão; ao adicionar
  uma base ou portal novo ao bot, acrescente o nome lá.
* Palavras com menos de 4 letras ("dor", "TDAH") não são reconhecidas como tema, a menos que estejam
  em 2+ artigos.


## Pergunta de esclarecimento na faixa de confiança baixa — 23/10/2026

**Antes:** abaixo de `LIMIAR_CONFIANCA` (0,60) o bot se abstinha. Perguntas legítimas que ficavam
em 0,38–0,57 ("bactérias resistentes a antibióticos", "onde posso baixar o texto completo de
graça?", "Que palavras-chave uso para achar artigos sobre cárie infantil?") recebiam "ainda não
tenho um registro verificado", sem chance de o usuário confirmar o que queria.

**Agora:** entre `LIMIAR_ESCLARECIMENTO` (0,35) e 0,60 o bot pergunta antes de agir
(`fluxo._esclarecer`). A resposta tem `tipo = "esclarecimento"`, não traz artigo nenhum e oferece
até duas ações, na ordem das probabilidades do classificador. A segunda só entra com probabilidade
>= `MIN_SEGUNDA_OPCAO` (0,25). As opções viram botões no front. A pergunta original fica em
`Contexto.esclarecimento` e vale **só para a mensagem seguinte**: "sim", "1"/"2", o rótulo do
botão ou "não". Qualquer outra mensagem descarta a pergunta e segue o fluxo normal. A ação
confirmada roda sobre a pergunta original e o traço registra "confirmado pelo usuário".

**Travas:**
* `fora_de_escopo` previsto **nunca** vira pergunta, nem com uma ação logo atrás. "escreve sobre
  depressão" sai 0,51 fora de escopo contra 0,48 busca; oferecer busca ali enfraqueceria a
  abstenção de pedidos de escrita (`test_esclarecimento.py`).
* `formatar_referencia` só é oferecida quando o contexto resolve o artigo citado. Sem lista, o
  "sim" levaria a outra abstenção, então o bot se abstém direto, como antes.
* Abaixo de 0,35 nada muda: abstenção.
* "sim"/"não"/"ok" **sem** pergunta em aberto (expirou, conversa limpa) recebem
  `SEM_PERGUNTA_PENDENTE`. Antes, "sim" virava busca por tema solto, porque a palavra aparece em
  vários artigos da base, e o bot devolvia 2 artigos.

**Efeito medido:** `tests/avaliar.py` com as mesmas métricas (acurácia, Precisão@5, abstenção
fora de escopo 1,000, 0 citações inventadas). O caso 9 continua errado na intenção, mas agora
pergunta "artigos sobre "cárie infantil" ou dicas de como buscar?" em vez de se abster.

**Limite conhecido:** a pergunta herda o erro do classificador. "quem ganhou o jogo ontem?" sai
`avaliar_fonte` 0,41 e o bot pergunta "você quer saber se essa fonte é confiável?". É inofensivo
(nada é recomendado, e o "não" encerra), mas soa estranho.
