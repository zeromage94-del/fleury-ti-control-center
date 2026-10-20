/* Recursos de diagnóstico somente leitura aproveitados dos vídeos de referência. */
'use strict';
MENUS.splice(MENUS.findIndex(x=>x[0]==='scripts'),0,['remoteconsole','list','Console de Diagnóstico']);
S.remoteConsoleResult=null;
S.remoteConsoleType='';
const REMOTE_READONLY=[
 ['apps','Aplicativos instalados','Lista de software instalado por máquina','download'],
 ['processes','Processos e memória','Processos com maior consumo de RAM','list'],
 ['drives','Discos e unidades de rede','Armazenamento local e mapeamentos visíveis','monitor'],
 ['startup','Inicialização do Windows','Programas configurados para iniciar','settings'],
 ['updates','Atualizações do Windows','Atualizações recentes e estado do sistema','refresh'],
 ['services','Serviços do Windows','Consulta de serviços relevantes','settings'],
 ['network','Conexão de rede','Interfaces e configuração de rede','wifi']
];
function remoteConsole(){
 const machine=selected();
 const cards=REMOTE_READONLY.map(([key,label,desc,icon])=>`<button type="button" class="action-card" data-act="remote-readonly" data-type="${esc(key)}"><span class="action-icon">${ico(icon)}</span><span><strong>${esc(label)}</strong><small>${esc(desc)}</small></span></button>`).join('');
 const result=S.remoteConsoleResult&&S.remoteConsoleResult.target===machine?.target
  ?panel('Resultado: '+esc(S.remoteConsoleResult.label),'list',`<div class="panel-body">${prettyData(S.remoteConsoleResult.result)}</div>`)
  :panel('Resultado de consulta','list',empty('Escolha uma operação acima para consultar o equipamento.','info'));
 return pageHead('Console de Diagnóstico','Funções úteis inspiradas nos vídeos: consulta de processos, software, unidades, inicialização, serviços e atualizações.')+
 `<div class="workspace"><div class="stack">${panel('Operações de consulta remota','list',`<div class="panel-body"><p class="hint">Selecione a máquina no topo da tela. As operações são somente leitura e usam WinRM administrativo autorizado.</p><div class="action-grid">${cards}</div></div>`)}<div class="section-gap">${result}</div></div>
 <div class="stack">${panel('Equipamento selecionado','monitor',machineInfo())}<div class="note blue">Os vídeos mostram também terminais e configurações sensíveis. Neste módulo, alterações em registros, certificados, políticas ou processos não são executadas; essas operações exigiriam avaliação específica de risco.</div></div></div>`;
}
const prevVideoSettings=settings;
settings=function(){
 return prevVideoSettings()+`<div class="section-gap">${panel('Aplicativo local','settings',`<div class="panel-body"><p class="hint">Fecha o servidor local. Fechar somente a guia do navegador não encerra o aplicativo.</p><button type="button" class="btn danger" data-act="stop-app">${ico('power')} Encerrar aplicativo</button></div>`)}</div>`;
};
const prevVideoRender=render;
render=function(){
 if(S.page!=='remoteconsole')return prevVideoRender();
 sidebar();main.innerHTML=remoteConsole()+`<footer class="page-credit">Criado por Ana Tazinaffo</footer>`;
 document.querySelector('#user-name').textContent=S.stats.username||'Técnico de TI';
 document.querySelector('#avatar').textContent=(S.stats.username||'T').trim().slice(0,1).toUpperCase();
 document.querySelector('#search-icon').innerHTML=ico('search');
 syncGlobalTarget();
};
const prevVideoAct=act;
act=async function(action,data={}){
 if(action==='stop-app')return showModal({title:'Encerrar o Fleury TI Control Center?',desc:'O servidor local será desligado. Para voltar, abra o programa novamente.',actionText:'Encerrar aplicativo',danger:true,onConfirm:async()=>{
  await request('system/shutdown',{confirm:true});
  toast('Aplicativo encerrado. Já pode fechar o navegador.');
 }});
 if(action==='remote-readonly'){
  const m=currentMachine();if(!m)return;
  const type=data.type||'';
  const item=REMOTE_READONLY.find(x=>x[0]===type);
  if(!item){toast('Consulta desconhecida.',true);return;}
  const path=['updates','services','network'].includes(type)?`diagnostics/${type}`:`diagnostics/remote-console`;
  return busyCall(async()=>{
   const d=await request(`${path}?target=${encodeURIComponent(m.target)}`+(['updates','services','network'].includes(type)?'':`&type=${encodeURIComponent(type)}`));
   S.remoteConsoleResult={target:m.target,label:item[1],result:d.result};
   render();toast('Consulta concluída em '+m.target+'.');
  },'');
 }
 return prevVideoAct(action,data);
};
