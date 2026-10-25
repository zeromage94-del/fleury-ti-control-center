/* v1.0 - seletor explicito e menu de contexto, sem comandos ocultos */
'use strict';
const machineMenuRoot=document.createElement('div');
machineMenuRoot.id='machine-menu-root';
document.body.appendChild(machineMenuRoot);
function selectedTargetBar(id='machine-target-main'){
 const m=selected();
 return `<section class="target-toolbar" aria-label="Selecionar equipamento para executar comandos">
 <div class="target-toolbar-heading">${ico('monitor')}<div><strong>Máquina / IP para executar comandos</strong><small>Escolha a estação da rede antes de abrir a ferramenta</small></div></div>
 <div class="target-toolbar-controls">${machinePicker(id)}
 <button class="btn target-add" data-act="add-machine">${ico('plus')} Adicionar IP</button>
 <button class="btn primary" data-act="commands-page" ${m?'':'disabled'}>${ico('bolt')} Comandos</button>
 <button class="btn target-install" data-act="software-page" ${m?'':'disabled'}>${ico('download')} Instalação</button></div>
 <div class="target-toolbar-status">${m?`Selecionada: <strong>${esc(m.name)} · ${esc(m.target)}</strong>`:'<strong>Selecione uma máquina para continuar</strong>'}</div>
 </section>`;
}
const previousMachinesV10=machines;
// Comandos Rápidos e instalação mostram sua própria seleção persistente; uma barra extra fica visível acima da tabela.
const previousDashboardV10=dashboard;
dashboard=function(){
 const original=previousDashboardV10();
 return original.replace('<div class="dashboard-grid">',selectedTargetBar('dashboard-target-main')+'<div class="dashboard-grid">');
};
function hideMachinePopup(){machineMenuRoot.innerHTML='';}
function showMachinePopup(target,xy){
 const m=S.machines.find(x=>x.target===target);
 if(!m)return toast('O equipamento não está cadastrado.',true);
 S.selected=m.target;
 S.inventory=null;S.printers=null;S.diagnostics=null;S.restorePoints=null;
 hideMachinePopup();
 render();
 machineMenuRoot.innerHTML=`<div class="machine-menu" role="menu" aria-label="Ações rápidas de ${esc(m.name)}">
 <div class="machine-menu-title">${ico('monitor')} <div><strong>${esc(m.name)}</strong><small>${esc(m.target)} · ${esc(m.status)}</small></div><button type="button" class="machine-menu-close" aria-label="Fechar menu">×</button></div>
 <div class="machine-menu-tools">
 <button role="menuitem" data-mini-action="quick-optimize">${ico('bolt')}<span>Otimizar agora<small>Limpar temporários antigos</small></span></button>
 <button role="menuitem" data-mini-action="cleanup-run">${ico('refresh')}<span>Limpar temporários<small>Todos os perfis locais</small></span></button>
 <button role="menuitem" data-mini-action="guided-disk">${ico('monitor')}<span>HD em 100%<small>Diagnóstico orientado</small></span></button>
 <button role="menuitem" data-mini-action="restart">${ico('power')}<span>Reiniciar computador<small>Execução direta</small></span></button>
 <button role="menuitem" data-mini-action="rdp">${ico('monitor')}<span>Acesso remoto (RDP)<small>Com credenciais autorizadas</small></span></button>
 <button role="menuitem" data-mini-action="inventory">${ico('list')}<span>Consultar inventário<small>Windows e hardware</small></span></button>
 <button role="menuitem" data-mini-action="software-page">${ico('download')}<span>Instalar programas<small>Catálogo de softwares</small></span></button>
 <button role="menuitem" data-mini-action="commands-page">${ico('settings')}<span>Ver todas as ferramentas<small>Scripts e manutenção</small></span></button>
 </div></div>`;
 const menu=machineMenuRoot.firstElementChild;
 const w=305, h=Math.min(window.innerHeight-16,menu.scrollHeight||480);
 const left=Math.max(8,Math.min(window.innerWidth-w-8,xy.x-260));
 let top=xy.y+8;
 if(top+h>window.innerHeight-8)top=Math.max(8,xy.y-h-8);
 menu.style.left=`${left}px`;menu.style.top=`${top}px`;
 menu.focus?.();
}
main.addEventListener('click',e=>{
 const row=e.target.closest('[data-machine-row]');
 if(!row)return;
 e.stopImmediatePropagation();
 const rect=(e.target.closest('[data-machine-arrow]')||row).getBoundingClientRect();
 showMachinePopup(row.dataset.machineRow,{x:rect.right,y:rect.top});
},true);
main.addEventListener('keydown',e=>{
 if((e.key==='Enter'||e.key===' ')&&e.target.matches('tr[data-machine-row]')){
   e.preventDefault();const r=e.target.getBoundingClientRect();showMachinePopup(e.target.dataset.machineRow,{x:r.right,y:r.top});
 }
});
machineMenuRoot.addEventListener('click',async e=>{
 if(e.target.closest('.machine-menu-close')){hideMachinePopup();return;}
 const btn=e.target.closest('[data-mini-action]');if(!btn)return;
 const action=btn.dataset.miniAction; hideMachinePopup();
 try{await act(action);}catch(err){toast(err.message,true);}
});
document.addEventListener('click',e=>{
 if(machineMenuRoot.children.length&&!e.target.closest('#machine-menu-root')&&!e.target.closest('[data-machine-row]'))hideMachinePopup();
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')hideMachinePopup();});
main.addEventListener('change',e=>{
 if(['machine-target-main','dashboard-target-main'].includes(e.target.id)){
  S.selected=e.target.value||null;S.inventory=null;S.printers=null;S.diagnostics=null;S.restorePoints=null;hideMachinePopup();render();
 }
});
// Don't destroy selectors under the cursor during passive refresh.
const previousRefreshV10=refresh;
refresh=async function(quiet=false){
 if(quiet && (machineMenuRoot.children.length || ['SELECT','INPUT'].includes(document.activeElement?.tagName)))return;
 await previousRefreshV10(quiet);
};
