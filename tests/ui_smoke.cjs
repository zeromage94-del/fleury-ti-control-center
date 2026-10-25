/* Carrega a interface como scripts clássicos; sem rede, administração ou DOM real. */
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assert=require('node:assert/strict');
const nodes=new Map();
function node(){return {innerHTML:'',textContent:'',value:'',children:[],style:{},dataset:{},
 addEventListener(){},appendChild(){},append(){},contains(){return false;},closest(){return null;},
 querySelector(){return node();},querySelectorAll(){return [];},classList:{add(){},remove(){},toggle(){}},
 focus(){},setSelectionRange(){},remove(){}};}
const document={querySelector(s){if(!nodes.has(s))nodes.set(s,node());return nodes.get(s);},
 createElement:node,body:node(),activeElement:null,addEventListener(){}};
const context=vm.createContext({document,window:{__APP_TOKEN__:'test',addEventListener(){},innerWidth:1280,innerHeight:900},
 console,URL,Blob,setTimeout(){},setInterval(){},navigator:{},fetch(){throw Error('Rede proibida no smoke test');}});
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'static/index.html'),'utf8');
const scripts=[...html.matchAll(/src="\/static\/([^\"]+\.js)"/g)].map(m=>m[1]);
for(const file of scripts)vm.runInContext(fs.readFileSync(path.join(root,'static',file),'utf8'),context,{filename:file});
vm.runInContext(`
 S.machines=[{target:'PC-TESTE',name:'Teste',status:'Online'}]; S.selected='PC-TESTE';
 S.stats={username:'Teste',machines:1};
 for(const [page] of MENUS){S.page=page;render();if(!main.innerHTML)throw Error('Página vazia: '+page);}
`,context);
const texts=scripts.map(f=>fs.readFileSync(path.join(root,'static',f),'utf8')).join('\n');
const actions=new Set([...texts.matchAll(/data-act="([a-z][a-z0-9-]*)"/g)].map(m=>m[1]));
for(const action of actions){assert(texts.includes(`action==='${action}'`) ||
 texts.includes(`'${action}'`),`Ação sem referência no dispatcher: ${action}`);}
assert(vm.runInContext("MENUS.some(x=>x[0]==='integrations')",context));
vm.runInContext(`S.integrationCatalog={printers:[{id:'p1',name:'Teste',address:'127.0.0.1:9100'}],labels:[{id:'l1',name:'Teste'}]};S.page='integrations';render();`,context);
assert(nodes.get('#main').innerHTML.includes('zebra-print'));
console.log(`${scripts.length} scripts carregados; todas as páginas renderizadas; ${actions.size} ações verificadas.`);
// Regression: navigation during another operation must still load the catalog.
(async()=>{
 assert.equal(vm.runInContext("MENUS.filter(x=>['software','winutil'].includes(x[0])).length",context),1);
 await vm.runInContext(`(async()=>{
  let calls=0,resolve;
  request=async path=>{if(path==='software/jobs')return [];calls++;return new Promise(r=>resolve=r);};
  S.busy=true;S.softwareCatalog=[];switchPage('software');
  const pending=fetchSoftwareCatalog();
  if(calls!==1)throw Error('Catálogo ignorado ou duplicado durante operação');
  resolve({programs:[{key:'firefox',name:'Firefox',category:'Navegadores',winget_id:'Mozilla.Firefox'}]});
  await pending;
  if(!main.innerHTML.includes('Mozilla.Firefox'))throw Error('Catálogo não renderizado');
  S.softwareCatalog=[];request=async()=>{throw Error('Falha simulada');};
  await fetchSoftwareCatalog();
  if(!main.innerHTML.includes('Falha simulada'))throw Error('Erro invisível');
  request=async()=>({programs:[{key:'7zip',name:'7-Zip',category:'Utilitários',winget_id:'7zip.7zip'}]});
  await act('software-refresh');
  if(!main.innerHTML.includes('7zip.7zip')||S.softwareCatalogError)throw Error('Retry falhou');
  S.page='machines';switchPage('winutil');
  if(S.page!=='software')throw Error('Atalho legado não redirecionado');
  S.busy=false;S.machines[0].device_type='computer';S.page='scripts';S.selected='PC-TESTE';
  let modal=null,requests=[];
  showModal=options=>{modal=options;};
  request=async(path,body)=>{
   requests.push({path,body});
   if(path==='maintenance/downloads-cleanup')return {ok:false,partial:true,message:'Arquivo em uso não removido',result:{Falhas:1,ArquivosRemovidos:10}};
   if(path==='printers/drivers/catalog')return {packages:[{id:'zd',driver_name:'ZDesigner ZD421',models:['ZD421'],reviewed:true,verified:false}]};
   if(path.startsWith('printers/drivers/installed'))return {ok:true,result:[{Name:'ZDesigner ZD421'}]};
   if(path.startsWith('admin/printers'))return {ok:true,result:[{Name:'Zebra ZD421',DriverName:'ZDesigner antigo'}]};
   if(path==='printers/drivers/change')return {ok:true,result:{DriverAtual:'ZDesigner ZD421'}};
   throw Error('Rota não simulada: '+path);
  };
  render();
  if(main.innerHTML.includes('downloads-preview')||main.innerHTML.includes('data-download-id')||main.innerHTML.includes('downloads-days'))throw Error('Downloads ainda exige prévia, seleção ou idade');
  if(!main.innerHTML.includes('Excluir todos os Downloads de todos os usuários'))throw Error('Botão integral ausente');
  await act('downloads-cleanup');
  if(modal)throw Error('Limpeza Downloads abriu confirmação adicional');
  const cleanup=requests.filter(x=>x.path==='maintenance/downloads-cleanup');
  if(cleanup.length!==1||Object.keys(cleanup[0].body).join(',')!=='target'||cleanup[0].body.target!=='PC-TESTE')throw Error('Clique não executou Downloads integral em uma requisição');
  if(requests.length!==1||!main.innerHTML.includes('Arquivo em uso não removido'))throw Error('Prévia foi solicitada ou resultado parcial está oculto');
  S.machines[0].device_type='printer';await act('downloads-cleanup');
  if(requests.length!==1)throw Error('Limpeza enviada para impressora');
  S.machines[0].device_type='computer';
  S.page='integrations';await act('drivers-installed');
  S.driverPrinter='Zebra ZD421';S.driverPackage='zd';render();
  if(!main.innerHTML.includes('ZDesigner ZD421'))throw Error('Driver installed-only revisado não aparece');
  await act('driver-change');
  if(modal)throw Error('Troca de driver abriu confirmação');
  const change=requests.find(x=>x.path==='printers/drivers/change');
  if(!change||change.body.driver!=='zd'||change.body.target!=='PC-TESTE'||'confirm' in change.body)throw Error('Troca não executou diretamente para o driver/alvo escolhido');
  showModal=()=>{throw Error('Comando abriu pedido de autorização');};
  refresh=async()=>{};loadAsset=async()=>{};
  document.querySelector('#tef-service-name').value='SiTef';
  document.querySelector('#zebra-printer').value='p1';
  document.querySelector('#zebra-label').value='l1';
  document.querySelector('#zebra-data').value='{}';
  request=async(path,body)=>{
   requests.push({path,body});
   if(path==='software/jobs')return [];
   if(path.startsWith('maintenance/restore-points'))return {ok:true,result:{Pontos:[{Numero:12,Descricao:'SIM antigo',IdadeDias:45,MaisRecente:false}]}};
   if(path.startsWith('admin/printers'))return {ok:true,result:[]};
   return {ok:true,message:'SIM',result:{message:'SIM',Codigo:0,Removido:true},job_id:'SIM'};
  };
  const direct=[
   ['asset-delete',{id:'42'},'assets/delete-image'],
   ['restore-create',{},'maintenance/restore-create'],
   ['restore-delete',{sequence:'12'},'maintenance/restore-delete'],
   ['cleanup-run',{},'maintenance/cleanup'],
   ['quick-optimize',{},'maintenance/quick-optimize'],
   ['disk-service',{service:'SysMain'},'maintenance/disk-service'],
   ['disk-tool',{tool:'sfc-scan'},'maintenance/disk-tool'],
   ['tef-service',{},'maintenance/tef-restart'],
   ['quick-flush-dns',{},'maintenance/flush-dns'],
   ['restart',{},'admin/restart'],
   ['rdp',{},'admin/rdp'],
   ['terminal',{},'admin/terminal'],
   ['spooler',{},'admin/spooler'],
   ['clear-print',{printer:'Zebra SIM'},'admin/clear-print'],
   ['zebra-print',{},'zebra/print'],
   ['winutil-launch',{},'winutil/launch'],
   ['software-install',{},'software/install'],
   ['software-uninstall',{},'software/uninstall'],
   ['stop-app',{},'system/shutdown']
  ];
  S.softwareSelected=new Set(['7zip']);
  for(const [action,data,path] of direct){
   const start=requests.length;
   await act(action,data);
   const posts=requests.slice(start).filter(x=>x.path===path);
   if(posts.length!==1||!posts[0].body||'confirm' in posts[0].body)throw Error('Comando não executou em um clique: '+action);
   if(path.startsWith('admin/')||path.startsWith('maintenance/')){
    if(posts[0].body.target!=='PC-TESTE')throw Error('Comando enviou alvo errado: '+action);
   }
  }
 })()`,context);
 console.log('Downloads, driver e 19 comandos executados por clique sem autorização adicional; alvos e resultados verificados.');
})().catch(e=>{console.error(e);process.exitCode=1;});
