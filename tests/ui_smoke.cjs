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
   if(path.startsWith('maintenance/downloads-preview'))return {ok:true,preview_id:'preview',files:[{id:'file1',name:'old.pdf',profile:'Alice',bytes:100}]};
   if(path==='maintenance/downloads-cleanup')return {ok:false,partial:true,message:'Arquivo alterado preservado',result:{Falhas:1}};
   if(path==='printers/drivers/catalog')return {packages:[{id:'zd',driver_name:'ZDesigner ZD421',models:['ZD421'],reviewed:true,verified:false}]};
   if(path.startsWith('printers/drivers/installed'))return {ok:true,result:[{Name:'ZDesigner ZD421'}]};
   if(path.startsWith('admin/printers'))return {ok:true,result:[{Name:'Zebra ZD421',DriverName:'ZDesigner antigo'}]};
   if(path==='printers/drivers/change')return {ok:true,result:{DriverAtual:'ZDesigner ZD421'}};
   throw Error('Rota não simulada: '+path);
  };
  await act('downloads-preview');
  if(S.downloadsSelected.size||!main.innerHTML.includes('old.pdf'))throw Error('Downloads pré-selecionados ou prévia ausente');
  await act('downloads-cleanup');
  if(modal)throw Error('Exclusão sem seleção abriu confirmação');
  if(requests.some(x=>x.path==='maintenance/downloads-cleanup'))throw Error('Downloads apagados sem seleção');
  S.downloadsSelected.add('file1');await act('downloads-cleanup');
  if(modal)throw Error('Limpeza Downloads abriu confirmação adicional');
  const cleanup=requests.filter(x=>x.path==='maintenance/downloads-cleanup');
  if(cleanup.length!==1||cleanup[0].body.files[0]!=='file1'||'confirm' in cleanup[0].body)throw Error('Clique não executou a seleção diretamente');
  if(S.downloadsPreview||!main.innerHTML.includes('Arquivo alterado preservado'))throw Error('Prévia não consumida ou resultado parcial oculto');
  S.page='integrations';await act('drivers-installed');
  S.driverPrinter='Zebra ZD421';S.driverPackage='zd';render();
  if(!main.innerHTML.includes('ZDesigner ZD421'))throw Error('Driver installed-only revisado não aparece');
  await act('driver-change');
  if(!modal||requests.some(x=>x.path==='printers/drivers/change'))throw Error('Troca sem confirmação ou modal ausente');
  await modal.onConfirm();
  const change=requests.find(x=>x.path==='printers/drivers/change');
  if(change.body.driver!=='zd'||change.body.target!=='PC-TESTE')throw Error('Troca enviou driver/alvo errado');
 })()`,context);
 console.log('Catálogo, Downloads direto sem modal, resultado parcial e troca de driver revisado aprovados.');
})().catch(e=>{console.error(e);process.exitCode=1;});
