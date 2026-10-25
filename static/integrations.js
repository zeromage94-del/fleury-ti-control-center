'use strict';
MENUS.push(['integrations','link','Integrações e Zebra']);
S.integrationCatalog=null;
S.adminScripts=[];
S.driverCatalog=null;S.driverInventory=null;S.driverPackage='';S.driverPrinter='';S.printerActionResult=null;
function printerDriverPanel(){
 const m=selected(),inventory=S.driverInventory?.target===m?.target?S.driverInventory:null;
 const catalog=S.driverCatalog,packages=catalog?.packages||[];
 const drivers=inventory?.drivers||[],printers=inventory?.printers||[];
 const eligible=packages.filter(p=>p.reviewed===true&&drivers.some(d=>d.Name.toLowerCase()===p.driver_name.toLowerCase()));
 const chosen=eligible.find(p=>p.id===S.driverPackage),printer=printers.find(p=>p.Name===S.driverPrinter);
 let official='';
 try{const url=new URL(catalog?.official_url||'https://www.zebra.com/us/en/support-downloads/printer-software/printer-drivers.html');if(url.protocol==='https:'&&['zebra.com','www.zebra.com'].includes(url.hostname))official=url.href;}catch{}
 return panel('Zebra • repositório de drivers revisados','download',`<div class="panel-body">
 <p>Catálogo local revisado pela TI para os modelos que ela administra. Os drivers não são baixados ou executados automaticamente. ${official?`<a href="${esc(official)}" target="_blank" rel="noopener noreferrer">Drivers oficiais Zebra</a>`:''}</p>
 <div class="toolbar-group"><button class="btn" data-act="drivers-catalog">Carregar repositório</button><button class="btn" data-act="drivers-installed" ${!m||deviceType(m)!=='computer'?'disabled':''}>Consultar drivers e impressoras do computador</button></div>
 ${catalog?`<p class="hint">${esc(catalog.note||'A troca usa apenas um driver revisado já instalado no computador selecionado.')}</p>${packages.length?`<div class="table-scroll"><table><thead><tr><th>Pacote</th><th>Modelos</th><th>Driver / versão</th><th>Validação local</th></tr></thead><tbody>${packages.map(p=>`<tr><td>${esc(p.title||p.id)}</td><td>${esc((p.models||[]).join(', '))}</td><td>${esc(p.driver_name)}<br>${esc(p.version||'Versão não informada')}</td><td>${p.package_present&&p.verified?'INF local verificado':'Referência revisada para driver já instalado'}</td></tr>`).join('')}</tbody></table></div>`:'<p>Nenhum pacote revisado cadastrado. Cadastre somente drivers oficiais compatíveis com seus modelos.</p>'}`:''}
 ${inventory?`<p><strong>Computador:</strong> ${esc(inventory.target)}</p><p class="hint">A troca altera a fila Windows desta estação. Não corrige cabo, sensor, cabeça de impressão ou mídia. Compare modelo, DPI e linguagem antes da troca.</p>
 <p><label>Impressora Zebra <select class="select" id="driver-printer"><option value="">Selecione a impressora...</option>${printers.map(p=>`<option value="${esc(p.Name)}" ${p.Name===S.driverPrinter?'selected':''}>${esc(p.Name)} · ${esc(p.DriverName)}</option>`).join('')}</select></label></p>
 <p><label>Driver revisado já instalado <select class="select" id="driver-package"><option value="">Selecione o pacote compatível...</option>${eligible.map(p=>`<option value="${esc(p.id)}" ${p.id===S.driverPackage?'selected':''}>${esc(p.title||p.id)} · ${esc(p.driver_name)} · ${esc((p.models||[]).join(', '))}</option>`).join('')}</select></label></p>
 ${!eligible.length?'<p class="hint">Nenhum driver do catálogo foi encontrado entre os instalados. A TI precisa instalar um pacote oficial revisado na estação antes da troca.</p>':''}
 ${!printers.length?'<p class="hint">Nenhuma fila Zebra reconhecida. Confira o nome e o driver no Windows antes de prosseguir.</p>':''}
 <button class="btn danger" data-act="driver-change" ${!chosen||!printer?'disabled':''}>Trocar driver da impressora selecionada</button>
 <details><summary>Drivers instalados consultados</summary>${prettyData(drivers)}</details>`:''}
 ${S.printerActionResult?.target===m?.target?`<div class="section-gap"><div class="note ${S.printerActionResult.ok===false?'red':'blue'}">${esc(S.printerActionResult.message||'Confira o resultado da operação de impressão.')}</div>${prettyData(S.printerActionResult.result)}</div>`:''}
 </div>`);
}
const previousDriverPrinters=printers;
printers=function(){const result=S.printerActionResult?.target===S.selected?S.printerActionResult:null;return previousDriverPrinters()+(result?`<div class="section-gap">${panel('Resultado da manutenção de impressão','list',`<div class="panel-body"><div class="note ${result.ok===false?'red':'blue'}">${esc(result.message||'Confira o resultado da operação de impressão.')}</div>${prettyData(result.result)}</div>`)}</div>`:'');};
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
 `<div class="section-gap">${printerDriverPanel()}</div>`+
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
 if(action==='printer-diagnose'){
  const m=currentMachine();if(!m)return;
  return busyCall(async()=>{
   const d=await request(`printers/diagnose?target=${encodeURIComponent(m.target)}&printer=${encodeURIComponent(data.printer||'')}`);
   S.printerActionResult={target:m.target,ok:d.result.healthy,message:d.result.note,result:d.result};render();
  },'');
 }
 if(action==='drivers-catalog')return busyCall(async()=>{S.driverCatalog=await request('printers/drivers/catalog');S.driverPackage='';render();},'Repositório de drivers carregado.');
 if(action==='drivers-installed'){
  const m=currentMachine();if(!m)return;
  if(deviceType(m)!=='computer')return toast('Selecione o computador Windows que possui a fila da impressora.',true);
  return busyCall(async()=>{
   S.driverInventory=null;S.driverPackage='';S.driverPrinter='';render();
   const [drivers,printers,catalog]=await Promise.all([request('printers/drivers/installed?target='+encodeURIComponent(m.target)),request('admin/printers?target='+encodeURIComponent(m.target)),request('printers/drivers/catalog')]);
   if(S.selected!==m.target)return;
   S.driverCatalog=catalog;
   S.driverInventory={target:m.target,drivers:Array.isArray(drivers.result)?drivers.result:[],printers:(Array.isArray(printers.result)?printers.result:[]).filter(p=>/Zebra|ZDesigner|ZT\d|ZD\d|GK\d|GX\d|GC\d/i.test(`${p.Name} ${p.DriverName}`))};
   render();toast('Drivers e filas Zebra consultados. Selecione o modelo compatível.');
  },'');
 }
 if(action==='driver-change'){
  const m=currentMachine(),inventory=S.driverInventory;
  if(!m||inventory?.target!==m.target)return toast('Consulte os drivers do computador selecionado primeiro.',true);
  const printer=inventory.printers.find(p=>p.Name===S.driverPrinter),pack=S.driverCatalog?.packages.find(p=>p.id===S.driverPackage);
  if(!printer||!pack||pack.reviewed!==true||!inventory.drivers.some(d=>d.Name.toLowerCase()===pack.driver_name.toLowerCase()))return toast('Selecione uma fila Zebra e um driver revisado já instalado.',true);
  return busyCall(async()=>{
   if(S.selected!==m.target||S.driverInventory!==inventory)throw Error('O computador ou a consulta mudou. Consulte novamente.');
   const d=await request('printers/drivers/change',{target:m.target,printer:printer.Name,driver:pack.id});
   S.printerActionResult={target:m.target,...d};S.driverInventory=null;S.driverPackage='';S.driverPrinter='';render();toast(d.message||'Confira o resultado da troca do driver.',d.ok===false);
  },'');
 }
 if(action==='spooler'||action==='clear-print'){
  const m=currentMachine();if(!m)return;
  const printer=data.printer,clearing=action==='clear-print';
  if(clearing&&!printer)return toast('Selecione uma impressora para limpar a fila.',true);
  return busyCall(async()=>{
   const d=await request(clearing?'admin/clear-print':'admin/spooler',{target:m.target,printer});
   S.printerActionResult={target:m.target,...d};render();toast(d.message||'Confira o resultado da manutenção de impressão.',d.ok===false);
   try{const list=await request('admin/printers?target='+encodeURIComponent(m.target));S.printers={target:m.target,data:list.result};render();}catch(e){toast('Operação retornou resultado, mas a nova consulta falhou: '+e.message,true);}
  },'');
 }
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
  return busyCall(async()=>{const d=await request('zebra/print',{printer,label,data:variables});toast(d.result.message);},'');
 }
 if(action==='winutil-launch')return busyCall(async()=>{const d=await request('winutil/launch',{});toast(d.result.message);},'');
 return previousIntegrationAct(action,data);
};
const previousIntegrationWinutil=winutil;
winutil=function(){return previousIntegrationWinutil()+`<div class="section-gap"><button class="btn primary" data-act="winutil-launch">Abrir WinUtil local revisado</button></div>`;};
main.addEventListener('change',e=>{
 if(e.target.id==='driver-printer'){S.driverPrinter=e.target.value;render();}
 if(e.target.id==='driver-package'){S.driverPackage=e.target.value;render();}
});
