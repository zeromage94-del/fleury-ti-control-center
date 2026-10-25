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
 })()`,context);
 console.log('Catálogo: carregamento com operação ocupada, deduplicação, falha visível, retry e menu único aprovados.');
})().catch(e=>{console.error(e);process.exitCode=1;});
