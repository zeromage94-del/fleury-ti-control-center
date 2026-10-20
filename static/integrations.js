'use strict';
MENUS.push(['integrations','link','Integrações e Zebra']);
S.integrationCatalog=null;
S.adminScripts=[];
const previousIntegrationRender=render;
function integrationsPage(){
 const c=S.integrationCatalog;
 const opts=items=>items.map(x=>`<option value="${esc(x.id)}">${esc(x.name)} · ${esc(x.address||x.id)}</option>`).join('');
 return pageHead('Integrações e Zebra','Conectores configurados pela equipe de TI. Impressão depende da impressora e do modelo cadastrados no servidor.')+
 panel('Zebra • zpl-rest','printer',`<div class="panel-body"><button class="btn" data-act="zebra-load">Carregar impressoras e modelos</button>
 ${c?`<p><label>Impressora <select class="select" id="zebra-printer">${opts(c.printers)}</select></label></p><p><label>Modelo <select class="select" id="zebra-label">${opts(c.labels)}</select></label></p>
 <p><label>Variáveis do modelo (JSON; use dados fictícios no teste)<textarea class="field" id="zebra-data" rows="4">{}</textarea></label></p>
 <button class="btn primary" data-act="zebra-print" ${!c.printers.length||!c.labels.length?'disabled':''}>Imprimir etiqueta</button>`:'<p>Configure FLEURY_ZPL_REST_URL no ambiente da estação e carregue o catálogo.</p>'}
 <p class="hint">Sem preview externo. O pedido vai ao servidor configurado e consome uma etiqueta física. Confira a fila antes de repetir após erro ou timeout.</p></div>`)+
 `<div class="section-gap">${panel('WinUtil oficial • estação do técnico','download',`<div class="panel-body"><p>Abra a cópia local revisada do WinUtil em janela própria. Requer sessão administrativa autorizada. A seleção global de máquina não se aplica ao WinUtil original.</p><button class="btn primary" data-act="winutil-launch">Abrir WinUtil local</button> <button class="btn" data-act="winutil-repo">Repositório oficial</button><p class="hint">Configure FLEURY_WINUTIL_PATH e FLEURY_WINUTIL_SHA256. As operações internas do WinUtil têm registro próprio; o Fleury audita sua abertura.</p></div>`)}</div>`+
 `<div class="section-gap">${panel('Zammad','ticket',`<div class="panel-body"><p>Importa até 300 chamados por sincronização, usando as permissões do token. Alterações da fila local não são enviadas ao Zammad.</p><button class="btn" data-act="zammad-sync">Sincronizar Zammad</button></div>`)}</div>`+
 `<div class="section-gap">${panel('Scripts administrativos • consultas','code',`<div class="panel-body"><button class="btn" data-act="scripts-load">Carregar biblioteca</button><p>Usam o equipamento selecionado no topo e as permissões WinRM existentes.</p><div class="action-grid">${S.adminScripts.map(x=>`<button class="btn" data-act="admin-script" data-key="${esc(x.key)}">${esc(x.name)}</button>`).join('')}</div>${S.adminScriptResult?prettyData(S.adminScriptResult):''}</div>`)}</div>`;
}
render=function(){
 if(S.page!=='integrations')return previousIntegrationRender();
 sidebar();main.innerHTML=integrationsPage();syncGlobalTarget();
};
const previousIntegrationAct=act;
act=async function(action,data={}){
 if(action==='zebra-load')return busyCall(async()=>{const d=await request('zebra/catalog');S.integrationCatalog=d.result;render();},'Catálogo Zebra carregado.');
 if(action==='scripts-load')return busyCall(async()=>{S.adminScripts=await request('scripts/catalog');render();},'');
 if(action==='admin-script'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{const d=await request(`scripts/run?target=${encodeURIComponent(m.target)}&key=${encodeURIComponent(data.key)}`);S.adminScriptResult={Maquina:m.target,Consulta:data.key,Resultado:d.result};render();},'Consulta concluída.');
 }
 if(action==='zebra-print'){
  const printer=document.querySelector('#zebra-printer').value,label=document.querySelector('#zebra-label').value;
  let variables;try{variables=JSON.parse(document.querySelector('#zebra-data').value);}catch{toast('Informe JSON válido.',true);return;}
  const p=S.integrationCatalog.printers.find(x=>x.id===printer),l=S.integrationCatalog.labels.find(x=>x.id===label);
  if(!p||!l)return toast('Selecione impressora e modelo.',true);
  return showModal({title:'Imprimir etiqueta Zebra?',desc:`Destino: ${p.name} (${p.address}). Modelo: ${l.name}. Será enviado ao servidor ZPL configurado. Confira as variáveis e a impressora antes de confirmar.`,actionText:'Confirmar impressão',onConfirm:async()=>{const d=await request('zebra/print',{printer,label,data:variables,confirm:true});toast(d.result.message);}});
 }
 if(action==='winutil-launch')return showModal({title:'Abrir WinUtil na estação local?',desc:'Abre a cópia revisada na estação deste técnico, em uma janela separada. As operações dentro do WinUtil não são registradas pelo Fleury. Não executa na máquina selecionada no topo.',actionText:'Abrir cópia revisada',onConfirm:async()=>{const d=await request('winutil/launch',{confirm:true});toast(d.result.message);}});
 return previousIntegrationAct(action,data);
};
const previousIntegrationWinutil=winutil;
winutil=function(){return previousIntegrationWinutil()+`<div class="section-gap"><button class="btn primary" data-act="winutil-launch">Abrir WinUtil local revisado</button></div>`;};
