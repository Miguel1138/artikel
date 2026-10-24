/* Verificação da interface sem navegador.
 *
 * Roda o `app.js` real dentro de um DOM mínimo em Node, com um `fetch` que responde o
 * contrato da API. Pega o que importa: erro de sintaxe, `ReferenceError`, elemento que não
 * existe, resposta que não desenha e traço da decisão que não aparece.
 *
 * É o teste que faltava na primeira versão da interface — ela dependia de CDN e ficava em
 * branco sem ninguém perceber.
 *
 * Uso: node web/_verificar_interface.js
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const DIR = __dirname;
const RAIZ = path.join(DIR, '..');
let falhas = 0;
const conferir = (rotulo, ok, detalhe = '') => {
  if (!ok) falhas += 1;
  console.log((ok ? '  ok   ' : '  FALHA') + ' ' + rotulo + (detalhe ? ' — ' + detalhe : ''));
};

/* ------------------------------------------------------------------ DOM mínimo */
class No {
  constructor(tag) {
    this.tagName = (tag || '').toUpperCase();
    this.children = [];
    this.atributos = {};
    this._texto = '';
    this.eventos = {};
    this.value = '';
  }
  get className() { return this.atributos.class || ''; }
  set className(v) { this.atributos.class = v; }
  get id() { return this.atributos.id || ''; }
  set id(v) { this.atributos.id = v; }
  set textContent(v) { this._texto = String(v); this.children = []; }
  get textContent() { return this._texto + this.children.map((c) => c.textContent).join(''); }
  set innerHTML(v) { this._texto = String(v); }
  get innerHTML() { return this.textContent; }
  appendChild(no) { this.children.push(no); return no; }
  append(...nos) { nos.forEach((n) => this.appendChild(n)); }
  setAttribute(k, v) { this.atributos[k] = String(v); }
  getAttribute(k) { return this.atributos[k]; }
  addEventListener(tipo, fn) { (this.eventos[tipo] = this.eventos[tipo] || []).push(fn); }
  focus() {}
  scrollIntoView() {}
  disparar(tipo, extra = {}) {
    (this.eventos[tipo] || []).forEach((fn) => fn({ preventDefault() {}, target: this, ...extra }));
  }
  // busca simples por tag/atributo, suficiente para as checagens
  procurar(predicado, achados = []) {
    if (predicado(this)) achados.push(this);
    this.children.forEach((c) => c.procurar(predicado, achados));
    return achados;
  }
}

function montarAmbiente(respostas) {
  const raiz = new No('div');
  raiz.id = 'raiz';
  const documento = {
    createElement: (tag) => new No(tag),
    createTextNode: (texto) => {
      const no = new No('#text');
      no.textContent = texto;
      return no;
    },
    getElementById: (id) => (id === 'raiz' ? raiz : raiz.procurar((n) => n.id === id)[0] || null),
  };

  const chamadas = [];
  const fetch = async (url, opcoes = {}) => {
    chamadas.push({ url, opcoes });
    const chave = Object.keys(respostas).find((k) => url.endsWith(k));
    if (!chave) return { ok: false, status: 404, statusText: 'Not Found', text: async () => '{}' };
    const corpo = respostas[chave];
    return {
      ok: true, status: 200, statusText: 'OK',
      text: async () => JSON.stringify(typeof corpo === 'function' ? corpo() : corpo),
    };
  };

  const janela = { ARTIKEL_API: 'http://127.0.0.1:8000' };
  const sandbox = {
    document: documento,
    window: janela,
    fetch,
    crypto: { randomUUID: () => 'sessao-de-teste' },
    navigator: { clipboard: { writeText: async () => {} } },
    // O app lê `location.search` (?api=...) e `location.origin`: no navegador existem,
    // então o DOM de teste precisa oferecê-los.
    location: { search: '', origin: 'http://127.0.0.1:8000' },
    URLSearchParams,
    setTimeout,
    console,
  };
  sandbox.globalThis = sandbox;
  return { raiz, documento, chamadas, sandbox };
}

/* ------------------------------------------------------------------ respostas */
const SAUDE = {
  status: 'ok', artigos_na_base: 246, periodicos_na_base: 107, entradas_faq: 12,
  modelo_carregado: true, limiar_confianca: 0.35, limiar_score: 0.1,
  recorte_anos: [2016, 2026], areas: ['biologia', 'computacao', 'medicina', 'odontologia', 'psicologia'],
};

const CHAT = {
  resposta: 'Separei 3 artigos da base curada em odontologia.',
  intencao: 'buscar_referencias',
  tipo: 'recomendacao',
  artigos: [{
    posicao: 1, id: 'art_001', titulo: 'In-office dental bleaching in adolescents',
    autores: 'CARNEIRO, Taynara de Souza et al.', ano: 2023, periodico: 'Brazilian Oral Research',
    doi: '10.1590/example', url: 'https://doi.org/10.1590/example', score: 0.253,
    motivo: 'alta similaridade; revisado por pares', referencia_abnt: 'CARNEIRO, Taynara de Souza et al. In-office dental bleaching. 2023.',
    resumo: 'Ensaio clínico randomizado.', licenca: 'cc-by', area: 'odontologia',
  }],
  fontes: ['odontologia'],
  sugestoes: ['Me dá a referência ABNT do primeiro artigo'],
  traco: {
    intencao_prevista: 'buscar_referencias', confianca: 0.51, limiar_confianca: 0.35,
    acao: 'recomendar', regra: 'similaridade+curadoria >= 0.1', termos: ['clareamento'],
    n_candidatos: 5, score_maximo: 0.253, limiar_score: 0.1, contexto_usado: false,
    confianca_abaixo_do_limiar: false,
  },
};

async function main() {
  console.log('Verificação da interface (DOM mínimo, sem navegador)');
  console.log('  app.js:', fs.existsSync(path.join(DIR, 'app.js')) ? 'encontrado' : 'AUSENTE');
  console.log('  index.html:', fs.existsSync(path.join(DIR, 'index.html')) ? 'encontrado' : 'AUSENTE');
  console.log('  estilo.css:', fs.existsSync(path.join(DIR, 'estilo.css')) ? 'encontrado' : 'AUSENTE');

  // 1) Sintaxe
  const codigo = fs.readFileSync(path.join(DIR, 'app.js'), 'utf-8');
  try {
    new vm.Script(codigo, { filename: 'app.js' });
    conferir('app.js tem sintaxe válida', true);
  } catch (causa) {
    conferir('app.js tem sintaxe válida', false, causa.message);
    process.exit(1);
  }

  // 2) index.html aponta para o arquivo certo e nada de CDN
  const html = fs.readFileSync(path.join(DIR, 'index.html'), 'utf-8');
  conferir('index.html carrega app.js', /<script src="app\.js">/.test(html));
  conferir('index.html tem o elemento #raiz', /id="raiz"/.test(html));
  conferir('index.html não depende de CDN', !/https?:\/\/[^"]*\.js/.test(html));

  // 3) Executa o app com o DOM mínimo
  const ambiente = montarAmbiente({ '/saude': SAUDE, '/chat': CHAT });
  const contexto = vm.createContext(ambiente.sandbox);
  try {
    await vm.runInContext(codigo, contexto, { filename: 'app.js' });
    await new Promise((r) => setTimeout(r, 30));   // deixa o /saude resolver
  } catch (causa) {
    conferir('app.js roda sem exceção', false, causa.message);
    process.exit(1);
  }
  conferir('app.js roda sem exceção', true);

  const todos = () => ambiente.raiz.procurar(() => true);
  const porTag = (tag) => todos().filter((n) => n.tagName === tag.toUpperCase());
  const temTexto = (trecho) => todos().some((n) => n.textContent.includes(trecho));

  conferir('pediu /saude na carga', ambiente.chamadas.some((c) => c.url.endsWith('/saude')));
  conferir('mostra o tamanho da base', temTexto('246'));
  conferir('mostra o classificador', temTexto('classificador carregado'));
  conferir('mostra os limiares', temTexto('0.35'));
  conferir('tem campo de texto', porTag('input').length >= 1);
  conferir('tem botão enviar', temTexto('enviar'));
  conferir('tem botão limpar conversa', temTexto('limpar conversa'));
  conferir('mostra as sugestões', temTexto('aprendizado de máquina na saúde'));

  // 4) Fluxo de conversa: digitar, enviar, desenhar a resposta
  const campo = porTag('input')[0];
  campo.value = 'preciso de artigos sobre clareamento dental';
  const formulario = porTag('form')[0];
  if (!formulario) {
    conferir('formulário de envio existe', false);
  } else {
    formulario.disparar('submit');
    await new Promise((r) => setTimeout(r, 40));
    const pedido = ambiente.chamadas.find((c) => c.url.endsWith('/chat'));
    conferir('enviou POST /chat', Boolean(pedido) && pedido.opcoes.method === 'POST');
    if (pedido) {
      const corpo = JSON.parse(pedido.opcoes.body);
      conferir('enviou a pergunta e a sessão', corpo.mensagem.includes('clareamento') && corpo.sessao === 'sessao-de-teste');
    }
    conferir('desenhou a resposta', temTexto('Separei 3 artigos'));
    conferir('desenhou o cartão do artigo', temTexto('In-office dental bleaching'));
    conferir('mostra o motivo da indicação', temTexto('Por que este:'));
    conferir('mostra a referência ABNT', temTexto('CARNEIRO, Taynara de Souza et al. In-office'));
    conferir('mostra o score', temTexto('0.253'));
    conferir('mostra o traço da decisão', temTexto('traço da decisão'));
    conferir('mostra a regra aplicada', temTexto('similaridade+curadoria'));
    conferir('mostra a etiqueta da intenção', temTexto('Recomendação da base curada'));
    // Depois do envio a tela é redesenhada: o campo é um nó novo, então a checagem
    // olha o campo atual, não a referência antiga.
    const campoDepois = ambiente.raiz.procurar((n) => n.tagName === 'INPUT')[0];
    conferir('limpa o campo depois de enviar', campoDepois && campoDepois.value === '');
    conferir('tem botão de copiar ABNT', temTexto('copiar ABNT'));
    conferir('tem atalho para pedir a referência', temTexto('referência do artigo 1'));
  }

  // 5) Abstenção precisa ser destacada, não parecer erro
  const abstencoes = montarAmbiente({
    '/saude': SAUDE,
    '/chat': { ...CHAT, tipo: 'abstencao', artigos: [], resposta: 'Ainda não tenho um registro verificado.',
               traco: { ...CHAT.traco, acao: 'abstencao', regra: 'intenção fora de escopo' } },
  });
  await vm.runInContext(codigo, vm.createContext(abstencoes.sandbox), { filename: 'app.js' });
  await new Promise((r) => setTimeout(r, 30));
  const campoAbst = abstencoes.raiz.procurar((n) => n.tagName === 'INPUT')[0];
  campoAbst.value = 'escreve minha introdução';   // o campo é lido no submit
  const formAbst = abstencoes.raiz.procurar((n) => n.tagName === 'FORM')[0];
  formAbst.disparar('submit');
  await new Promise((r) => setTimeout(r, 40));
  const classeAbstencao = abstencoes.raiz.procurar((n) => n.className === 'abstencao');
  conferir('abstenção usa o bloco de aviso', classeAbstencao.length === 1);
  conferir('abstenção aparece na tela', abstencoes.raiz.textContent.includes('Ainda não tenho um registro'));
  conferir('abstenção não vira recomendação', !abstencoes.raiz.textContent.includes('Recomendação da base curada'));

  // 6) Esclarecimento: as opções viram botões que mandam o próprio rótulo como mensagem
  const esclarecimento = montarAmbiente({
    '/saude': SAUDE,
    '/chat': { ...CHAT, tipo: 'esclarecimento', artigos: [], fontes: [],
               resposta: 'Só para confirmar: você quer que eu procure artigos sobre "cárie"?',
               sugestoes: ['Procurar artigos sobre isso', 'Não, é outra coisa'],
               traco: { ...CHAT.traco, acao: 'esclarecimento', confianca_abaixo_do_limiar: true,
                        regra: 'confiança 0.45 entre 0.35 e 0.6: pergunta antes de agir' } },
  });
  await vm.runInContext(codigo, vm.createContext(esclarecimento.sandbox), { filename: 'app.js' });
  await new Promise((r) => setTimeout(r, 30));
  const campoEsc = esclarecimento.raiz.procurar((n) => n.tagName === 'INPUT')[0];
  campoEsc.value = 'cárie';
  esclarecimento.raiz.procurar((n) => n.tagName === 'FORM')[0].disparar('submit');
  await new Promise((r) => setTimeout(r, 40));
  const texto = esclarecimento.raiz.textContent;
  conferir('esclarecimento tem etiqueta própria', texto.includes('Pergunta de esclarecimento'));
  conferir('esclarecimento explica o traço', texto.includes('pergunta antes de agir'));
  const opcao = esclarecimento.raiz.procurar((n) => n.tagName === 'BUTTON' && n.textContent === 'Procurar artigos sobre isso')[0];
  conferir('esclarecimento mostra as opções como botões', Boolean(opcao));
  if (opcao) {
    opcao.disparar('click');
    await new Promise((r) => setTimeout(r, 40));
    const enviados = esclarecimento.chamadas.filter((c) => c.url.endsWith('/chat'))
      .map((c) => JSON.parse(c.opcoes.body).mensagem);
    conferir('botão envia o rótulo da opção', enviados[enviados.length - 1] === 'Procurar artigos sobre isso');
    // O mock devolve o mesmo esclarecimento de novo: só o último turno pode ter botões ativos.
    const botoes = esclarecimento.raiz.procurar((n) => n.tagName === 'BUTTON' && n.textContent === 'Procurar artigos sobre isso');
    conferir('opções antigas somem depois da resposta', botoes.length === 1);
  }

  // 7) API fora do ar: precisa avisar, não ficar em branco
  const semApi = montarAmbiente({});
  semApi.sandbox.fetch = async () => { throw new Error('conexão recusada'); };
  await vm.runInContext(codigo, vm.createContext(semApi.sandbox), { filename: 'app.js' });
  await new Promise((r) => setTimeout(r, 30));
  conferir('avisa quando a API está fora do ar', semApi.raiz.textContent.includes('não consegui falar com a API'));
  conferir('mostra o comando para subir a API', semApi.raiz.textContent.includes('uvicorn main:app'));

  console.log(falhas ? `\n${falhas} verificação(ões) falharam` : '\nInterface verificada: chat, respostas, traço e abstenção');
  process.exit(falhas ? 1 : 0);
}

main().catch((causa) => {
  console.error('erro na verificação:', causa);
  process.exit(1);
});
