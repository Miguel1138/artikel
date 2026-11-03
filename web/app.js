/* Interface do Artikel — JavaScript puro, sem dependência externa.
 *
 * Por que não React: a restrição do projeto é "ferramentas gratuitas ou locais". Neste
 * ambiente não há acesso a CDN (unpkg, jsdelivr, cdnjs, esm.sh) nem ao registro npm, então
 * uma interface que dependa de React via CDN fica em branco. Este arquivo é autossuficiente.
 *
 * Regra: nenhuma decisão de negócio aqui. O cliente envia a mensagem e o id da sessão e
 * desenha o que a API devolveu — inclusive o traço da decisão, que é a evidência de R4.
 */
// Mesma origem por padrão: a API serve esta pasta em `/`. Para rodar a interface num
// servidor separado, defina `window.ARTIKEL_API` antes de carregar este arquivo (ou passe
// ?api=http://127.0.0.1:8000 na URL).
const parametroApi = new URLSearchParams(location.search).get('api');
const API = window.ARTIKEL_API || parametroApi || location.origin;

const EXEMPLOS = [
  'Preciso de artigos sobre aprendizado de máquina na saúde',
  'A revista X é confiável?',
  'Como procuro artigos no SciELO?',
  'Escreve minha introdução',
];

const ROTULO_TIPO = {
  recomendacao: 'Recomendação da base curada',
  parecer_fonte: 'Parecer sobre a fonte',
  referencia_abnt: 'Referência NBR 6023',
  orientacao_busca: 'Orientação de busca',
  abstencao: 'Abstenção',
  esclarecimento: 'Pergunta de esclarecimento',
};

const estado = {
  sessao: (crypto.randomUUID && crypto.randomUUID()) || 'sessao-' + Math.random().toString(36).slice(2),
  saude: null,
  erroSaude: null,
  turnos: [],
  ocupado: false,
  erro: null,
  rascunho: '',
};

const el = (tag, props = {}, filhos = []) => {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(props)) {
    if (chave === 'classe') no.className = valor;
    else if (chave === 'texto') no.textContent = valor;
    else if (chave === 'html') no.innerHTML = valor;
    else if (chave.startsWith('on')) no.addEventListener(chave.slice(2), valor);
    else if (valor !== null && valor !== undefined) no.setAttribute(chave, valor);
  }
  for (const f of [].concat(filhos)) {
    if (f === null || f === undefined || f === false) continue;
    no.appendChild(typeof f === 'string' ? document.createTextNode(f) : f);
  }
  return no;
};

/* ------------------------------------------------------------------ API */
async function chamarApi(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(API + caminho, opcoes);
  } catch (causa) {
    throw new Error(
      'não consegui falar com a API em ' + API +
      '. Suba o servidor com: uvicorn main:app --app-dir app --port 8000'
    );
  }
  const texto = await resposta.text();
  let dados = null;
  try { dados = texto ? JSON.parse(texto) : null; } catch (causa) { dados = null; }
  if (!resposta.ok) {
    const detalhe = (dados && dados.detail) || texto || resposta.statusText;
    throw new Error(resposta.status + ' — ' + detalhe);
  }
  return dados;
}

/* ------------------------------------------------------------------ pedaços */
function selos() {
  const { saude } = estado;
  if (!saude) return [el('span', { classe: 'selo', texto: 'verificando API…' })];
  const pronto = saude.status === 'ok' && saude.modelo_carregado;
  return [
    el('span', {
      classe: pronto ? 'selo ok' : 'selo alerta',
      texto: saude.artigos_na_base + ' artigos · ' + saude.periodicos_na_base + ' periódicos',
    }),
    el('span', {
      classe: saude.modelo_carregado ? 'selo ok' : 'selo erro',
      texto: saude.modelo_carregado ? 'classificador carregado' : 'classificador ausente',
    }),
    el('span', {
      classe: 'selo',
      texto: 'limiares ' + saude.limiar_confianca + ' / ' + saude.limiar_score,
    }),
  ];
}

function cartaoArtigo(artigo) {
  const copiar = el('button', {
    texto: 'copiar ABNT',
    onclick: async (evento) => {
      try {
        await navigator.clipboard.writeText(artigo.referencia_abnt);
        evento.target.textContent = 'copiado';
        setTimeout(() => { evento.target.textContent = 'copiar ABNT'; }, 1800);
      } catch (causa) {
        // clipboard bloqueado (ex.: página aberta por file://): o texto segue visível
        evento.target.textContent = 'selecione o texto';
      }
    },
  });

  const acoes = el('div', { classe: 'acoes' }, [
    artigo.doi ? el('a', {
      href: 'https://doi.org/' + artigo.doi, target: '_blank', rel: 'noreferrer',
      texto: 'DOI: ' + artigo.doi,
    }) : null,
    artigo.url ? el('a', { href: artigo.url, target: '_blank', rel: 'noreferrer', texto: 'abrir no periódico' }) : null,
    el('span', { classe: 'espaco' }),
    copiar,
    el('button', {
      texto: 'referência do artigo ' + artigo.posicao,
      onclick: () => enviar('Me dá a referência ABNT do artigo ' + artigo.posicao),
    }),
  ]);

  return el('article', { classe: 'cartao-artigo' }, [
    el('h3', {}, [
      el('span', { classe: 'numero', texto: String(artigo.posicao) }),
      artigo.titulo,
    ]),
    el('div', {
      classe: 'meta',
      texto: [
        artigo.autores,
        artigo.ano || 's.d.',
        artigo.periodico,
        artigo.licenca ? String(artigo.licenca).toUpperCase() : null,
      ].filter(Boolean).join(' · '),
    }),
    el('div', { classe: 'motivo', texto: 'Por que este: ' + artigo.motivo + ' (score ' + artigo.score + ')' }),
    artigo.referencia_abnt ? el('div', { classe: 'referencia', texto: artigo.referencia_abnt }) : null,
    acoes,
  ]);
}

function painelTraco(traco) {
  if (!traco) return null;
  const linhas = [
    ['intenção prevista', traco.intencao_prevista],
    ['confiança', traco.confianca + ' (limiar ' + traco.limiar_confianca + ')'],
    ['ação', traco.acao],
    ['regra aplicada', traco.regra],
    ['candidatos', String(traco.n_candidatos)],
    ['score máximo', (traco.score_maximo === null || traco.score_maximo === undefined)
      ? '—' : traco.score_maximo + (traco.limiar_score ? ' (limiar ' + traco.limiar_score + ')' : '')],
    ['contexto usado', traco.contexto_usado ? 'sim' : 'não'],
  ];
  if (traco.confianca_abaixo_do_limiar) {
    linhas.push(['observação', traco.acao === 'esclarecimento'
      ? 'confiança abaixo do limiar: pergunta antes de agir'
      : 'confiança abaixo do limiar: resposta abstida']);
  }
  const tabela = el('table', {}, linhas.map(([rotulo, valor]) => el('tr', {}, [
    el('td', { texto: rotulo }),
    el('td', {}, [el('code', { texto: String(valor) })]),
  ])));

  const detalhes = el('details', { classe: 'traco' }, [
    el('summary', { texto: 'traço da decisão (R4): ' + traco.acao + ' · ' + traco.regra }),
    tabela,
  ]);
  return detalhes;
}

function turno(t, ultimo) {
  // As opções do esclarecimento só valem para a mensagem seguinte: botões apenas no último turno.
  const opcoes = t.tipo === 'esclarecimento' && ultimo && (t.sugestoes || []).length
    ? el('div', { classe: 'sugestoes' }, t.sugestoes.map((opcao) => el('button', {
        texto: opcao,
        disabled: estado.ocupado ? 'disabled' : null,
        onclick: () => enviar(opcao),
      })))
    : null;
  const corpo = el('div', { classe: 'corpo' }, [
    el('span', { classe: 'etiqueta-intencao', texto: ROTULO_TIPO[t.tipo] || t.tipo }),
    t.tipo === 'abstencao'
      ? el('div', { classe: 'abstencao', texto: t.resposta })
      : el('div', { classe: 'texto-resposta', texto: t.resposta }),
    opcoes,
    ...(t.artigos || []).map(cartaoArtigo),
    (t.fontes && t.fontes.length)
      ? el('div', { classe: 'motivo', texto: 'Fontes citadas: ' + t.fontes.join(' · ') })
      : null,
    painelTraco(t.traco),
  ]);
  return el('section', { classe: 'turno' }, [
    el('div', { classe: 'pergunta', texto: t.pergunta }),
    el('div', { classe: 'resposta' }, [corpo]),
  ]);
}

function avisos() {
  const lista = [];
  if (estado.erroSaude) {
    lista.push(el('div', { classe: 'aviso-base' }, [
      'Não consegui falar com a API em ',
      el('code', { texto: API }),
      ' (' + estado.erroSaude + ').',
    ]));
  }
  if (estado.saude && (estado.saude.status !== 'ok' || !estado.saude.modelo_carregado)) {
    lista.push(el('div', {
      classe: 'aviso-base',
      texto: estado.saude.status !== 'ok'
        ? 'A base curada não está disponível: rode python scripts/coleta/pipeline.py.'
        : 'O classificador não está treinado: rode python scripts/treinar_classificador.py.',
    }));
  }
  if (estado.erro) {
    lista.push(el('p', { classe: 'erro-api', texto: 'Falha na requisição: ' + estado.erro }));
  }
  return lista;
}

/* ------------------------------------------------------------------ render */
function desenhar() {
  const raiz = document.getElementById('raiz');
  raiz.textContent = '';

  const topo = el('header', { classe: 'topo' }, [
    el('h1', {}, ['Artikel ', el('span', { texto: '·' }), ' assistente de referências confiáveis']),
    el('span', { classe: 'sub', texto: 'base curada · sem LLM' }),
    el('span', { classe: 'espaco' }),
    ...selos(),
    el('button', { classe: 'limpar', texto: 'limpar conversa', onclick: limpar }),
  ]);

  const principal = el('main', {}, [
    ...avisos(),
    estado.turnos.length === 0
      ? el('div', {}, [
          el('p', {
            texto: 'O Artikel recomenda apenas artigos da base curada pela equipe, com DOI ou '
              + 'link verificado. Quando não há registro confiável, ele se abstém em vez de inventar.',
          }),
          el('div', { classe: 'sugestoes' }, EXEMPLOS.map((exemplo) => el('button', {
            texto: exemplo,
            disabled: estado.ocupado ? 'disabled' : null,
            onclick: () => enviar(exemplo),
          }))),
        ])
      : null,
    ...estado.turnos.map((t, i) => turno(t, i === estado.turnos.length - 1)),
    estado.ocupado ? el('p', { classe: 'carregando', texto: 'consultando a base curada…' }) : null,
    el('div', { id: 'fim' }),
  ]);

  const entrada = el('input', {
    type: 'text',
    placeholder: 'Pergunte sobre artigos, fontes, ABNT ou busca acadêmica',
    autofocus: 'autofocus',
    onkeydown: (evento) => { if (evento.key === 'Enter') enviar(evento.target.value); },
  });
  entrada.value = estado.rascunho;   // preserva o que estava digitado ao redesenhar
  entrada.addEventListener('input', (evento) => { estado.rascunho = evento.target.value; });
  if (estado.ocupado) entrada.setAttribute('disabled', 'disabled');

  const rodape = el('footer', { classe: 'pergunta-fixa' }, [
    el('form', { onsubmit: (evento) => { evento.preventDefault(); enviar(entrada.value); } }, [
      entrada,
      el('button', {
        type: 'submit',
        texto: 'enviar',
        disabled: estado.ocupado ? 'disabled' : null,
      }),
    ]),
    el('div', {
      classe: 'dica',
      texto: 'Sessão ' + estado.sessao.slice(0, 8) + ' — o contexto ("o segundo artigo") vale só nesta aba.',
    }),
  ]);

  raiz.append(topo, principal, rodape);
  const fim = document.getElementById('fim');
  if (fim && estado.turnos.length) fim.scrollIntoView({ behavior: 'smooth', block: 'end' });
  if (!estado.ocupado) entrada.focus();
}

/* ------------------------------------------------------------------ ações */
async function enviar(texto) {
  const mensagem = (texto || '').trim();
  if (!mensagem || estado.ocupado) return;
  estado.ocupado = true;
  estado.erro = null;
  estado.rascunho = '';      // o campo é redesenhado vazio
  desenhar();
  try {
    const resposta = await chamarApi('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensagem, sessao: estado.sessao }),
    });
    estado.turnos.push({ pergunta: mensagem, ...resposta });
  } catch (causa) {
    estado.erro = causa.message;
  } finally {
    estado.ocupado = false;
    desenhar();
  }
}

async function limpar() {
  try {
    await chamarApi('/sessao/' + estado.sessao + '/limpar', { method: 'POST' });
  } catch (causa) { /* limpar é melhor esforço */ }
  estado.turnos = [];
  estado.erro = null;
  desenhar();
}

async function iniciar() {
  desenhar();
  try {
    estado.saude = await chamarApi('/saude');
    estado.erroSaude = null;
  } catch (causa) {
    estado.erroSaude = causa.message;
  }
  desenhar();
}

iniciar();
