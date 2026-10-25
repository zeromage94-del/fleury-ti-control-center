/* Complemento MVP 0.7: ativos, manutenção, incidentes e indicadores */
'use strict';
const CATEGORY_NAMES=['Lentidão','Disco 100%','Impressora Zebra','PINPAD / TEF','Impressão geral','Rede','Sistema Windows','Outros','Não classificado'];
MENUS.splice(4,0,['assets','list','Inventário / Fotos']);
MENUS.splice(5,0,['maintenance','settings','Manutenção TI']);
S.analytics=null;
S.assetDetails=null;
S.assetImages=[];
S.assetTarget=null;
S.diagnostics=null;
S.cleanupPreview=null;
S.restorePoints=null;
S.zplRest=null;
const assetBlobURLs=new Map();
function asText(v) {return esc(v===null||v===undefined?'—':v);}
function percentText(v) {return v===null||v===undefined?'Sem dados':`${Number(v).toLocaleString('pt-BR')}%`;}
function durationText(v) {return v===null||v===undefined?'Sem dados':`${Number(v).toLocaleString('pt-BR')} h`;}
function machinePicker(id='new-target-select') {return `<select class="select" id="${id}" style="min-width:260px;max-width:440px"><option value="">Selecione o computador...</option>${S.machines.map(m=>`<option value="${esc(m.target)}" ${m.target===S.selected?'selected':''}>${esc(m.name)} — ${esc(m.target)}</option>`).join('')}</select>`;}
function categoryOptions(v) {return CATEGORY_NAMES.map(c=>`<option value="${esc(c)}" ${v===c?'selected':''}>${esc(c)}</option>`).join('');}
const previousRender=render;
render=function(){
 sidebar();
 const fns={dashboard,machines,remote,printers,tickets,scripts,logs,settings,assets,maintenancePage,commands,software};
 const page=S.page==='maintenance'?'maintenancePage':S.page;
 main.innerHTML=(fns[page]||dashboard)()+`<footer class="page-credit">Criado por Ana Tazinaffo</footer>`;
 document.querySelector('#user-name').textContent=S.stats.username||'Técnico de TI';
 document.querySelector('#avatar').textContent=(S.stats.username||'T').trim().slice(0,1).toUpperCase();
 document.querySelector('#search-icon').innerHTML=ico('search');
};
const previousRefresh=refresh;
refresh=async function(quiet=false) {
 if (quiet && document.activeElement?.closest?.('#asset-form')) return;
 await previousRefresh(quiet);
 try {S.analytics=await request('analytics'); render();}
 catch(e) {if(!quiet) toast('Indicadores indisponíveis: '+e.message,true);}
};
const previousActions=actions;
actions=function(){
 const base=previousActions().replace('Execução direta','Sem solicitação no PC remoto');
 return base.replace('</div></section>',
   actionButton('settings','Manutenção Windows','Disco 100% e limpeza','maintenance-page')+
   actionButton('printer','Diagnóstico Zebra','Impressão de etiquetas','maintenance-page')+
   actionButton('shield','Verificar PINPAD','Portas e serviços TEF','maintenance-page')+'</div></section>');
};
const previousDashboard=dashboard;
dashboard=function(){
 const x=S.analytics||{};
 const cards=[
  ['check','Resolvidos',x.resolved??0,percentText(x.resolution_pct)+' da fila total'],
  ['ticket','Pendentes',x.pending??0,'Abertos, em andamento e pendentes'],
  ['clock','Tempo médio de resolução',durationText(x.avg_resolution_hours),`${x.avg_resolution_count||0} chamados com datas válidas`],
  ['shield','SLA cumprido',percentText(x.sla_pct),`${x.sla_met||0} dentro de ${x.sla_evaluated||0} avaliados`]
 ];
 const metricsBlock=`<div class="metrics analytics-metrics">${cards.map(([ic,k,v,s])=>`<div class="metric"><div class="metric-icon">${ico(ic)}</div><div><div class="metric-title">${esc(k)}</div><div class="metric-number">${esc(v)}</div><div class="metric-sub">${esc(s)}</div></div></div>`).join('')}</div>`;
 const ranking=x.ranking||[];
 const rankBody=ranking.length?`<div class="panel-body">${ranking.map((r,i)=>`<div class="rank-entry"><div class="rank-line"><span><strong>${i+1}.</strong> ${esc(r.category)}</span><span>${r.count} • ${percentText(r.percentage)}</span></div><div class="rank-track"><div style="width:${Math.max(0,Math.min(100,r.percentage))}%" class="rank-fill"></div></div></div>`).join('')}<p class="hint">Percentuais sobre ${x.total||0} chamado(s). Títulos importados podem receber categoria sugerida automaticamente; revise a classificação na fila.</p></div>`:empty('Importe chamados ou cadastre ocorrências para visualizar o ranking.','ticket');
 const blocks=`${metricsBlock}<div class="analytics-grid">${panel('Ranking de problemas recorrentes','alert',rankBody)}${panel('Resumo do SLA','clock',`<div class="panel-body"><div class="kv-row"><span class="kv-label">Chamados concluídos com SLA avaliável</span><strong>${x.sla_evaluated??0}</strong></div><div class="kv-row"><span class="kv-label">Dentro do prazo</span><strong>${x.sla_met??0}</strong></div><div class="kv-row"><span class="kv-label">Fora do prazo</span><strong>${x.sla_missed??0}</strong></div><div class="kv-row"><span class="kv-label">Abertos já vencidos</span><strong>${x.sla_open_overdue??0}</strong></div><div class="note blue">SLA sem prazo informado = não avaliado. Sem datas de conclusão = fora da média de resolução.</div></div>`)}</div>`;
 const original=previousDashboard();
 return original.includes('<div class="dashboard-grid">')?original.replace('<div class="dashboard-grid">',blocks+'<div class="dashboard-grid">'):original+blocks;
};
const previousTickets=tickets;
tickets=function(){
 let original=previousTickets();
 const categoriesPanel=panel('Classificação dos incidentes e SLA','ticket',S.tickets.length?`<div class="table-scroll"><table><thead><tr><th>Atendimento</th><th>Categoria</th><th>Abertura</th><th>Resolução</th><th>Prazo SLA</th></tr></thead><tbody>${S.tickets.slice(0,120).map(t=>`<tr><td><strong>#${esc(t.external_id||t.id)}</strong><br><small>${esc(t.title)}</small></td><td><select class="select category-select" data-id="${t.id}">${categoryOptions(t.category)}</select></td><td>${dstr(t.created_at)}</td><td>${dstr(t.resolved_at)}</td><td>${dstr(t.sla_due_at)}</td></tr>`).join('')}</tbody></table></div>`:empty('Sem chamados para classificar.','ticket'),`<button class="btn sm" data-act="zammad-sync">${ico('refresh')} Sincronizar Zammad</button>`);
 return original.replace("<div class=\"section-gap note blue\">",`<div class="section-gap">${categoriesPanel}</div><div class="section-gap note blue">`)
 .replace('A fila desta versão é local. A sincronização automática depende',S.stats.zammad_configured?'Conector Zammad disponível quando a instância e o token estiverem configurados. A sincronização é somente leitura. As demais integrações dependem':'A fila desta versão é local. A sincronização automática depende');
};
function assets(){
 const target=S.selected;
 const loaded=target && S.assetTarget===target;
 const d=loaded?S.assetDetails:null;
 const imgs=loaded?S.assetImages:[];
 const fields=[['asset_tag','Número de patrimônio'],['location','Unidade / localização'],['department','Setor'],['owner','Responsável pelo ativo']];
 const details=`<div class="panel-body"><div class="toolbar-group">${machinePicker('asset-picker')}<button class="btn primary" data-act="asset-load">${ico('refresh')} Carregar ficha</button><button class="btn" data-act="inventory">${ico('monitor')} Coletar hardware</button></div>${loaded?`<form id="asset-form"><div class="asset-form-grid">${fields.map(([key,label])=>`<label><span class="field-label">${label}</span><input class="field" name="${key}" maxlength="120" value="${esc(d?.[key]||'')}" /></label>`).join('')}</div><label class="field-label" for="asset-notes">Observações (sem senhas ou dados sensíveis)</label><textarea class="asset-notes" id="asset-notes" name="notes" maxlength="1200" rows="3">${esc(d?.notes||'')}</textarea><div class="toolbar-group" style="margin-top:12px"><button class="btn primary" type="submit">${ico('check')} Salvar patrimônio</button><span class="hint">Os dados ficam no banco local desta instalação.</span></div></form>`:'<div class="hint">Selecione uma máquina e clique em Carregar ficha para editar o inventário.</div>'}</div>`;
 const gallery=`<div class="panel-body"><div class="toolbar-group"><button class="btn primary" data-act="asset-photo" ${!loaded?'disabled':''}>${ico('upload')} Anexar foto</button><span class="hint">PNG, JPEG ou WebP; máximo 1 MB cada, até 8 imagens por máquina.</span><input id="asset-file" type="file" accept="image/png,image/jpeg,image/webp" hidden /></div>${imgs.length?`<div class="asset-gallery">${imgs.map(x=>`<div class="asset-image-card"><img src="${assetBlobURLs.get(x.id)||''}" alt="Foto de patrimônio anexada" loading="lazy"><div class="asset-image-caption" title="${esc(x.original_name)}">${esc(x.original_name)} <button class="btn sm danger" data-act="asset-delete" data-id="${x.id}">Excluir</button></div></div>`).join('')}</div>`:empty('Nenhuma imagem cadastrada para este patrimônio.','info')}</div>`;
 return pageHead('Inventário de ativos e imagens','Controle de patrimônio com foto, localização e responsáveis; consulta de hardware quando disponível.')+
 `<div class="workspace"><div class="stack">${panel('Ficha do equipamento','list',details)}<div class="section-gap">${panel('Fotografias anexadas','upload',gallery)}</div></div>${panel('Máquina em foco','monitor',machineInfo())}</div><div class="footer-note">Fotos e dados são guardados em data/ no computador que executa o aplicativo. Obtenha aprovação da empresa antes de inserir fotos de instalações ou informações pessoais.</div>`;
}
function prettyData(v){return `<pre class="diagnostic-output">${esc(JSON.stringify(v,null,2))}</pre>`;}
function maintenancePage(){
 const m=selected();
 const diag = S.diagnostics?.target===m?.target?S.diagnostics:null;
 const diagnosticPanel=diag?panel(diag.label,'list',`<div class="panel-body">${prettyData(diag.result)}</div>`):panel('Resultado do diagnóstico','list',empty('Execute uma consulta para visualizar as informações técnicas.','info'));
 const cleanup=S.cleanupPreview?.target===m?.target?S.cleanupPreview:null;
 const restoration=S.restorePoints?.target===m?.target?S.restorePoints:null;
 const points=restoration?.result?.Pontos||[];
 const zplList=S.zplRest?.Impressoras||[];
 const zplRestPanel=panel('Integração ZPL REST (consulta)','printer',`<div class="panel-body">
 <p class="hint">Conector opcional de consulta ao servidor zpl-rest. Exibe impressoras cadastradas, sem enviar etiquetas, jobs ou dados de laboratório. O serviço deve ser homologado e protegido com HTTPS ou executado localmente.</p>
 <div class="tool-buttons"><button class="btn" data-act="zpl-rest-check">${ico('refresh')} Consultar servidor ZPL REST</button></div>
 ${S.zplRest?`<div class="note blue">${S.zplRest.Quantidade} impressora(s) cadastrada(s) no zpl-rest.</div>${zplList.length?`<div class="table-scroll"><table><thead><tr><th>Nome</th><th>Endereço</th><th>Densidade</th></tr></thead><tbody>${zplList.map(x=>`<tr><td>${esc(x.Nome)}</td><td>${esc(x.Endereco)}</td><td>${esc(x.Densidade)}</td></tr>`).join('')}</tbody></table></div>`:empty('Nenhuma impressora retornada.','printer')}`:'<p class="hint">Defina FLEURY_ZPL_REST_URL no ambiente para habilitar a consulta.</p>'}
 <div class="note red">Uso em laboratório: não carregue etiquetas reais de pacientes no preview externo Labelary, nem instale zpl-rest na rede sem avaliação de segurança. A consulta não faz calibração ou reset de Zebra.</div>
 </div>`);
 const restorePanel=panel('Pontos de restauração do Windows','history',`<div class="panel-body">
 <p class="hint">Crie uma recuperação antes de alterações no Windows; consulte os pontos existentes. Exclua individualmente apenas os antigos (14+ dias), preservando o mais recente e exigindo outro ponto com menos de 7 dias.</p>
 <div class="tool-buttons"><button class="btn primary" data-act="restore-create">${ico('check')} Criar ponto de restauração</button><button class="btn" data-act="restore-list">${ico('refresh')} Listar / atualizar pontos</button></div>
 ${restoration?`<div class="note blue">${points.length} ponto(s) listado(s) nesta máquina.</div>${points.length?`<div class="table-scroll"><table><thead><tr><th>Nº</th><th>Data</th><th>Descrição</th><th>Idade</th><th>Ação</th></tr></thead><tbody>${points.map(x=>`<tr><td>${esc(x.Numero)}</td><td>${esc(x.CriadoEm)}</td><td>${esc(x.Descricao)}</td><td>${esc(x.IdadeDias)} dias</td><td>${x.MaisRecente?'Protegido':Number(x.IdadeDias)>=14?`<button class="btn sm danger" data-act="restore-delete" data-sequence="${esc(x.Numero)}">Excluir antigo</button>`:'Preservado'}</td></tr>`).join('')}</tbody></table></div>`:empty('Sem pontos cadastrados ou disponíveis. Verifique a Proteção do Sistema do Windows.','info')}`:'<p class="hint">Selecione uma máquina e clique em Listar / atualizar pontos.</p>'}
 <div class="note">Não altera a Proteção do Sistema nem a retenção existente. Não é backup de documentos, imagens nem sistemas laboratoriais. Funções sujeitas às políticas da TI.</div>
 </div>`);
 return pageHead('Manutenção e diagnósticos','Windows 10/11 • temporários de todos os perfis • Zebra • PINPAD / TEF • disco em 100%')+
 `<div class="panel maintenance-select"><div class="panel-body toolbar-group">${machinePicker('maintenance-picker')}<button class="btn" data-act="verify">${ico('wifi')} Ping</button><span class="hint">Exige gestão autorizada e WinRM no computador selecionado.</span></div></div>
 <div class="maintenance-grid">
 ${panel('Desempenho e HD em 100%','monitor',`<div class="panel-body"><p class="hint">Mede I/O, verifica espaço, tipo/saúde do disco, eventos e serviços. Se houver erros de armazenamento, priorize backup e manutenção física.</p><div class="tool-buttons"><button class="btn primary" data-act="diagnostic" data-type="disk-100">Diagnosticar disco 100%</button><button class="btn" data-act="diagnostic" data-type="performance">CPU, RAM e perfis</button><button class="btn" data-act="disk-tool" data-tool="dism-check">DISM CheckHealth</button><button class="btn" data-act="disk-tool" data-tool="dism-repair">DISM RestoreHealth</button><button class="btn" data-act="disk-tool" data-tool="chkdsk-scan">CHKDSK /scan</button><button class="btn" data-act="disk-tool" data-tool="sfc-scan">SFC /scannow</button></div><hr class="thin-divider"/><h3>Testes pontuais de serviços</h3><div class="tool-buttons"><button class="btn" data-act="disk-service" data-service="SysMain">Reiniciar SysMain</button><button class="btn" data-act="disk-service" data-service="WSearch">Reiniciar Windows Search</button></div><p class="hint">Os serviços não são desabilitados de modo permanente.</p></div>`)}
 ${panel('Limpeza segura de temporários','refresh',`<div class="panel-body"><p class="hint">Limpeza direta, sem simulação, dos arquivos .tmp/.temp com 7 dias ou mais em C:\\Windows\\Temp e TEMP de todos os perfis. Não exclui imagens, documentos, logs, programas ou dados de etiquetas/TEF. Arquivos em uso são ignorados.</p><div class="toolbar-group"><label><span class="field-label">Arquivos com pelo menos</span><select id="cleanup-days" class="select">${[7,14,30,60,90].map(d=>`<option value="${d}" ${d===S.quickDays?'selected':''}>${d} dias</option>`).join('')}</select></label><button class="btn primary" data-act="quick-optimize">Otimização rápida</button><button class="btn" data-act="cleanup-run">Limpar temporários agora</button></div><div class="note">Execução direta e registro de auditoria. Nenhuma mudança em antivírus, política de segurança ou inicialização. Nenhuma limpeza garante corrigir um HD em 100%.</div></div>`)}
 ${panel('Impressoras Zebra','printer',`<div class="panel-body"><p class="hint">Identifica modelo pelo driver/nome, porta/IP, estado da fila, Spooler e teste TCP da porta de impressão. A calibração da etiqueta depende do modelo, mídia e driver.</p><label><span class="field-label">Nome exato da impressora instalada</span><input class="field" id="zebra-name" placeholder="Ex.: ZDesigner ZD421-203dpi ZPL"></label><div class="tool-buttons"><button class="btn primary" data-act="diagnostic" data-type="zebra">Diagnóstico Zebra</button><button class="btn" data-act="printers-list">Listar impressoras</button><button class="btn" data-act="printer-page">Abrir filas de impressão</button></div></div>`)}
 ${panel('PINPAD / TEF','shield',`<div class="panel-body"><p class="hint">Consulta portas COM, dispositivos USB/serial e serviços TEF conhecidos. Não acessa dados de cartão, transações nem chaves de pagamento.</p><div class="tool-buttons"><button class="btn primary" data-act="diagnostic" data-type="pinpad">Diagnóstico PINPAD</button></div><div class="thin-divider"></div><label><span class="field-label">Nome técnico do serviço TEF encontrado</span><input class="field" id="tef-service-name" placeholder="Serviço validado no diagnóstico"></label><div class="tool-buttons"><button class="btn danger" data-act="tef-service">Reiniciar middleware TEF</button></div><div class="note red">Nunca reinicie o TEF durante uma transação. Verifique com o operador e fornecedor antes de agir.</div></div>`)}
 </div><div class="section-gap">${zplRestPanel}</div><div class="section-gap">${restorePanel}</div><div class="section-gap">${diagnosticPanel}</div>`;
}
const oldAct=act;
async function loadAsset(target){
 if(!target) throw Error('Selecione uma máquina primeiro.');
 const [d,images]=await Promise.all([request('assets/detail?target='+encodeURIComponent(target)),request('assets/images?target='+encodeURIComponent(target))]);
 S.assetTarget=target;S.assetDetails=d;S.assetImages=images;
 await Promise.all(images.map(async (i)=>{
  if(assetBlobURLs.has(i.id))return;
  const r=await fetch('/api/assets/image?id='+encodeURIComponent(i.id),{headers:{'X-Fleury-Token':API_TOKEN}});
  if(r.ok)assetBlobURLs.set(i.id,URL.createObjectURL(await r.blob()));
 }));
 render();
}
async function diagnosticsCall(type,target){
 let url='diagnostics/'+type+'?target='+encodeURIComponent(target);
 if(type==='zebra'){
  const printer=document.querySelector('#zebra-name')?.value?.trim();
  if(!printer) throw Error('Informe o nome exato da impressora Zebra.');
  url+='&printer='+encodeURIComponent(printer);
 }
 const d=await request(url);
 S.diagnostics={target,label:({'disk-100':'Diagnóstico HD / SSD 100%','performance':'Diagnóstico de desempenho','zebra':'Diagnóstico Zebra','pinpad':'Diagnóstico PINPAD / TEF'})[type],result:d.result};
 render();
 toast('Diagnóstico concluído.');
}
act=async function(action,data={}){
 if(action==='asset-page')return switchPage('assets');
 if(action==='maintenance-page')return switchPage('maintenance');
 if(action==='asset-load'){const m=currentMachine();if(!m)return;return busyCall(()=>loadAsset(m.target),'Ficha carregada.');}
 if(action==='asset-photo'){const input=document.querySelector('#asset-file');if(input){input.value='';input.click();}return;}
 if(action==='asset-delete'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{
   await request('assets/delete-image',{target:m.target,id:Number(data.id)});
   const url=assetBlobURLs.get(Number(data.id));if(url)URL.revokeObjectURL(url);
   assetBlobURLs.delete(Number(data.id));await loadAsset(m.target);toast('Imagem excluída.');
  },'');
 }
 if(action==='zpl-rest-check'){
  return busyCall(async()=>{const d=await request('diagnostics/zpl-rest');S.zplRest=d.result;render();toast('Conector ZPL REST consultado.');},'');
 }
 if(action==='restore-list'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{const d=await request('maintenance/restore-points?target='+encodeURIComponent(m.target));
   S.restorePoints={target:m.target,result:d.result};render();toast('Lista de pontos atualizada.');},'');
 }
 if(action==='restore-create'){
  const m=currentMachine();if(!m)return;
  const description=document.querySelector('#restore-description')?.value.trim()||'Fleury TI - antes da manutenção';
  return busyCall(async()=>{
   const d=await request('maintenance/restore-create',{target:m.target,description});
   S.restorePoints=null;S.diagnostics={target:m.target,label:'Ponto criado',result:d.result};
   const list=await request('maintenance/restore-points?target='+encodeURIComponent(m.target));
   S.restorePoints={target:m.target,result:list.result};render();toast('Ponto de restauração criado.');
  },'');
 }
 if(action==='restore-delete'){
  const m=currentMachine();if(!m)return;
  const n=Number(data.sequence);
  const point=S.restorePoints?.target===m.target?S.restorePoints.result?.Pontos?.find(x=>Number(x.Numero)===n):null;
  if(!point||point.MaisRecente||Number(point.IdadeDias)<14)return toast('Ponto não elegível. Atualize a lista.',true);
  return busyCall(async()=>{
   const d=await request('maintenance/restore-delete',{target:m.target,sequence:n});
   S.diagnostics={target:m.target,label:'Ponto excluído',result:d.result};S.restorePoints=null;
   const list=await request('maintenance/restore-points?target='+encodeURIComponent(m.target));
   S.restorePoints={target:m.target,result:list.result};render();toast('Ponto selecionado removido.');
  },'');
 }
 if(action==='zammad-sync')return busyCall(async()=>{const d=await request('tickets/zammad-sync',{});await refresh();toast(`${d.created} novos, ${d.updated} atualizados do Zammad.${d.possibly_truncated?' Limite de 300 atingido; podem existir outros chamados.':''}`);},'');
 if(action==='diagnostic'){
  const m=currentMachine();if(!m)return;
  return busyCall(()=>diagnosticsCall(data.type,m.target),'');
 }
 if(action==='cleanup-run'||action==='quick-optimize'){
  const m=currentMachine();if(!m)return;
  const days=Number(document.querySelector('#quick-cleanup-days')?.value||document.querySelector('#cleanup-days')?.value||S.quickDays||14);S.quickDays=days;
  const quick=action==='quick-optimize';
  return busyCall(async()=>{
   const d=await request(quick?'maintenance/quick-optimize':'maintenance/cleanup',{target:m.target,days});
   S.diagnostics={target:m.target,label:quick?'Resultado da otimização rápida':'Resultado da limpeza de temporários',result:d.result};
   render();toast(d.message||'Confira o resultado da limpeza.',d.ok===false);
  },'');
 }
 if(action==='disk-service'){
  const m=currentMachine();if(!m)return;
  const service=data.service;
  return busyCall(async()=>{
   const d=await request('maintenance/disk-service',{target:m.target,service});
   S.diagnostics={target:m.target,label:'Teste de serviço '+service,result:d.result};render();toast('Operação concluída.');
  },'');
 }
 if(action==='disk-tool'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{
   const d=await request('maintenance/disk-tool',{target:m.target,tool:data.tool});
   S.diagnostics={target:m.target,label:'Resultado '+data.tool,result:d.result};render();toast(d.ok?'Verificação concluída.':'A ferramenta reportou falha. Consulte o resultado.',!d.ok);
  },'');
 }
 if(action==='tef-service'){
  const m=currentMachine();if(!m)return;
  const service=document.querySelector('#tef-service-name')?.value?.trim();
  if(!service)return toast('Informe o serviço identificado no diagnóstico, sem adivinhar o nome.',true);
  return busyCall(async()=>{
   const d=await request('maintenance/tef-restart',{target:m.target,service});
   S.diagnostics={target:m.target,label:'Resultado do middleware de pagamento',result:d.result};render();toast('Serviço reiniciado; validar a conexão do PINPAD.');
  },'');
 }
 return oldAct(action,data);
};
main.addEventListener('change',e=>{
 if(['asset-picker','maintenance-picker'].includes(e.target.id)){
  S.selected=e.target.value||null;S.inventory=null;S.diagnostics=null;S.cleanupPreview=null;S.restorePoints=null;render();
 }
 if(e.target.classList.contains('category-select')){
  const ident=Number(e.target.dataset.id),category=e.target.value;
  busyCall(async()=>{await request('tickets/category',{id:ident,category});await refresh();toast('Categoria atualizada.');},'');
 }
 if(e.target.id==='asset-file'){
  const file=e.target.files?.[0];if(!file)return;
  const m=currentMachine();if(!m)return;
  if(file.size>1024*1024){toast('Máximo de 1 MB por imagem.',true);return;}
  busyCall(async()=>{
   const raw=await new Promise((resolve,reject)=>{const fr=new FileReader();fr.onload=()=>resolve(fr.result);fr.onerror=()=>reject(Error('Não foi possível ler imagem'));fr.readAsDataURL(file);});
   const base=String(raw).split(',')[1];
   await request('assets/upload',{target:m.target,name:file.name,data:base});
   await loadAsset(m.target);toast('Foto anexada.');
  },'');
 }
});
main.addEventListener('submit',e=>{
 if(e.target.id!=='asset-form')return;
 e.preventDefault();const target=S.selected;
 const data=Object.fromEntries(new FormData(e.target).entries());
 busyCall(async()=>{await request('assets/update',{target,...data});await loadAsset(target);toast('Inventário atualizado.');},'');
});
const priorModal=showModal;
showModal=function(args){
 if(args?.title==='Novo atendimento') {
  args.inputs=[...args.inputs,{name:'category',label:'Categoria principal',type:'select',options:[{value:'',label:'Sugestão automática pelo título'},...CATEGORY_NAMES.map(c=>({value:c,label:c}))]},{name:'sla_hours',label:'Prazo contratual de SLA (horas; em branco = sem dado)',placeholder:'Ex.: 8'}];
 }
 return priorModal(args);
};
// O primeiro refresh do módulo básico pode ocorrer antes deste complemento carregar.
refresh(true);

const previousSettings=settings;
settings=function(){return previousSettings().replace('MVP 0.1','MVP 0.7').replace('Para sincronização automática via API, será necessário configurar um conector específico do software de chamados utilizado.', 'Zammad: configure HTTPS e token de API para sincronização somente leitura. Outras plataformas exigem integração específica.');};


/* v0.6: ações rápidas diretamente ao selecionar uma máquina da rede */
S.quickDays=14;
const previousMachines=machines;
function quickBtn(icon,label,action,desc='',attrs='') {
 return `<button class="quick-command" data-act="${action}" ${attrs} title="${esc(desc||label)}">
  <span class="quick-command-icon">${ico(icon)}</span><span><strong>${esc(label)}</strong>${desc?`<small>${esc(desc)}</small>`:''}</span></button>`;
}
function quickPanel() {
 const m=selected(), target=m?.target||null;
 const diag=S.diagnostics?.target===target?S.diagnostics:null;
 const points=S.restorePoints?.target===target?S.restorePoints.result?.Pontos||[]:[];
 return `<div class="quick-wrap"><div class="quick-target"><label class="field-label" for="quick-machine-picker">Máquina para aplicar o comando</label>
 ${machinePicker('quick-machine-picker')}<small class="hint">A seleção é individual. Todas as ações exigem permissões já concedidas e são auditadas.</small></div>
 ${!m?'<div class="empty">Selecione uma máquina na tabela ou na caixa acima para habilitar os comandos.</div>':`
 <div class="quick-subtitle">${ico('monitor')} ${esc(m.name)} <span class="muted">· ${esc(m.target)}</span></div>
 <h3 class="quick-group-title">Diagnóstico</h3><div class="quick-grid">
 ${quickBtn('wifi','Ping','verify','Conectividade ICMP')}
 ${quickBtn('list','Inventário','inventory','Hardware e Windows')}
 ${quickBtn('monitor','Disco em 100%','diagnostic','I/O, SMART e alertas','data-type="disk-100"')}
 ${quickBtn('list','HD 100% orientado','guided-disk','Causas e recomendações')}
 ${quickBtn('refresh','CPU e memória','diagnostic','Performance e perfis','data-type="performance"')}
 ${quickBtn('wifi','Rede / DNS','quick-read','Interfaces e servidores DNS','data-type="network"')}
 ${quickBtn('settings','Serviços','quick-read','Estado e inicialização','data-type="services"')}
 ${quickBtn('calendar','Atualizações','quick-read','Hotfix e reinício pendente','data-type="updates"')}
 ${quickBtn('shield','PINPAD / TEF','diagnostic','Portas e serviços','data-type="pinpad"')}
 </div>
 <h3 class="quick-group-title">Correções controladas</h3><div class="quick-grid">
 ${quickBtn('check','Criar restauração','restore-create','Antes de alterações no Windows')}
 ${quickBtn('clock','Pontos existentes','restore-list','Consultar e excluir antigo')}
 ${quickBtn('refresh','DISM CheckHealth','disk-tool','Verificar integridade','data-tool="dism-check"')}
 ${quickBtn('settings','DISM RestoreHealth','disk-tool','Reparar componentes','data-tool="dism-repair"')}
 ${quickBtn('shield','SFC /scannow','disk-tool','Reparar arquivos de sistema','data-tool="sfc-scan"')}
 ${quickBtn('monitor','CHKDSK /scan','disk-tool','Verificar volume','data-tool="chkdsk-scan"')}
 ${quickBtn('refresh','Reiniciar SysMain','disk-service','Teste sem desativar serviço','data-service="SysMain"')}
 ${quickBtn('search','Reiniciar Search','disk-service','Teste sem desativar serviço','data-service="WSearch"')}
 ${quickBtn('wifi','Limpar cache DNS','quick-flush-dns','Sem alterar configurações')}
 ${quickBtn('printer','Reiniciar Spooler','spooler','Interrompe filas de impressão')}
 </div>
 <h3 class="quick-group-title">Otimização expressa · Todos os usuários</h3>
 <div class="quick-cleanup"><label class="field-label" for="quick-cleanup-days">Idade mínima em TEMP</label><select id="quick-cleanup-days" class="select">${[7,14,30,60,90].map(d=>`<option value="${d}" ${d===S.quickDays?'selected':''}>${d} dias</option>`).join('')}</select>
 <div class="quick-grid">${quickBtn('bolt','Otimizar agora','quick-optimize','Limpeza direta .tmp/.temp')}
 ${quickBtn('refresh','Limpar temporários','cleanup-run','Todos os perfis; sem simular')}</div>
 <p class="hint">Sem remoção de programas, imagens, documentos ou logs. Nenhuma alteração de antivírus, GPO, registro ou serviços. O clique executa a ação.</p></div>
 <h3 class="quick-group-title">Software homologado</h3><div class="quick-grid">
 ${quickBtn('download','Instalar software','software-page','Catálogo WinGet permitido')}
 ${quickBtn('bolt','Comandos rápidos','commands-page','Todas as ferramentas')}
 </div>
 <h3 class="quick-group-title">Suporte e impressoras</h3><div class="quick-grid">
 ${quickBtn('printer','Listar impressoras','printers-list','Ver driver e fila')}
 ${quickBtn('printer','Diagnóstico Zebra','maintenance-page','Configuração e porta')}
 ${quickBtn('shield','PINPAD avançado','maintenance-page','Middleware TEF')}
 ${quickBtn('monitor','Conectar RDP','rdp','Autenticação Windows')}
 ${quickBtn('terminal','PowerShell remoto','terminal','WinRM autorizado')}
 ${quickBtn('power','Reiniciar PC','restart','Execução ao clicar')}
 </div>
 ${points.length?`<h3 class="quick-group-title">Pontos existentes (${points.length})</h3><div class="restore-quick-list">${points.map(p=>`<div class="restore-quick"><div><strong>#${asText(p.Numero)}</strong> ${asText(p.Descricao)} <small class="muted">${asText(p.CriadoEm)}</small></div>${!p.MaisRecente&&Number(p.IdadeDias)>=14?`<button class="btn sm danger" data-act="restore-delete" data-sequence="${esc(p.Numero)}">Excluir antigo</button>`:'<span class="chip green">Preservado</span>'}</div>`).join('')}</div>`:''}
 ${diag?`<h3 class="quick-group-title">${esc(diag.label)}</h3><div class="quick-output">${prettyData(diag.result)}</div>`:''}
 `}</div>`;
}
function machines(){
 return pageHead('Máquinas da rede','Clique no equipamento para usar os comandos do painel lateral, ou escolha pela caixa de seleção.')+
 `${selectedTargetBar('machine-target-main')}<div class="machines-layout"><div class="stack">${panel('Máquinas da rede','monitor',`<div class="panel-body"><div class="toolbar"><input class="field compact-field" id="table-search" placeholder="Buscar máquina ou IP" value="${esc(S.filter)}"><div class="toolbar-group"><button class="btn" data-act="neighbors">${ico('wifi')} Descobrir</button><button class="btn" data-act="scan-subnet">${ico('search')} Varredura /24</button><button class="btn primary" data-act="add-machine">${ico('plus')} Cadastrar</button></div></div>${machineTable()}</div>`)}
 <div class="note blue">A seleção não dispara comandos automaticamente. A máquina deve ter WinRM configurado pela TI, e as ações dependem de credenciais e políticas corporativas existentes.</div></div>
 <div class="stack"><div class="quick-pinned">${panel('Acesso rápido · Máquina selecionada','bolt',quickPanel())}</div>${panel('Detalhes da máquina','monitor',machineInfo())}</div></div>`;
}
// Aciona a mesma seleção da lista de máquinas e da caixa de ferramentas.
main.addEventListener('change',e=>{
 if(e.target.id==='quick-machine-picker'){
  S.selected=e.target.value||null;S.inventory=null;S.diagnostics=null;S.cleanupPreview=null;S.restorePoints=null;S.printers=null;render();
 }
 if(e.target.id==='quick-cleanup-days')S.quickDays=Number(e.target.value)||14;
});
const previousQuickAct=act;
act=async function(action,data={}){
 if(action==='quick-read'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{
   const d=await request('diagnostics/'+data.type+'?target='+encodeURIComponent(m.target));
   S.diagnostics={target:m.target,label:({updates:'Atualizações do Windows',network:'Diagnóstico de rede e DNS',services:'Serviços do Windows'})[data.type]||'Diagnóstico',result:d.result};
   render();toast('Consulta concluída.');
  },'');
 }
 if(action==='quick-flush-dns'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{
   const d=await request('maintenance/flush-dns',{target:m.target});
   S.diagnostics={target:m.target,label:'Limpeza do cache DNS',result:d.result};render();toast('Cache DNS atualizado.');
  },'');
 }
 return previousQuickAct(action,data);
};
// Seletor presente também no cartão Ações rápidas do dashboard.
const previousDashboardActions=actions;
actions=function(){
 let html=previousDashboardActions();
 const selector=`<div class="quick-dashboard-target"><label class="field-label" for="quick-machine-picker">Aplicar ações rápidas na máquina</label>${machinePicker('quick-machine-picker')}<button class="btn sm" data-act="machine-page">${ico('chevron')} Abrir todas as ferramentas</button></div>`;
 return html.replace('<div class="action-grid">',selector+'<div class="action-grid">');
};
