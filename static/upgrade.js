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
 S.downloadsPreview=null;S.downloadsSelected=new Set();
 hideMachinePopup();render();
}
const globalTargetSelect=document.querySelector('#global-machine-picker');
globalTargetSelect.addEventListener('change',e=>setActiveTarget(e.target.value));
document.querySelector('#global-add-machine').addEventListener('click',()=>act('add-machine'));
S.downloadsDays=30;S.downloadsPreview=null;S.downloadsSelected=new Set();S.downloadsResult=null;
function downloadsPanel(machine){
 const preview=S.downloadsPreview?.target===machine?.target?S.downloadsPreview:null;
 const result=S.downloadsResult?.target===machine?.target?S.downloadsResult:null;
 const files=preview?.files||[];
 return panel('Downloads • revisão de todos os perfis','download',`<div class="panel-body">
 <p class="hint">Downloads pode conter arquivos pessoais. Esta opção é separada da otimização rápida: primeiro consulte os arquivos antigos, selecione individualmente e confirme a exclusão. Nada é selecionado automaticamente.</p>
 <div class="toolbar-group"><label><span class="field-label">Idade mínima</span><select class="select" id="downloads-days">${[30,60,90,180,365].map(d=>`<option value="${d}" ${S.downloadsDays===d?'selected':''}>${d} dias</option>`).join('')}</select></label><button class="btn" data-act="downloads-preview" ${!machine?'disabled':''}>Consultar prévia de Downloads</button></div>
 ${preview?`<p class="hint">Prévia de ${esc(preview.target)}: ${files.length} arquivo(s) elegível(is). A prévia expira; arquivos alterados, recentes, bloqueados ou em atalhos de pasta são preservados.</p>${files.length?`<div class="table-scroll"><table><thead><tr><th>Selecionar</th><th>Perfil</th><th>Arquivo</th><th>Tamanho</th></tr></thead><tbody>${files.map(f=>`<tr><td><input type="checkbox" data-download-id="${esc(f.id)}" ${S.downloadsSelected.has(f.id)?'checked':''} aria-label="Selecionar ${esc(f.name)} do perfil ${esc(f.profile)}"></td><td>${esc(f.profile)}</td><td>${esc(f.name)}</td><td>${esc((Number(f.bytes||0)/1048576).toFixed(2))} MB</td></tr>`).join('')}</tbody></table></div><p><button class="btn danger" data-act="downloads-cleanup" ${!S.downloadsSelected.size?'disabled':''}>Excluir ${S.downloadsSelected.size} arquivo(s) selecionado(s)</button></p>`:'<p>Nenhum arquivo elegível retornado nesta prévia.</p>'}${preview.result?`<details><summary>Resultado da inspeção</summary>${prettyData(preview.result)}</details>`:''}`:''}
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
 <div class="scripts-hero">${panel('Otimização rápida • Todos os perfis','bolt',`<div class="panel-body"><p class="hint">Remove somente .tmp/.temp antigos de Windows\\Temp e AppData\\Local\\Temp dos perfis locais, inclusive desconectados. Preserva fotos, documentos, software e arquivos em uso. Sem simulação; executa após confirmação do técnico.</p><div class="toolbar-group"><label><span class="field-label">Idade mínima</span><select class="select" id="quick-cleanup-days">${[7,14,30,60,90].map(d=>`<option value="${d}" ${S.quickDays===d?'selected':''}>${d} dias</option>`).join('')}</select></label><button class="btn primary" data-act="quick-optimize">${ico('bolt')} Otimizar agora</button><button class="btn" data-act="cleanup-run">${ico('refresh')} Limpar temporários de todos os usuários</button></div></div>`)}
 ${panel('Restauração do sistema','clock',`<div class="panel-body"><p class="hint">Crie antes da manutenção, liste e exclua seletivamente um ponto antigo (≥ 14 dias). O ponto mais novo é protegido. Não elimina backups externos.</p><div class="toolbar-group"><button class="btn primary" data-act="restore-create">${ico('check')} Criar ponto</button><button class="btn" data-act="restore-list">${ico('list')} Listar pontos</button></div>${restoreRows}</div>`)}
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
 ${quickBtn('power','Reiniciar estação','restart','Com confirmação')}
 </div></div>`)}
 </div>${S.diagnostics?.target===m?.target?`<div class="section-gap">${panel(esc(S.diagnostics.label),'list',`<div class="panel-body">${prettyData(S.diagnostics.result)}</div>`)}</div>`:''}
 <div class="note blue">As ações remotas exigem WinRM e credenciais existentes da TI. Não alteram políticas EDR/GPO nem desinstalam programas automaticamente. DISM, CHKDSK e SFC podem ser demorados; faça fora de procedimentos laboratoriais ativos.</div>`;
};
// Reimplementa a renderização da última versão para registrar a nova aba;
// não interfere nos dados armazenados, apenas troca o conteúdo visível.
render=function(){
 if(S.downloadsPreview&&S.downloadsPreview.target!==S.selected){S.downloadsPreview=null;S.downloadsSelected=new Set();}
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
 if(action==='downloads-preview'){
  const m=currentMachine();if(!m)return;
  const days=Number(document.querySelector('#downloads-days')?.value||S.downloadsDays);S.downloadsDays=days;
  return busyCall(async()=>{
   S.downloadsPreview=null;S.downloadsSelected=new Set();S.downloadsResult=null;render();
   const d=await request(`maintenance/downloads-preview?target=${encodeURIComponent(m.target)}&days=${days}`);
   if(S.selected!==m.target)return;
   S.downloadsPreview={target:m.target,days,preview_id:d.preview_id,files:d.files||[],result:d.result};
   render();toast(d.message||'Prévia carregada. Revise e selecione apenas os arquivos que deseja excluir.',d.ok===false);
  },'');
 }
 if(action==='downloads-cleanup'){
  const m=currentMachine(),preview=S.downloadsPreview;
  if(!m||!preview||preview.target!==m.target)return toast('Consulte uma nova prévia para o computador selecionado.',true);
  const files=[...S.downloadsSelected].filter(id=>preview.files.some(f=>f.id===id));
  if(!files.length)return toast('Selecione individualmente os arquivos a excluir.',true);
  return showModal({title:'Excluir Downloads selecionados?',danger:true,
   desc:`Computador ${m.target}: excluir ${files.length} arquivo(s) de Downloads dos perfis listados. São arquivos pessoais; confirme que podem ser descartados. A exclusão não vai para a Lixeira. A prévia será consumida e precisará ser refeita.`,actionText:'Excluir arquivos selecionados',onConfirm:async()=>{
    if(S.selected!==m.target||S.downloadsPreview!==preview)throw Error('O computador ou a prévia mudou. Consulte novamente.');
    S.downloadsPreview=null;S.downloadsSelected=new Set();render();
    const d=await request('maintenance/downloads-cleanup',{target:m.target,preview_id:preview.preview_id,files,confirm:true});
    S.downloadsResult={target:m.target,...d};render();toast(d.message||'Confira o resultado da limpeza de Downloads.',d.ok===false);
   }});
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
 if(e.target.id==='downloads-days'){
  S.downloadsDays=Number(e.target.value);S.downloadsPreview=null;S.downloadsSelected=new Set();render();
 }
 if(e.target.matches?.('[data-download-id]')){
  const preview=S.downloadsPreview,id=e.target.dataset.downloadId;
  if(preview?.target!==S.selected||!preview.files.some(f=>f.id===id))return;
  if(e.target.checked)S.downloadsSelected.add(id);else S.downloadsSelected.delete(id);
  render();
 }
});
