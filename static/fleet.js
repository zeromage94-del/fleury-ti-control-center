'use strict';
S.softwareJobs=[]; S.softwareCollapsed=new Set(); S.softwareSubmitting=false;
const DEVICE_NAMES={computer:'Computadores',printer:'Impressoras',unknown:'Não identificados'};
function deviceType(m){return ['computer','printer'].includes(m?.device_type)?m.device_type:'unknown';}
function groupedMachineOptions(computersOnly=false){
 return '<option value="">Selecione o equipamento...</option>'+Object.entries(DEVICE_NAMES).map(([kind,label])=>{
  const items=S.machines.filter(m=>deviceType(m)===kind);
  if(!items.length)return '';
  return `<optgroup label="${label}${computersOnly&&kind!=='computer'?' · indisponíveis para instalação':''}">${items.map(m=>`<option value="${esc(m.target)}" ${S.selected===m.target?'selected':''} ${computersOnly&&kind!=='computer'?'disabled':''}>${esc(m.name)} · ${esc(m.target)}</option>`).join('')}</optgroup>`;
 }).join('');
}
machinePicker=function(id='machine-picker'){return `<select class="select" id="${id}" aria-label="Equipamento de destino">${groupedMachineOptions(id==='software-picker')}</select>`;};
syncGlobalTarget=function(){const picker=document.querySelector('#global-machine-picker');if(picker&&document.activeElement!==picker)picker.innerHTML=groupedMachineOptions();};
const fleetOldMachines=machines;
machines=function(){
 const summary=Object.entries(DEVICE_NAMES).map(([kind,label])=>`<span class="chip">${label}: ${S.machines.filter(m=>deviceType(m)===kind).length}</span>`).join(' ');
 const groups=Object.entries(DEVICE_NAMES).map(([kind,label])=>{
  const items=S.machines.filter(m=>deviceType(m)===kind);
  return panel(`${label} (${items.length})`,kind==='printer'?'printer':'monitor',items.length?`<div class="table-scroll"><table><thead><tr><th>Equipamento / IP</th><th>Estado</th><th>Identificação</th><th>Tipo</th><th></th></tr></thead><tbody>${items.map(m=>`<tr><td><strong>${esc(m.name)}</strong><br>${esc(m.target)}</td><td>${statusTag(m.status)}</td><td>${esc(m.type_evidence||'Não confirmado')}</td><td><select class="select" data-device-kind="${esc(m.target)}" aria-label="Tipo de ${esc(m.name)}">${Object.entries(DEVICE_NAMES).map(([v,n])=>`<option value="${v}" ${kind===v?'selected':''}>${n}</option>`).join('')}</select></td><td><button class="btn sm" data-act="device-select" data-target="${esc(m.target)}">Selecionar</button></td></tr>`).join('')}</tbody></table></div>`:empty('Nenhum dispositivo neste grupo.'));
 }).join('<div class="section-gap"></div>');
 return pageHead('Rede e dispositivos','Computadores e impressoras separados. Identificação por serviços é provável; revise dispositivos antes de administrar.')+
 `<div class="panel-body"><div class="toolbar-group"><button class="btn primary" data-act="discover-local">Descobrir segmentos locais</button><button class="btn" data-act="discover-segments">Informar segmentos</button><button class="btn" data-act="neighbors">Vizinhos conhecidos</button><button class="btn" data-act="add-machine">Adicionar equipamento</button></div><p>${summary}</p><p class="hint">A descoberta testa ICMP e serviços TCP. Equipamentos isolados, desligados ou filtrados podem não aparecer. Em redes maiores que /24, informe também os outros segmentos autorizados.</p></div>${groups}`;
};
const SOFTWARE_COLORS=['#ff7f50','#4aabff','#41c9a4','#bc8df5','#f2c25d','#e78bac'];
swItem=function(p){const active=S.softwareSelected.has(p.key);const color=p.name.charCodeAt(0)%SOFTWARE_COLORS.length;return `<label class="wu-app ${active?'wu-checked':''}"><input type="checkbox" data-software-key="${esc(p.key)}" ${active?'checked':''} aria-label="Selecionar ${esc(p.name)}"><span class="wu-app-icon wu-icon-${color}">${esc(p.name.slice(0,2).toUpperCase())}</span><span><strong>${esc(p.name)}</strong><small>${esc(p.winget_id)}</small></span><span class="wu-scope" title="${esc(p.scope_note)}">PC</span></label>`;};
function jobsMarkup(){
 const names={queued:'Na fila',running:'Executando',succeeded:'Concluído',failed:'Falhou',interrupted:'Interrompido; verificar antes de repetir'};
 return S.softwareJobs.length?S.softwareJobs.slice(0,12).map(j=>`<details class="wu-job"><summary><span class="chip ${j.state==='succeeded'?'green':j.state==='failed'||j.state==='interrupted'?'red':'blue'}">${esc(names[j.state]||j.state)}</span> ${esc(j.operation==='install'?'Instalar':'Desinstalar')} · ${esc(j.target)} · ${j.packages.length} app(s)</summary><div class="panel-body"><p>${esc(j.error||'Escopo por máquina · todos os usuários quando suportado pelo instalador.')}</p>${prettyData(j.result)}</div></details>`).join(''): '<p class="hint">Nenhuma operação enviada. A fila continua funcionando quando você troca de aba.</p>';
}
software=function(){
 const machine=selected(),valid=machine&&deviceType(machine)==='computer';
 const entries=S.softwareCatalog||[];
 const groups=swGrouping(entries.filter(p=>(S.softwareCategory==='Todas'||p.category===S.softwareCategory)&&`${p.name} ${p.winget_id} ${p.category}`.toLowerCase().includes(S.softwareSearch.toLowerCase())));
 const categories=['Todas',...swGrouping(entries).map(([name])=>name)];
 return pageHead('Aplicativos • WinUtil remoto','Instalação e desinstalação silenciosas pelo WinGet na estação selecionada. Escopo obrigatório por máquina.')+
 `<section class="wu-shell"><header class="wu-top"><div><span class="wu-logo">${ico('download')}</span><strong>APLICATIVOS</strong><span class="chip">WinGet</span></div><label class="wu-search">${ico('search')}<input id="software-search" aria-label="Pesquisar aplicativos" placeholder="Pesquisar aplicativo ou pacote..." value="${esc(S.softwareSearch)}"></label></header>
 <nav class="wu-categories" aria-label="Categorias de aplicativos">${categories.map(c=>`<button class="${S.softwareCategory===c?'active':''}" data-act="software-category" data-category="${esc(c)}">${esc(c)}</button>`).join('')}</nav>
 <div class="wu-layout"><aside class="wu-actions"><h3>Equipamento</h3>${machinePicker('software-picker')}<p class="wu-destination">${valid?`<strong>${esc(machine.name)}</strong><br>${esc(machine.target)}`:'Selecione um computador identificado.'}</p><span class="chip">Todos os usuários · por máquina</span>
 <h3>Ações</h3><button class="btn primary" data-act="software-install" ${!valid||!S.softwareSelected.size||S.softwareSubmitting?'disabled':''}>Instalar selecionados</button><button class="btn danger" data-act="software-uninstall" ${!valid||!S.softwareSelected.size||S.softwareSubmitting?'disabled':''}>Desinstalar selecionados</button><button class="btn" data-act="software-installed" ${!valid?'disabled':''}>Consultar instalados</button>
 <h3>Seleção · ${S.softwareSelected.size}/20</h3><button class="btn" data-act="software-clear">Limpar seleção</button><button class="btn" data-act="software-collapse">Recolher categorias</button><button class="btn" data-act="software-expand">Expandir categorias</button><button class="btn" data-act="software-refresh">Atualizar catálogo</button>
 <p class="hint">Um clique envia à fila sem confirmação adicional. Usa as permissões administrativas existentes. Pacotes sem escopo por máquina falham, sem instalar só no perfil do técnico.</p></aside>
 <div class="wu-content">${groups.length?groups.map(([category,items])=>`<section class="wu-group"><button class="wu-group-heading" data-act="software-toggle" data-category="${esc(category)}">${S.softwareCollapsed.has(category)?'+':'−'} ${esc(category)} <small>${items.length}</small></button>${S.softwareCollapsed.has(category)?'':`<div class="wu-grid">${items.map(swItem).join('')}</div>`}</section>`).join(''):empty(entries.length?'Nenhum aplicativo encontrado.':'Carregando catálogo; use Atualizar se necessário.')}<div class="wu-footnote">Instalações por máquina ficam disponíveis aos usuários conforme suporte do pacote. Aplicativos individuais de outros perfis não são removidos por esta rotina.</div></div></div></section>
 <div class="section-gap">${panel('Fila de software em segundo plano','list',`<div id="software-job-list" class="panel-body">${jobsMarkup()}</div>`,`<button class="btn sm" data-act="software-jobs-refresh">Atualizar fila</button>`)}</div>
 ${S.softwareResult?`<div class="section-gap">${panel('Aplicativos instalados por máquina','list',`<div class="panel-body"><p>${esc(S.softwareResult.target)}</p>${prettyData(S.softwareResult.result)}</div>`)}</div>`:''}`;
};
// A aba WinUtil remota usa o mesmo catálogo nativo, sem executar irm/iex na rede.
winutil=function(){return software();};
const fleetPreviousAct=act;
act=async function(action,data={}){
 if(action==='device-select'){setActiveTarget(data.target);return;}
 if(action==='add-machine')return showModal({title:'Adicionar equipamento',inputs:[{name:'target',label:'IP ou hostname',required:true},{name:'name',label:'Nome amigável'},{name:'device_type',label:'Tipo verificado',type:'select',options:[{value:'unknown',label:'Não identificado'},{value:'computer',label:'Computador'},{value:'printer',label:'Impressora'}]}],actionText:'Cadastrar',onConfirm:async f=>{await request('machines/add',{target:f.target,name:f.name});await request('machines/classify',{target:f.target,device_type:f.device_type});S.selected=f.target;await refresh();}});
 if(action==='discover-local')return busyCall(async()=>{const d=await request('machines/scan',{mode:'local'});await refresh();toast(`${d.found} dispositivos. ${d.note}`);},'');
 if(action==='discover-segments')return showModal({title:'Descobrir segmentos autorizados',desc:'Informe até 8 CIDRs privados de até 256 endereços cada, separados por vírgula. A rotina consulta portas de serviço e ping, sem alterar os equipamentos.',inputs:[{name:'segments',label:'Segmentos',placeholder:'192.168.1.0/24, 192.168.2.0/24',required:true}],actionText:'Descobrir',onConfirm:async f=>{const segments=f.segments.split(',').map(x=>x.trim()).filter(Boolean);const d=await request('machines/scan',{mode:'segments',segments});await refresh();toast(`${d.found} dispositivos. ${d.note}`);}});
 if(action==='software-collapse'){S.softwareCollapsed=new Set(S.softwareCatalog.map(p=>p.category));render();return;}
 if(action==='software-expand'){S.softwareCollapsed.clear();render();return;}
 if(action==='software-toggle'){if(S.softwareCollapsed.has(data.category))S.softwareCollapsed.delete(data.category);else S.softwareCollapsed.add(data.category);render();return;}
 if(action==='software-jobs-refresh')return refreshSoftwareJobs();
 if(action==='software-installed'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{const d=await request('software/installed?target='+encodeURIComponent(m.target));S.softwareResult={target:m.target,result:d.result};render();},'');
 }
 if(['software-install','software-uninstall'].includes(action)){
  const m=selected();if(!m||deviceType(m)!=='computer')return toast('Selecione um computador verificado.',true);
  const packages=[...S.softwareSelected];if(!packages.length||packages.length>20)return toast('Selecione de 1 a 20 aplicativos.',true);
  if(S.softwareSubmitting)return;
  S.softwareSubmitting=true;render();
  try{const d=await request(action==='software-install'?'software/install':'software/uninstall',{target:m.target,packages});toast(d.duplicate?'Esta operação já está na fila.':`Operação enviada para ${m.target}. Acompanhe a fila.`);await refreshSoftwareJobs();}
  catch(e){toast(e.message,true);}finally{S.softwareSubmitting=false;render();}
  return;
 }
 return fleetPreviousAct(action,data);
};
async function refreshSoftwareJobs(){
 try{const jobs=await request('software/jobs');const changed=JSON.stringify(jobs)!==JSON.stringify(S.softwareJobs);S.softwareJobs=jobs;const el=document.querySelector('#software-job-list');if(el&&(changed||!el.querySelector('details')))el.innerHTML=jobsMarkup();}
 catch(e){toast(e.message,true);}
}
main.addEventListener('change',e=>{if(e.target.matches('[data-device-kind]'))busyCall(async()=>{await request('machines/classify',{target:e.target.dataset.deviceKind,device_type:e.target.value});await refresh();},'Tipo atualizado.');});
setInterval(()=>{if(['software','winutil'].includes(S.page))refreshSoftwareJobs();},3000);
const fleetSwitchPage=switchPage;
switchPage=function(page){fleetSwitchPage(page);if(['software','winutil'].includes(page))refreshSoftwareJobs();};
