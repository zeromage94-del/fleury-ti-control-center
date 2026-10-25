/* v0.9: Catálogo WinGet em grupos, inspirado na disposição do WinUtil.
 * Código próprio; nenhum PowerShell externo baixado, nenhum script arbitrário.
 * O alvo é o equipamento cadastrado/selecionado. Operações geram auditoria.
 */
'use strict';
S.softwareCatalog=[];
S.softwareSelected=new Set();
S.softwareCategory='Todas';
S.softwareSearch='';
S.softwareResult=null;

function commands(){
 return pageHead('Comandos Rápidos', 'Diagnósticos e manutenção autorizada da estação selecionada.')+
 `<div class="workspace command-layout"><div class="stack">
 ${panel('Ferramentas · Windows 10 / 11', 'bolt', quickPanel())}</div>
 <div class="stack">${panel('Computador selecionado', 'monitor', machineInfo())}
 <div class="note blue">Operações via WinRM já autorizado pela TI, com registro de auditoria. Não instala agentes ocultos nem altera políticas de segurança.</div>
 <div class="note">Em laboratório, não reinicie máquinas ou serviços em meio a exames, etiquetagem ou pagamentos. O diagnóstico de disco em 100% não garante reparo automático.</div></div></div>`;
}

const SW_GROUP_ORDER=['Navegadores','Arquivos e PDF','Produtividade','TI e desenvolvimento','Utilitários'];
function swGrouping(items){
 const groups={}; for(const p of items){(groups[p.category]??=[]).push(p);}
 return Object.keys(groups).sort((a,b)=>{
  const ai=SW_GROUP_ORDER.indexOf(a),bi=SW_GROUP_ORDER.indexOf(b);
  return (ai<0?999:ai)-(bi<0?999:bi)||a.localeCompare(b);
 }).map(c=>[c,groups[c]]);
}
function swItem(p){
 const selected=S.softwareSelected.has(p.key);
 return `<label class="sw-checkrow ${selected?'sw-active':''}">
  <input type="checkbox" data-software-key="${esc(p.key)}" ${selected?'checked':''} aria-label="Selecionar ${esc(p.name)}">
  <span class="sw-row-text"><strong>${esc(p.name)}</strong><small>${esc(p.description)}</small></span>
  <span class="sw-pack-icon" title="Pacote ${esc(p.winget_id)}">${ico('check')}</span></label>`;
}
function software(){
 const entries=S.softwareCatalog||[];
 const categories=['Todas',...swGrouping(entries).map(([name])=>name)];
 const term=(S.softwareSearch||'').toLowerCase().trim();
 const show=entries.filter(p=>(S.softwareCategory==='Todas'||p.category===S.softwareCategory) &&
   `${p.name} ${p.description} ${p.category} ${p.winget_id}`.toLowerCase().includes(term));
 const groups=swGrouping(show);
 const machine=selected();
 const selectedNames=[...S.softwareSelected].map(k=>S.softwareCatalog.find(p=>p.key===k)?.name||k);
 const sub=`Lista organizada como no WinUtil, sem jogos. Pacotes de catálogo fechado via fonte WinGet; requer aprovação corporativa.`;
 const groupsHtml=groups.length?groups.map(([category,items])=>
  `<section class="sw-group"><div class="sw-group-title">${ico('download')} <span>${esc(category)}</span><small>${items.length}</small></div>
  <div class="sw-group-list">${items.map(swItem).join('')}</div></section>`).join(''):
  `<div class="sw-none">${entries.length?'Nenhum aplicativo corresponde à pesquisa.':'Catálogo não carregado. Clique em Atualizar.'}</div>`;
 const result=S.softwareResult?`<section class="sw-result">${panel('Resultado da última operação','list',
    `<div class="panel-body"><span class="chip ${S.softwareResult.ok?'green':'red'}">${S.softwareResult.ok?'Concluído':'Verificar detalhes'}</span>
    <p class="hint">${esc(S.softwareResult.type)} em ${esc(S.softwareResult.target)}.</p>${prettyData(S.softwareResult.result)}</div>`)}</section>`:'';
 return pageHead('Instalação de Software',sub)+
 `<div class="sw-topband">
 <div class="sw-topbrand">${ico('download')} <div><strong>Central de aplicativos</strong><small>Instale ou remova apenas o que for permitido na sua unidade</small></div></div>
 <span class="sw-source">${ico('shield')} Fonte: <b>WinGet</b> · Sem jogos</span></div>
 <div class="sw-main-layout">
 <div class="sw-main-col">
 <div class="sw-toolbar"><div class="sw-search-input">${ico('search')} <input class="field" id="software-search" value="${esc(S.softwareSearch)}" placeholder="Pesquisar aplicativo, categoria ou ID do pacote..." aria-label="Pesquisar aplicativos"></div>
 <button class="btn sm" data-act="software-refresh">${ico('refresh')} Atualizar catálogo</button></div>
 <div class="sw-cat-tabs" role="group" aria-label="Filtrar categorias">${categories.map(c=>
  `<button type="button" class="sw-cat-tab ${S.softwareCategory===c?'active':''}" data-act="software-category" data-category="${esc(c)}">${esc(c)}</button>`).join('')}</div>
 <div class="sw-groups">${groupsHtml}</div>
 ${result}
 <p class="sw-hint">Catálogo fechado de aplicativos conhecidos, adaptado do conceito visual do WinUtil. Não executa o comando <code>irm ... | iex</code>, nem instala ou remove ferramentas de segurança corporativa. A TI deve homologar os pacotes e versões antes de utilizar em produção.</p>
 </div>
 <aside class="sw-sidecol">
 <div class="sw-target-card"><header>${ico('monitor')} <strong>Computador de destino</strong></header>
 <label class="field-label" for="software-picker">Máquina selecionada</label>
 ${machinePicker('software-picker')}
 <div class="sw-machine-info">${machine?`${ico('monitor')} <span><strong>${esc(machine.name)}</strong><small>${esc(machine.target)}</small></span>${statusTag(machine.status)}`:
  'Selecione um equipamento na lista de máquinas.'}</div>
 <div class="sw-side-divider"></div>
 <div class="sw-selection-label">Seleção atual <strong>${S.softwareSelected.size} de 5</strong></div>
 <div class="sw-picks">${selectedNames.length?selectedNames.map(x=>`<span class="sw-picked">${ico('check')} ${esc(x)}</span>`).join(''):
  '<small>Marque os aplicativos desejados no catálogo à esquerda.</small>'}</div>
 <button class="btn primary sw-action-btn" data-act="software-install" ${!machine||!S.softwareSelected.size?'disabled':''}>${ico('download')} Instalar selecionados</button>
 <button class="btn sw-uninstall-btn sw-action-btn" data-act="software-uninstall" ${!machine||!S.softwareSelected.size?'disabled':''}>${ico('upload')} Desinstalar selecionados</button>
 <button class="btn sw-clear-btn" data-act="software-clear" ${!S.softwareSelected.size?'disabled':''}>Limpar seleção</button>
 <div class="sw-policy">${ico('shield')} <span>Operações executadas ao clicar e auditadas. Sem bypass de bloqueios do Windows, EDR ou GPO.</span></div>
 </div>
 <div class="sw-side-note"><strong>Antes de executar</strong><p>WinGet exige contexto compatível e pode falhar via WinRM. Desinstalar <strong>remove programas</strong>, portanto não execute em softwares exigidos para o funcionamento do laboratório.</p></div>
 </aside></div>`;
}

let softwareCatalogPending=null;
S.softwareCatalogError='';
function fetchSoftwareCatalog(){
 if(softwareCatalogPending)return softwareCatalogPending;
 S.softwareCatalogError='';
 softwareCatalogPending=(async()=>{
  try{
   const d=await request('software/catalog');
   if(!Array.isArray(d.programs)||!d.programs.length)throw Error('Catálogo vazio ou inválido. Atualize o aplicativo e tente novamente.');
   S.softwareCatalog=d.programs;
   const allowed=new Set(d.programs.map(x=>x.key));
   S.softwareSelected=new Set([...S.softwareSelected].filter(k=>allowed.has(k)));
  }catch(e){S.softwareCatalogError=e.message;}
  finally{softwareCatalogPending=null;if(S.page==='software')render();}
 })();
 return softwareCatalogPending;
}

const originalSwSwitch=switchPage;
switchPage=function(page){
 originalSwSwitch(page);
 if(page==='software'&&!S.softwareCatalog.length){
  fetchSoftwareCatalog();
 }
};

const originalSwAct=act;
act=async function(action,data={}){
 if(action==='commands-page') return switchPage('commands');
 if(action==='software-page') return switchPage('software');
 if(action==='software-category'){
  S.softwareCategory=data.category||'Todas';render();return;
 }
 if(action==='guided-disk'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{
   const d=await request('diagnostics/disk-guided?target='+encodeURIComponent(m.target));
   S.diagnostics={target:m.target,label:'Disco 100% · Análise de causas',result:d.result};
   render();toast('Diagnóstico concluído.');
  },'');
 }
 if(action==='software-refresh') return fetchSoftwareCatalog();
 if(action==='software-clear'){S.softwareSelected.clear();render();return;}
 if(['software-install','software-uninstall'].includes(action)){
  const m=currentMachine();if(!m)return;
  const keys=[...S.softwareSelected];
  if(!keys.length)return toast('Selecione ao menos um aplicativo.',true);
  if(keys.length>5)return toast('Máximo de 5 programas por operação.',true);
  const uninstall=action==='software-uninstall';
  return busyCall(async()=>{
   const d=await request(uninstall?'software/uninstall':'software/install',{target:m.target,packages:keys});
   S.softwareResult={target:m.target,ok:!!d.ok,type:uninstall?'Desinstalação':'Instalação',result:d.result};
   render();toast(d.message||'Operação enviada. Acompanhe o resultado.',d.ok===false);
  },'');
 }
 return originalSwAct(action,data);
};

main.addEventListener('change',e=>{
 if(e.target.id==='software-picker'){
  S.selected=e.target.value||null;S.inventory=null;S.diagnostics=null;S.restorePoints=null;render();return;
 }
 if(e.target.matches('[data-software-key]')){
  const key=e.target.dataset.softwareKey;
  if(e.target.checked){
   if(S.softwareSelected.size>=20){e.target.checked=false;toast('Selecione até vinte programas por operação.',true);return;}
   S.softwareSelected.add(key);
  }else S.softwareSelected.delete(key);
  render();
 }
});
main.addEventListener('input',e=>{
 if(e.target.id==='software-search'){
  const caret=e.target.selectionStart;S.softwareSearch=e.target.value;
  render();const el=document.querySelector('#software-search');
  if(el){el.focus();el.setSelectionRange(caret,caret);}
 }
});
