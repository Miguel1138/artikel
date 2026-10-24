/* Confere que a API real devolve o contrato que a interface consome.
 *
 * A verificação com DOM simulado usa respostas fixas: ela pega erro de JavaScript, não
 * divergência entre o front e a API. Este script fala com a API de verdade e checa campo a
 * campo o que `web/app.js` lê.
 *
 * Uso: node web/_verificar_contrato.js [http://127.0.0.1:8000]
 */
const BASE = process.argv[2] || 'http://127.0.0.1:8000';

const PERGUNTAS = [
  'preciso de artigos sobre clareamento dental',
  'a revista X é confiável?',
  'escreve minha introdução',
];

let falhas = 0;
const conferir = (rotulo, ok, detalhe = '') => {
  if (!ok) falhas += 1;
  console.log((ok ? '  ok   ' : '  FALHA') + ' ' + rotulo + (detalhe ? ' — ' + detalhe : ''));
};

async function pegar(caminho, opcoes) {
  const r = await fetch(BASE + caminho, opcoes);
  const texto = await r.text();
  if (!r.ok) throw new Error(caminho + ' -> ' + r.status + ': ' + texto.slice(0, 200));
  return JSON.parse(texto);
}

async function main() {
  console.log('Contrato da API real em ' + BASE);

  const saude = await pegar('/saude');
  for (const campo of ['status', 'artigos_na_base', 'periodicos_na_base', 'entradas_faq',
                       'modelo_carregado', 'limiar_confianca', 'limiar_score', 'areas']) {
    conferir('GET /saude traz "' + campo + '"', campo in saude);
  }
  conferir('a base tem artigos', saude.artigos_na_base > 0, String(saude.artigos_na_base));
  conferir('o classificador está carregado', saude.modelo_carregado === true);

  const sessao = 'contrato-' + Date.now();
  for (const pergunta of PERGUNTAS) {
    const r = await pegar('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensagem: pergunta, sessao }),
    });
    console.log('\n  P: ' + pergunta);
    conferir('  resposta em texto', typeof r.resposta === 'string' && r.resposta.length > 0);
    conferir('  intenção válida', ['buscar_referencias', 'avaliar_fonte', 'formatar_referencia',
                                   'orientar_busca', 'fora_de_escopo'].includes(r.intencao));
    conferir('  tipo conhecido pelo front', ['recomendacao', 'parecer_fonte', 'referencia_abnt',
                                             'orientacao_busca', 'abstencao', 'esclarecimento'].includes(r.tipo));
    conferir('  lista de artigos', Array.isArray(r.artigos));
    conferir('  sugestões', Array.isArray(r.sugestoes) && r.sugestoes.length > 0);

    const t = r.traco;
    conferir('  traço da decisão completo',
      t && ['intencao_prevista', 'confianca', 'limiar_confianca', 'acao', 'regra',
            'n_candidatos', 'contexto_usado'].every((k) => k in t));

    for (const a of r.artigos) {
      const faltando = ['posicao', 'id', 'titulo', 'autores', 'score', 'motivo', 'referencia_abnt']
        .filter((k) => a[k] === undefined || a[k] === null || a[k] === '');
      conferir('  artigo ' + a.posicao + ' com os campos que o cartão usa', faltando.length === 0,
        faltando.join(', '));
    }
  }

  // Contexto (R1): o front manda o mesmo id de sessão e espera resolver "o segundo artigo".
  const busca = await pegar('/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mensagem: 'preciso de artigos sobre clareamento dental', sessao }),
  });
  if (busca.artigos.length >= 2) {
    const ref = await pegar('/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensagem: 'referência ABNT do segundo artigo', sessao }),
    });
    console.log('\n  P: referência ABNT do segundo artigo');
    conferir('  resposta é referência ABNT', ref.tipo === 'referencia_abnt');
    conferir('  usou o contexto da sessão', ref.traco.contexto_usado === true);
    conferir('  devolveu exatamente o 2º artigo', ref.artigos[0] && ref.artigos[0].id === busca.artigos[1].id);
    conferir('  a referência tem o autor do 2º artigo',
      ref.resposta.includes((busca.artigos[1].autores || '').split(';')[0].split(',')[0].slice(0, 8)));
  } else {
    console.log('\n  (busca trouxe menos de 2 artigos; teste de contexto não se aplica)');
  }

  await pegar('/sessao/' + sessao + '/limpar', { method: 'POST' });

  console.log(falhas ? `\n${falhas} verificação(ões) falharam` : '\nContrato conferido contra a API real');
  process.exit(falhas ? 1 : 0);
}

main().catch((causa) => {
  console.error('erro na verificação:', causa.message);
  process.exit(1);
});
