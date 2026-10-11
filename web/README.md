# Interface do Artikel

A interface consome a API e **não** contém regra de negócio: nenhuma resposta é montada no
cliente, tudo vem de `POST /chat`.

## Como rodar (um servidor só)

```bash
# na raiz do repositório, com a venv ativa
uvicorn main:app --app-dir app --port 8000
```

Abra **<http://127.0.0.1:8000/>**. A própria API serve esta pasta em `/`, na mesma origem,
então não há CORS nem um segundo servidor para subir.

Se preferir a interface num servidor separado (ou usar o Vite no Marco 4), aponte a API:

```bash
python -m http.server 5173 --directory web
# abra http://127.0.0.1:5173/?api=http://127.0.0.1:8000
```

## Arquivos

| Arquivo | Papel |
|---|---|
| `index.html` | página única; carrega `estilo.css` e `app.js` |
| `app.js` | todo o cliente: estado, chamadas à API, desenho do chat |
| `estilo.css` | estilos (papel claro, cartões, painel do traço) |
| `_verificar_interface.js` | rodar o `app.js` num DOM mínimo em Node e checar o chat |
| `_verificar_contrato.js` | conferir a API real contra o que este cliente lê |

### Por que JavaScript puro e não React

A restrição do projeto é "ferramentas gratuitas ou locais". A primeira versão desta
interface usava React 18 e Babel via CDN, e **ficava em branco** no ambiente da equipe:
`unpkg.com`, `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `esm.sh` e o registro npm estavam
todos inacessíveis, e não havia cópia local de React. Sem os scripts, a `div#raiz` nunca era
preenchida e não aparecia nem o campo de digitação.

A versão atual não tem dependência externa: abre e funciona. Se a equipe quiser React no
Marco 4, o caminho é `npm create vite@latest` com a rede liberada — o contrato da API abaixo
continua valendo, muda só o cliente.

## Verificação

```bash
node web/_verificar_interface.js                       # DOM simulado: chat, traço, abstenção
node web/_verificar_contrato.js http://127.0.0.1:8000  # API real contra o que o front lê
```

O primeiro roda o `app.js` de verdade dentro de um DOM mínimo e simula o usuário digitando e
enviando. O segundo fala com a API no ar e confere campo a campo. Os dois juntos pegam tanto
erro de JavaScript quanto divergência entre o front e o backend — foi a falta deles que
deixou a versão em branco passar.

## Contrato da API

| Método | Rota | Uso |
|---|---|---|
| GET | `/saude` | estado da base, do modelo e dos limiares |
| POST | `/chat` | `{ "mensagem": "...", "sessao": "abc" }` |
| POST | `/sessao/{sessao}/limpar` | limpa o contexto (R1) |
| GET | `/artigos?area=&ano=&limite=` | consulta direta à base |
| GET | `/periodicos` | lista curada usada em `avaliar_fonte` |

A resposta de `/chat` tem sempre a mesma forma:

```json
{
  "resposta": "texto para exibir",
  "intencao": "buscar_referencias",
  "tipo": "recomendacao",
  "artigos": [
    {
      "posicao": 1,
      "id": "art_001",
      "titulo": "...",
      "autores": "SILVA, João",
      "ano": 2023,
      "periodico": "...",
      "doi": "10.xxxx/yyyy",
      "url": "https://...",
      "score": 0.412,
      "motivo": "alta similaridade; revisado por pares; indexado em DOAJ, SciELO",
      "referencia_abnt": "SILVA, João. ...",
      "resumo": "...",
      "licenca": "cc-by",
      "area": "odontologia"
    }
  ],
  "fontes": ["..."],
  "sugestoes": ["..."],
  "traco": {
    "intencao_prevista": "buscar_referencias",
    "confianca": 0.93,
    "limiar_confianca": 0.35,
    "acao": "recomendar",
    "regra": "similaridade+curadoria >= 0.1",
    "termos": ["..."],
    "n_candidatos": 5,
    "score_maximo": 0.412,
    "limiar_score": 0.1,
    "contexto_usado": false,
    "confianca_abaixo_do_limiar": false
  }
}
```

## O que a interface mostra

1. **Resposta** em texto, com os artigos em cartões numerados — o número é o que o usuário
   cita depois ("referência ABNT do segundo artigo"), e cada cartão tem o atalho para pedir.
2. **Motivo** de cada artigo, porque o documento exige justificar a recomendação.
3. **Referência ABNT** pronta para copiar (botão "copiar ABNT").
4. **Traço da decisão** em painel recolhível: intenção, confiança, ação, regra, candidatos e
   score máximo. É a evidência de R4 na demonstração.
5. **Aviso de abstenção** destacado quando `"tipo": "abstencao"` — abstenção é resposta
   correta e aparece como escolha, não como erro.
6. **Estado da API** no topo (base, periódicos, classificador, limiares) e aviso com o
   comando a rodar quando falta base ou modelo.
7. **Sessão** por aba (uuid), enviada em cada requisição para o contexto de "o segundo
   artigo" funcionar.
