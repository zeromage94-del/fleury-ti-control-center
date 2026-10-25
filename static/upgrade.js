/* Fleury TI v1.1: seleção global, Scripts reais, catálogo WinUtil controlado. */
'use strict';
// Mantém a seleção entre páginas e permite alterá-la sem sair da página.
function syncGlobalTarget(){
 const picker=document.querySelector('#global-machine-picker');
 if(!picker)return;
 const focus=document.activeElement===picker;
 const items=['<option value="">Selecione uma máquina...</option>'].concat(S.machines.map(m=>`<option value="${esc(m.target)}" ${m.target===S.selected?'selected':''}>${esc(m.name)} · ${esc(m.target)}</option>`));
 // Não recria enquanto o usuário abre a lista.
 if(!focus)picker.innerHTML=items.join('');
}
function setActiveTarget(target){
 S.selected=S.machines.some(m=>m.target===target)?target:null;
 S.inventory=null;S.diagnostics=null;S.restorePoints=null;S.printers=null;S.cleanupPreview=null;
 hideMachinePopup();render();
}
const globalTargetSelect=document.querySelector('#global-machine-picker');
globalTargetSelect.addEventListener('change',e=>setActiveTarget(e.target.value));
document.querySelector('#global-add-machine').addEventListener('click',()=>act('add-machine'));
S.downloadsResult=null;
function downloadsPanel(machine){
 const valid=machine&&deviceType(machine)==='computer';
 const result=S.downloadsResult?.target===machine?.target?S.downloadsResult:null;
 return panel('Downloads • todos os usuários','download',`<div class="panel-body">
 <p class="hint">O clique exclui definitivamente todos os arquivos de Downloads de todos os perfis locais do computador selecionado, incluindo subpastas, arquivos recentes e todos os formatos. Sem prévia, seleção ou confirmação adicional.</p>
 <p><strong>Computador:</strong> ${esc(machine?.target||'Selecione um computador')}</p>
 <button class="btn danger" data-act="downloads-cleanup" ${!valid||S.busy?'disabled':''}>Excluir todos os Downloads de todos os usuários</button>
 <p class="hint">Arquivos em uso, falhas de permissão e pastas redirecionadas são informados no resultado. A pasta Downloads de cada usuário é preservada.</p>
 ${result?`<div class="note ${result.ok===false?'red':'blue'}">${esc(result.message||'Confira o resultado da limpeza de Downloads.')}</div>${prettyData(result.result)}`:''}
 </div>`);
}
// Inclui um painel próprio WinUtil, ao lado do catálogo de instalação nativo.
// Catálogo único: atalhos legados são redirecionados para software.
function winutil(){
 const body=software().replace('Instalação de Software','WinUtil • Instalar e Desinstalar');
 const official=`<section class="winutil-official"><div><strong>${ico('shield')} WinUtil original — Chris Titus Tech</strong><p>O catálogo abaixo funciona dentro do Fleury TI por WinGet, com permissões autorizadas. O projeto original abre em PowerShell separado; não é incorporado nem executado automaticamente em máquinas remotas.</p><code id="winutil-official-command">irm https://christitus.com/win | iex</code></div><div class="winutil-links"><button type="button" class="btn" data-act="winutil-copy">${ico('list')} Copiar comando oficial</button><button type="button" class="btn" data-act="winutil-repo">${ico('link')} Abrir GitHub oficial</button><button type="button" class="btn primary" data-act="software-page">${ico('download')} Central de instalação</button></div></section>`;
 return body.replace('<div class="sw-topband">',official+'<div class="sw-topband">');
}
// Este painel SUBSTITUI a antiga biblioteca, que não tinha limpeza nem restauração.
scripts=function(){
 const m=selected();
 const points=S.restorePoints?.target===m?.target?S.restorePoints.result?.Pontos||[]:[];
 const restoreRows=points.length?`<div class="restore-quick-list">${points.map(p=>`<div class="restore-quick"><div><strong>#${esc(p.Numero)}</strong> ${esc(p.Descricao)} <small>${esc(p.CriadoEm)} · ${esc(p.IdadeDias)} dias</small></div>${!p.MaisRecente&&Number(p.IdadeDias)>=14?`<button type="button" class="btn sm danger" data-act="restore-delete" data-sequence="${esc(p.Numero)}">Excluir este ponto</button>`:'<span class="chip green">Preservado</span>'}</div>`).join('')}</div>`:'<p class="hint">Clique em Listar pontos para consultar e habilitar a exclusão dos elegíveis.</p>';
 return pageHead('Scripts e automações','Limpeza de temporários de todos os usuários, Windows 11, restauração e reparos. Scripts predefinidos e auditados.')+
 `<div class="scripts-first">${panel('Máquina para executar os scripts','monitor',`<div class="panel-body toolbar-group">${machinePicker('scripts-machine-picker')}<button class="btn" data-act="add-machine">${ico('plus')} Adicionar IP</button><button class="btn" data-act="verify">${ico('wifi')} Ping</button><span class="hint">O mesmo IP pode ser alterado no topo de qualquer tela.</span></div>`)}</div>
 <div class="scripts-hero">${panel('Otimização rápida • Todos os perfis','bolt',`<div class="panel-body"><p class="hint">Remove somente .tmp/.temp antigos de Windows\\Temp e AppData\\Local\\Temp dos perfis locais, inclusive desconectados. Preserva fotos, documentos, software e arquivos em uso. Sem simulação; executa ao clicar.</p><div class="toolbar-group"><label><span class="field-label">Idade mínima</span><select class="select" id="quick-cleanup-days">${[7,14,30,60,90].map(d=>`<option value="${d}" ${S.quickDays===d?'selected':''}>${d} dias</option>`).join('')}</select></label><button class="btn primary" data-act="quick-optimize">${ico('bolt')} Otimizar agora</button><button class="btn" data-act="cleanup-run">${ico('refresh')} Limpar temporários de todos os usuários</button></div></div>`)}
 ${panel('Restauração do sistema','clock',`<div class="panel-body"><p class="hint">Crie antes da manutenção, liste e exclua seletivamente um ponto antigo (≥ 14 dias). O ponto mais novo é protegido. Não elimina backups externos.</p><p><label>Descrição do ponto <input class="field" id="restore-description" value="Fleury TI - antes da manutenção" maxlength="100"></label></p><div class="toolbar-group"><button class="btn primary" data-act="restore-create">${ico('check')} Criar ponto</button><button class="btn" data-act="restore-list">${ico('list')} Listar pontos</button></div>${restoreRows}</div>`)}
 </div><div class="section-gap">${downloadsPanel(m)}</div><div class="section-gap">${panel('Ferramentas Windows 10 / 11 e diagnóstico HD 100%','settings',`<div class="panel-body"><div class="quick-grid">
 ${quickBtn('monitor','HD em 100%','diagnostic','Analisar I/O e eventos','data-type="disk-100"')}
 ${quickBtn('list','Disco · análise guiada','guided-disk','Espaço, disco, saúde')}
 ${quickBtn('refresh','CPU e RAM','diagnostic','Análise de desempenho','data-type="performance"')}
 ${quickBtn('shield','DISM CheckHealth','disk-tool','Integridade Windows','data-tool="dism-check"')}
 ${quickBtn('settings','DISM RestoreHealth','disk-tool','Reparação de componentes','data-tool="dism-repair"')}
 ${quickBtn('check','SFC /scannow','disk-tool','Arquivos de sistema','data-tool="sfc-scan"')}
 ${quickBtn('monitor','CHKDSK /scan','disk-tool','Verificar disco','data-tool="chkdsk-scan"')}
 ${quickBtn('refresh','Reiniciar SysMain','disk-service','Não desativa serviço','data-service="SysMain"')}
 ${quickBtn('search','Reiniciar Search','disk-service','Não desativa serviço','data-service="WSearch"')}
 ${quickBtn('wifi','Limpar DNS','quick-flush-dns','Cache sem alterar IP')}
 ${quickBtn('printer','Reiniciar Spooler','spooler','Interrompe impressão')}
 ${quickBtn('shield','Diagnóstico PINPAD','diagnostic','USB/COM e TEF','data-type="pinpad"')}
 ${quickBtn('printer','Zebra / PINPAD','maintenance-page','Mais ferramentas')}
 ${quickBtn('list','Inventário remoto','inventory','Hardware e Windows')}
 ${quickBtn('terminal','PowerShell Remoting','terminal','Requer WinRM')}
 ${quickBtn('power','Reiniciar estação','restart','Execução direta')}
 </div></div>`)}
 </div>${S.diagnostics?.target===m?.target?`<div class="section-gap">${panel(esc(S.diagnostics.label),'list',`<div class="panel-body">${prettyData(S.diagnostics.result)}</div>`)}</div>`:''}
 <div class="note blue">As ações remotas exigem WinRM e credenciais existentes da TI. Não alteram políticas EDR/GPO nem desinstalam programas automaticamente. DISM, CHKDSK e SFC podem ser demorados; faça fora de procedimentos laboratoriais ativos.</div>`;
};
// Reimplementa a renderização da última versão para registrar a nova aba;
// não interfere nos dados armazenados, apenas troca o conteúdo visível.
render=function(){
 sidebar();
 const fns={dashboard,machines,remote,printers,tickets,scripts,logs,settings,assets,maintenancePage,commands,software,winutil};
 const page=S.page==='maintenance'?'maintenancePage':S.page;
 main.innerHTML=(fns[page]||dashboard)()+`<footer class="page-credit">Criado por Ana Tazinaffo</footer>`;
 document.querySelector('#user-name').textContent=S.stats.username||'Técnico de TI';
 document.querySelector('#avatar').textContent=(S.stats.username||'T').trim().slice(0,1).toUpperCase();
 document.querySelector('#search-icon').innerHTML=ico('search');
 syncGlobalTarget();
};
const previousUpgradeSwitch=switchPage;
switchPage=function(page){
 previousUpgradeSwitch(page);
 if(page==='winutil'&&!S.softwareCatalog.length)busyCall(fetchSoftwareCatalog,'');
};
const previousUpgradeAct=act;
act=async function(action,data={}){
 if(action==='downloads-cleanup'){
  const m=currentMachine();if(!m)return;
  if(deviceType(m)!=='computer')return toast('Selecione um computador identificado.',true);
  return busyCall(async()=>{
   if(S.selected!==m.target)throw Error('O computador selecionado mudou.');
   S.downloadsResult=null;render();
   const d=await request('maintenance/downloads-cleanup',{target:m.target});
   S.downloadsResult={target:m.target,...d};render();toast(d.message||'Confira o resultado da limpeza de Downloads.',d.ok===false);
  },'');
 }
 if(action==='winutil-copy'){
  const command='irm https://christitus.com/win | iex';
  try{await navigator.clipboard.writeText(command);toast('Comando oficial copiado. Revise o código e execute somente em terminal autorizado.');}
  catch(e){showModal({title:'Comando oficial do WinUtil',desc:command+' — Copie e execute manualmente apenas em ambiente aprovado.',actionText:'Fechar'});}
  return;
 }
 if(action==='winutil-repo'){window.open('https://github.com/ChrisTitusTech/winutil','_blank','noopener,noreferrer');return;}
 if(action==='software-page'&&S.page==='winutil')return switchPage('software');
 return previousUpgradeAct(action,data);
};
main.addEventListener('change',e=>{
 if(e.target.id==='scripts-machine-picker')setActiveTarget(e.target.value);
});
