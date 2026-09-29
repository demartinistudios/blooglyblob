'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const BASE=process.env.BGB_REVIEW_URL,OUT=process.env.BGB_REVIEW_OUTPUT,KEY='blooglyblob-guide';
// Specific retired commands must not return to the public build instructions.
const OBSOLETE_COMMANDS=/\b(?:calibrate-servos|pi-test-servos)\b/i;
const SETUP=['computer-ssh-key','imager-choose','imager-settings','imager-write','pi-connect','repository-settings','audio-settings','software-install','service-check'];
const SOFTWARE_TOPICS=['overview','commands','settings','troubleshooting'];
if(!BASE||!OUT)throw Error('Set BGB_REVIEW_URL and a new BGB_REVIEW_OUTPUT directory');
fs.mkdirSync(OUT,{recursive:false});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.BGB_CHROME?{executablePath:process.env.BGB_CHROME}:{})});
 try{
  const page=await browser.newPage(),errors=[],links=new Set(),images=new Set(),checks=[],externalRequests=new Set();page.on('pageerror',e=>errors.push(e.message));
  async function capture(options){
   // Full-page captures must start at the top so sticky chrome is not baked into
   // the middle of the document after focus/copy checks scroll a control into view.
   await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   await page.screenshot(options);
  }
  // Exercise the browser copy API without touching the user's system clipboard.
  await page.addInitScript(()=>{
   window.clipboardWrites=[];window.clipboardDenied=false;
   Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{
    if(window.clipboardDenied)throw new DOMException('Fixture permission denied','NotAllowedError');
    window.clipboardWrites.push(text);
   }}});
  });
  page.on('request',request=>{const url=new URL(request.url());if(/^https?:$/.test(url.protocol)&&url.origin!==new URL(BASE).origin)externalRequests.add(url.href)});
  await page.goto(BASE);
  const data=await page.evaluate(()=>window.BGB);assert.ok(data.prints.length>0);
  assert.deepEqual(Object.keys(data).sort(),['electrical','guide','parts','plateSettingsHTML','prints']);
  assert.ok(!/"(exact|status|source|sources)":/.test(JSON.stringify(data)),'private fields in data.js');
  const build=data.guide.steps.filter(s=>s.kind==='build');assert.ok(build.length>0);
  // Step IDs are descriptive slugs; retired numeric and legacy IDs are gone, with no aliases.
  for(const step of data.guide.steps)assert.match(step.id,/^[a-z]+(?:-[a-z0-9]+)*$/,'descriptive step ID '+step.id);
  for(const retired of ['01','02','14','37','fb-base-nuts','fb-nuts','fb-stand','servo-position','software-prepare']){
   assert.ok(!data.guide.steps.some(s=>s.id===retired),'retired step ID '+retired);
   await page.goto(BASE+'#step-'+retired);assert.equal(await page.evaluate(()=>location.hash),'#step-'+retired);
   assert.ok((await page.locator('#page').innerText()).includes('Page not found'),'no alias for '+retired);
  }
  // Progress has no migration layer: stale ticks stay stored but only current build steps count.
  const stale={steps:['01','04','fb-base-nuts','servo-position','software-prepare','no-such-step',build[0].id],stock:['GS11','NOPE'],custom:{keep:true}};
  await page.evaluate(({KEY,stale,build1})=>{localStorage.clear();localStorage.setItem('unrelated','preserve');localStorage.setItem('bgb-r16-guide',JSON.stringify({steps:[build1],stock:[]}));localStorage.setItem(KEY,JSON.stringify(stale));},{KEY,stale,build1:build[1].id});
  await page.goto(BASE+'#step-'+build[1].id);await page.reload();
  assert.equal(await page.locator('#progress-count').textContent(),`1 / ${build.length}`,'only current build steps count; no earlier-preview import');
  assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),KEY),stale,'loading never rewrites saved progress');
  assert.equal(await page.evaluate(()=>localStorage.getItem('unrelated')),'preserve');
  await page.locator(`[data-step="${build[1].id}"]`).check();
  assert.equal(await page.locator('#progress-count').textContent(),`2 / ${build.length}`);
  assert.deepEqual((await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),KEY)).custom,{keep:true});
  await page.evaluate(KEY=>localStorage.removeItem(KEY),KEY);await page.reload();
  assert.equal(await page.locator('#progress-count').textContent(),`0 / ${build.length}`,'fresh browser starts empty');
  // Chapters follow the approved map: contiguous, in build order, shown as sidebar headings.
  const chapters=['Prepare','Print','Base hardware','Pi software','Base boards and controls','Base wiring','Light test','Frame and servos','Head','Body','Arms','Backpack and belt','Final wiring','First power-up','Head and arm mounting','Close up and test'];
  assert.deepEqual(build.map(s=>s.chapter).filter((c,i,a)=>c!==a[i-1]),chapters,'each chapter is contiguous, in build order');
  assert.deepEqual(await page.locator('#step-nav h3').evaluateAll(es=>es.map(e=>e.textContent)),chapters,'sidebar chapter headings');
  assert.deepEqual(await page.locator('#step-nav .num').evaluateAll(es=>es.map(e=>e.textContent)),build.map(s=>String(s.number)),'sidebar step numbers');
  assert.deepEqual(build.map(s=>s.number),Array.from({length:build.length},(_,i)=>i+1),'step numbers run continuously');
  assert.ok(data.guide.steps.filter(s=>s.kind==='service').every(s=>!s.number&&s.chapter==='Service'));
  const setupStart=build.findIndex(step=>step.id===SETUP[0]);
  assert.deepEqual(build.slice(setupStart,setupStart+SETUP.length+1).map(step=>step.id),[...SETUP,'pi-shifters']);
  assert.ok(build.slice(setupStart,setupStart+SETUP.length).every(step=>step.chapter==='Pi software'));
  await page.goto(BASE+'#step-'+SETUP[0]);
  for(const next of [...SETUP.slice(1),'pi-shifters']){
   await page.locator('[data-next-step]').click();await page.waitForURL(BASE+'#step-'+next);
   assert.equal(new URL(page.url()).hash,'#step-'+next,'setup continues without a reference detour');
  }
  async function checkCopies(){
   const closed=[];
   for(const detail of await page.locator('details').filter({has:page.locator('.code-card')}).all()){
    if(await detail.getAttribute('open')===null){closed.push(detail);await detail.locator('summary').first().click();}
   }
   for(const card of await page.locator('.code-card').all()){
    const kind=await card.getAttribute('data-kind'),copy=card.locator('[data-copy-code]');
    if(kind==='output'){assert.equal(await copy.count(),0,'expected output cannot be copied as a command');continue;}
    if(!await copy.count())continue; // Authored copy:false, e.g. placeholders.
    assert.match(await copy.innerText(),kind==='config'?/Copy example/:/Copy command/);
    const exact=await card.locator('pre.code-content > code').textContent();
    await page.evaluate(()=>{window.clipboardWrites=[]});
    await copy.focus();await page.keyboard.press('Enter');
    await page.waitForFunction(()=>window.clipboardWrites.length===1);
    assert.deepEqual(await page.evaluate(()=>window.clipboardWrites),[exact],'copy excludes context, prompts and output');
    assert.match(await card.locator('[role="status"]').innerText(),/copied/i);
    assert.equal(await copy.evaluate(el=>el===document.activeElement),true,'keyboard copy retains focus');
   }
   for(const detail of closed)await detail.locator('summary').first().click();
  }
  // The preparation link opens the complete tool list, even after unrelated filtering.
  await page.goto(BASE+'#parts');
  await page.locator('#search').fill('M3');
  await page.locator('#category').selectOption('Fastener');
  await page.locator('#stock-filter').selectOption('missing');
  const beforeTools=await page.evaluate(key=>localStorage.getItem(key),KEY);
  await page.goto(BASE+'#step-workbench');
  await page.locator('.instructions a[href="#parts/tools"]').click();
  assert.equal(new URL(page.url()).hash,'#parts/tools');
  assert.equal(await page.locator('#category').inputValue(),'Tool');
  assert.equal(await page.locator('#search').inputValue(),'');
  assert.equal(await page.locator('#stock-filter').inputValue(),'');
  assert.deepEqual(await page.locator('.part-card').evaluateAll(es=>es.map(e=>e.id)),data.parts.filter(p=>!p.omitted&&p.category==='Tool').map(p=>'part-'+p.id));
  assert.equal(await page.evaluate(key=>localStorage.getItem(key),KEY),beforeTools);
  await page.goto(BASE+'#parts/GS11');
  assert.equal(await page.locator('#part-GS11').count(),1,'tool filter must not hide a directly linked printed part');
  assert.equal(await page.locator('.part-card').count(),1);
  // Plate settings expand in the current guide page, preserving the route and shell.
  for(const route of ['printing','step-print-plates']){
   await page.goto(BASE+'#'+route);
   await page.waitForURL(BASE+'#step-print-plates');
   const before=page.url();
   assert.equal(new URL(before).hash,'#step-print-plates');
   assert.equal(await page.locator('nav a[data-route="printing"]').count(),0);
   assert.equal(await page.locator('input[data-step="print-plates"]').count(),1);
   assert.equal(await page.locator('a[href="repeat-build.html"]').count(),0);
   await page.locator('#plate-settings > summary').click();
   assert.equal(page.url(),before);
   assert.ok(await page.locator('#plate-settings').evaluate(el=>el.open));
   assert.equal(await page.locator('#plate-settings .plate').count(),10);
   assert.equal(await page.locator('#plate-settings footer').count(),0);
   assert.equal(await page.locator('#plate-settings h1').count(),0);
   assert.ok(await page.locator('#sidebar').count());
   await page.locator('#plate-settings > summary').click();
   assert.ok(!(await page.locator('#plate-settings').evaluate(el=>el.open)));
  }
  const beforePrinting=await page.evaluate(key=>localStorage.getItem(key),KEY);
  await page.goto(BASE+'#printing/GS11');
  await page.waitForURL(BASE+'#step-print-plates/GS11');
  assert.equal(new URL(page.url()).hash,'#step-print-plates/GS11');
  assert.ok(await page.locator('#plate-settings').evaluate(el=>el.open));
  assert.equal(await page.locator('.selected-plate').getAttribute('id'),'C1');
  assert.equal(await page.locator('#plate-settings a[href="downloads/stl/GS11.stl"][download]').count(),1);
  await page.goto(BASE+'#printing/AR07');
  await page.waitForURL(BASE+'#step-print-plates/AR07');
  assert.equal(new URL(page.url()).hash,'#step-print-plates/AR07');
  assert.ok((await page.locator('#page').innerText()).includes('not on the supplied plates'));
  assert.equal(await page.locator('a[href="downloads/stl/AR07.stl"][download]').count(),1);
  assert.equal(await page.evaluate(key=>localStorage.getItem(key),KEY),beforePrinting);
  await page.goto(BASE+'#hardware');
  const downloadLink=page.locator('a[href="downloads/screw-key-letter.pdf"]');
  assert.notEqual(await downloadLink.evaluate(el=>getComputedStyle(el,'::before').maskImage),'none');
  const downloadEvent=page.waitForEvent('download');
  await downloadLink.click();
  const download=await downloadEvent;
  assert.equal(download.suggestedFilename(),'screw-key-letter.pdf');
  assert.equal(new URL(page.url()).hash,'#hardware');
  // The service stand is retired (owner decision Q3): no stand step, saddle part or downloads.
  assert.ok(!data.parts.some(p=>p.id==='J05'),'retired stand saddle part');
  const installed=data.parts.filter(p=>p.category==='Printed'&&p.qty);
  const pieces=installed.reduce((n,p)=>n+p.qty,0);
  const plateQuantities={};for(const plate of data.prints)for(const [id,n] of Object.entries(plate.quantities))plateQuantities[id]=(plateQuantities[id]||0)+n;
  assert.deepEqual(plateQuantities,Object.fromEntries(installed.map(p=>[p.id,p.qty])));
  assert.ok(build.find(s=>s.id==='speaker-grilles').number < build.find(s=>s.id==='side-grilles').number,'attach speakers on the bench before mounting side grilles');
  // The three nut steps together preload every enclosure nut before any part fastens into them.
  const nutSteps=['board-cover-nuts','grille-vent-nuts','cradle-jack-nuts'].map(id=>build.find(s=>s.id===id));
  const preloaded={};for(const step of nutSteps)for(const [id,n] of Object.entries(step.hardware))preloaded[id]=(preloaded[id]||0)+n;
  assert.deepEqual(preloaded,{N2:8,N3:25});
  assert.deepEqual(nutSteps.map(s=>s.number),[nutSteps[0].number,nutSteps[0].number+1,nutSteps[0].number+2]);
  for(const id of ['front-grille-rear-vent','side-grilles','pi-shifters','audio-cradle','power-jack','bottom-cover']){
   const step=build.find(s=>s.id===id);assert.ok(step.number>nutSteps[2].number);
   assert.ok(!step.hardware.N3,'enclosure M3 nuts must be preloaded: '+id);
   if(id==='pi-shifters')assert.ok(!step.hardware.N2);
  }
  // Loading keeps saved progress, stock and unrelated fields exactly as stored.
  const existing={steps:['front-grille-rear-vent','pi-shifters','bottom-cover'],stock:['N2','N3'],custom:'keep'};
  await page.evaluate(({KEY,existing})=>localStorage.setItem(KEY,JSON.stringify(existing)),{KEY,existing});
  await page.reload();assert.deepEqual(await page.evaluate(KEY=>JSON.parse(localStorage.getItem(KEY)),KEY),existing);
  const steps=new Set(data.guide.steps.map(s=>s.id));
  const shots=['step-board-cover-nuts','step-grille-vent-nuts','step-cradle-jack-nuts','step-bottom-cover','step-backpack','step-belt','step-power-jack','step-button-leads','step-button','step-pi-shifters','step-secure-base-wiring','step-side-grilles','step-audio-cradle','step-audio-module','step-computer-ssh-key','step-imager-choose','step-imager-settings','step-imager-write','step-shoulder-servos','step-head-servo','step-eye-housings','step-eye-boards','step-feet','step-speaker-grilles','step-body-light-input','step-body-light-test','step-head-harness','step-body-light-strand','step-body-lights','step-print-plates','step-print-cleanup','step-front-grille-rear-vent','step-wagos','parts/C16','parts/C17','parts/C18','parts/FB41','parts/P35','start','parts','printing','hardware','electrical','safety','software','step-workbench','step-eye-windows','step-shifter-wiring','step-button-audio-wiring','step-fit-position','step-shelf-arms','step-head-shoulder-covers','step-first-movement','step-secure-wiring'];
  shots.push(...SETUP.map(id=>'step-'+id),...SOFTWARE_TOPICS.map(id=>'software/'+id));
  for(const r of shots.filter(r=>r.startsWith('step-')))assert.ok(steps.has(r.slice(5)),'screenshot route missing: '+r);
  const routes=['start','parts','parts/tools','hardware','printing','printing/GS11','printing/AR07','electrical','safety','software','troubleshooting',...data.guide.steps.map(s=>'step-'+s.id),...data.parts.map(p=>'parts/'+p.id)];
  routes.push(...SOFTWARE_TOPICS.map(id=>'software/'+id));
  const textOf=action=>action.replace(/`([^`]+)`/g,'$1').replaceAll('{tools}','tool list').replace(/\{step:([\w-]+)\}/g,(_,id)=>{
   const target=data.guide.steps.find(s=>s.id===id);
   assert.ok(target,'action references known step '+id);
   return target.kind==='service'?'“'+target.title+'”':'step '+target.number;
  });
  for(const width of [1440,820,360]){
   await page.setViewportSize({width,height:1000});
   for(const route of routes){
    await page.goto(BASE+'#'+route);await page.locator('#page').waitFor();
    const txt=await page.locator('#page').innerText();assert.ok(!/undefined|NaN|Step not found|Page not found/.test(txt),route);
    const leak=txt.match(OBSOLETE_COMMANDS);assert.ok(!leak,route+' contains '+(leak&&leak[0]));
    assert.ok(!/undefined|Page not found/.test(await page.title()),route+' title');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,route+' '+width);
    if(route.startsWith('step-')){
     const step=data.guide.steps.find(s=>s.id===route.slice(5));
     assert.equal(await page.locator('.action-panel').count(),step.panels.length);
     assert.equal(await page.locator('.action-copy .instructions li').count(),step.actions.length);
     assert.equal(await page.locator('.action-copy .action-note').count(),step.panels.filter(p=>p.caption).length,'notes remain with action text');
     const rendered=await page.locator('.action-panel').evaluateAll(panels=>panels.map(panel=>({
      title:panel.querySelector('h2').textContent,
      actions:[...panel.querySelectorAll('.instructions li')].map(li=>li.textContent),
      image:panel.querySelector('.action-panel-body > .diagram img')?.getAttribute('src')||null,
      blocks:[...panel.querySelectorAll('.code-card')].map(card=>({kind:card.dataset.kind,text:card.querySelector('code').textContent,copy:!!card.querySelector('[data-copy-code]')}))
     })));
     assert.deepEqual(rendered,step.panels.map(panel=>({
      title:panel.title,actions:panel.actions.map(i=>textOf(step.actions[i])),image:panel.image||null,
      blocks:(panel.codeBlocks||(panel.commands?.length?[{kind:'command',lines:panel.commands}]:[])).map(block=>({kind:block.kind,text:block.lines.join('\n'),copy:block.kind!=='output'&&block.copy!==false}))
     })),'each drawing, action and exact code stays with its authored panel: '+route);
     const layout=await page.locator('.action-panel').evaluateAll(es=>es.map(el=>{
      const image=el.querySelector('.diagram img'),copy=el.querySelector('.action-copy');
      if(!image)return null;
      const screenshot=el.classList.contains('action-panel-screenshot'),frame=image.parentElement;
      return {screenshot,clipped:getComputedStyle(frame).overflow==='hidden',height:(screenshot?frame:image).getBoundingClientRect().height,limit:screenshot?550:parseFloat(getComputedStyle(image).maxHeight),beside:copy.getBoundingClientRect().left>=el.querySelector('.diagram').getBoundingClientRect().right,gap:Math.abs(copy.getBoundingClientRect().top-el.querySelector('.diagram').getBoundingClientRect().top)};
     }).filter(Boolean));
     for(const panel of layout){if(panel.screenshot)assert.ok(panel.clipped,'screenshot frame must clip its full-window source');assert.ok(panel.height<=panel.limit+1,'oversized action image: '+route);if(panel.beside)assert.ok(panel.gap<2,'text must start beside its drawing: '+route);}

     assert.ok(step.panels.every(p=>p.actions.length>=1&&p.actions.length<=3));
     if(step.panels.some(p=>p.detail)){
      const details=page.locator('.action-detail'),count=step.panels.filter(p=>p.detail).length;assert.equal(await details.count(),count);
      for(let i=0;i<count;i++){
       const d=details.nth(i);assert.equal(await d.getAttribute('open'),null);
       await d.locator('summary').click();assert.notEqual(await d.getAttribute('open'),null);
       await d.locator('img').waitFor({state:'visible'});
       await d.locator('img').evaluate(img=>img.decode());
       await d.locator('summary').click();assert.equal(await d.getAttribute('open'),null);
      }
     }
     if(step.id==='fit-position')assert.equal(await page.locator('.action-panel').first().locator('.code-card[data-kind="command"]').count(),1,'fit commands must precede attachment');
     if(SETUP.includes(step.id)&&width===1440)await checkCopies();
    }
    for(const link of await page.locator('#page a[href^="downloads/"]').all()){assert.notEqual(await link.getAttribute('download'),null);assert.notEqual(await link.evaluate(el=>getComputedStyle(el,'::before').maskImage),'none');}
    if(route==='printing'){assert.ok(txt.includes(`${pieces} printed pieces / ${installed.length} types`)&&txt.includes('flow dynamics calibration off'));assert.ok(await page.locator('a[href="downloads/BlooglyBlob-PLA.3mf"]').count()>=1);}
    if(route==='hardware'){for(const size of ['M2','M3']){const count=Object.entries(data.guide.totals).filter(([id])=>id.startsWith(size+'x')).reduce((sum,[,n])=>sum+n,0);assert.ok(txt.includes(`${count} ${size} screws`));}}
    for(const href of await page.locator('a[href]').evaluateAll(es=>es.map(e=>e.getAttribute('href')))){
     if(href.startsWith('#step-'))assert.ok(steps.has(href.slice(6).split('/')[0]),href);
     if(href&&!/^(#|https?:|mailto:)/.test(href))links.add(href);
    }
    for(const src of await page.locator('img[src]').evaluateAll(es=>es.map(e=>e.getAttribute('src'))))if(!/^https?:/.test(src))images.add(src);
    await page.locator('#page img[src]').evaluateAll(async es=>{for(const e of es)e.loading='eager';await Promise.all(es.map(e=>e.decode().catch(()=>{throw new Error('Image failed to decode: '+e.src)})));});
    assert.ok(await page.locator('#page img[src]').evaluateAll(es=>es.every(e=>e.complete&&e.naturalWidth>0)),route+' image decode');
    assert.equal(await page.locator('#print').count(),0,'removed guide print control');
    if(route==='electrical'){
     const topics=page.locator('[data-reference]');
     assert.equal(await topics.count(),9);
     assert.equal(await page.locator('#reference-master').evaluate(el=>el.open),true,'master wiring is available on arrival');
     assert.deepEqual(new Set(await topics.evaluateAll(es=>es.map(e=>e.getAttribute('aria-controls')))),new Set(await page.locator('.reference-topic').evaluateAll(es=>es.map(e=>e.id))),'every electrical topic must have a visible navigation control');
     for(const control of await topics.all()){
      const id=await control.getAttribute('aria-controls');
      await control.click();
      await page.waitForFunction(id=>document.querySelector(`[aria-controls="${id}"]`).getAttribute('aria-expanded')==='true',id);
      assert.equal(await page.locator('.reference-topic[open]').count(),1,'one electrical topic at a time');
      const topic=page.locator('#'+id);
      assert.equal(await topic.evaluate(el=>el.open),true);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'electrical topic '+id+' '+width);
      if(id==='reference-master'){
       const view=topic.locator('.master-window');
       assert.equal(await view.locator('img').getAttribute('width'),'2640','connected drawing native dimensions');
       assert.equal(await topic.locator('[data-wiring-section]').count(),0,'one circuit, no separate section navigation');
       assert.ok(await view.locator('img').evaluate(el=>el.clientWidth<=el.parentElement.clientWidth&&el.clientHeight<=el.parentElement.clientHeight),'whole drawing fits the overview');
       const detail=topic.locator('[data-wiring-detail]');
       await detail.click();
       assert.equal(await detail.getAttribute('aria-pressed'),'true');
       assert.equal(await view.locator('img').evaluate(el=>el.clientWidth),2640,'larger labels retain native scale');
       assert.equal(await view.evaluate(el=>el===document.activeElement),true,'keyboard focus follows the drawing');
       await view.evaluate(el=>el.scrollTo({left:400,top:300}));
       assert.ok(await view.evaluate(el=>el.scrollLeft>0&&el.scrollTop>0),'connected drawing can be panned');
       assert.equal(await topic.locator('a[download][href="assets/circuits/master-wiring.svg"]').count(),1);
       assert.equal(await topic.locator('a[target="_blank"][href="assets/circuits/master-wiring.svg"]').count(),1);
       await detail.click();
       assert.equal(await detail.getAttribute('aria-pressed'),'false');
       assert.ok(await view.locator('img').evaluate(el=>el.clientWidth<=el.parentElement.clientWidth&&el.clientHeight<=el.parentElement.clientHeight),'fit diagram restores the whole circuit');
       await capture({path:path.join(OUT,'reference-master-'+width+'.png'),fullPage:true});
      }
      const sizes=await topic.locator('.diagram img').evaluateAll(es=>es.map(el=>({w:el.getBoundingClientRect().width,h:el.getBoundingClientRect().height})));
      for(const size of sizes){assert.ok(size.w<=361&&size.h<=641,'bounded electrical drawing '+id);}
      for(const summary of await topic.locator('.reference-table > summary').all()){
       await summary.click();
       assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'electrical table '+id+' '+width);
       await summary.click();
      }
      if(['reference-power','reference-signals','reference-connectors'].includes(id))await capture({path:path.join(OUT,id+'-'+width+'.png'),fullPage:true});
     }
     await page.locator('.reference-topic[open] > summary').click();
     await page.waitForFunction(()=>[...document.querySelectorAll('[data-reference]')].every(el=>el.getAttribute('aria-expanded')==='false'));
     assert.equal(await page.evaluate(()=>document.activeElement?.dataset.reference),'names','closing a topic restores focus to its visible selector');
    }
    if(route==='software'||route.startsWith('software/')){
     assert.equal(await page.locator(`.setup-cta a[href="#step-${SETUP[0]}"]`).count(),1,'reference links to first-time setup');
     for(const topic of SOFTWARE_TOPICS)assert.equal(await page.locator('#software-'+topic).count(),1,'software topic '+topic);
     if(route.includes('/')){
      const target='software-'+route.split('/')[1];
      assert.equal(new URL(page.url()).hash,'#'+route);
      assert.equal(await page.evaluate(()=>document.activeElement?.closest('section')?.id),target,'deep-link focus reaches topic');
     }
     if(route==='software'&&width===1440)await checkCopies();
    }
    if(route==='printing'){await page.locator('#plate-settings > summary').click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'expanded plate settings '+width);await capture({path:path.join(OUT,'plate-settings-'+width+'.png'),fullPage:true});await page.locator('#plate-settings > summary').click();}
    if(shots.includes(route))await capture({path:path.join(OUT,route.replaceAll('/','-')+'-'+width+'.png'),fullPage:true});
    checks.push({route,width});
   }
  }
  // Failure feedback keeps the exact command selectable instead of claiming success.
  await page.goto(BASE+'#step-repository-settings');
  const failureCard=page.locator('.code-card[data-kind="command"]').filter({has:page.locator('[data-copy-code]')}).first();
  const failureCode=failureCard.locator('pre.code-content > code'),failureText=await failureCode.textContent();
  await page.evaluate(()=>{window.clipboardDenied=true;window.clipboardWrites=[]});
  await failureCard.locator('[data-copy-code]').click();
  await page.waitForFunction(()=>[...document.querySelectorAll('.copy-status')].some(el=>/select|manually/i.test(el.textContent)));
  assert.match(await failureCard.locator('[role="status"]').innerText(),/select|manually/i);
  assert.deepEqual(await page.evaluate(()=>window.clipboardWrites),[]);
  assert.equal(await failureCode.textContent(),failureText);
  assert.notEqual(await failureCode.evaluate(el=>getComputedStyle(el).userSelect),'none');
  await page.evaluate(()=>{window.clipboardDenied=false});
  // Imager captures are reachable at the project subpath and open with keyboard input.
  await page.goto(BASE+'#step-imager-choose');
  const setupImage=page.locator('.action-panel img[src^="assets/setup/imager-"]').first();
  assert.ok(await setupImage.count(),'setup uses real captured Imager assets');
  const setupSource=await setupImage.getAttribute('src');
  const enlarge=setupImage.locator('..');await enlarge.focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#zoom-image').getAttribute('src'),setupSource);
  assert.ok(await page.locator('#zoom').isVisible());await page.keyboard.press('Escape');
  assert.ok(!await page.locator('#zoom').isVisible());
  // Enlarged reading must retain the page width and keyboard-copy controls.
  await page.setViewportSize({width:1440,height:1000});
  for(const route of ['step-repository-settings','software/commands']){
   await page.goto(BASE+'#'+route);
   await page.evaluate(()=>{document.documentElement.style.zoom='2'});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'200% zoom overflow: '+route);
   const copy=page.locator('[data-copy-code]').first();await copy.focus();
   assert.equal(await copy.evaluate(el=>document.activeElement===el),true);
   await capture({path:path.join(OUT,route.replaceAll('/','-')+'-zoom200.png'),fullPage:true});
   await page.evaluate(()=>{document.documentElement.style.zoom=''});
  }
  await page.goto(BASE+'#no-such-page');await page.locator('#page').waitFor();
  assert.ok((await page.locator('#page').innerText()).includes('Page not found'));assert.ok((await page.title()).startsWith('Page not found'));
  for(const doc of ['repeat-build.html','references.html']){
   await page.goto(new URL(doc,BASE).href);
   assert.ok(!OBSOLETE_COMMANDS.test((await page.locator('body').innerText()).replace(/\(R16 series\)/g,'')),doc+' leak');
   for(const width of [1440,820,360]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,doc+' '+width);await capture({path:path.join(OUT,doc.replace('.html','')+'-'+width+'.png'),fullPage:true});}
   for(const href of await page.locator('a[href]').evaluateAll(es=>es.map(e=>e.getAttribute('href'))))if(href&&!/^(#|https?:|mailto:)/.test(href))links.add(href);
   for(const src of await page.locator('img[src]').evaluateAll(es=>es.map(e=>e.getAttribute('src'))))if(!/^https?:/.test(src))images.add(new URL(src,new URL(doc,BASE)).href.slice(BASE.replace(/[^/]*$/,'').length));
  }
  await page.goto(BASE+'#step-eye-windows');await page.locator('[data-zoom]').first().click();assert.ok(await page.locator('#zoom').isVisible());await page.locator('#close-zoom').click();assert.ok(!await page.locator('#zoom').isVisible());
  for(const href of new Set([...links,...images]))assert.ok((await page.request.get(new URL(href,BASE).href)).ok(),href);
  await page.goto(BASE+'#step-power-jack');
  assert.equal(await page.locator('.bench-list').evaluate(el=>el.open),false);
  await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
  assert.equal(await page.locator('.bench-list').evaluate(el=>el.open),true,'print includes parts');
  await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
  assert.equal(await page.locator('.bench-list').evaluate(el=>el.open),false,'restore inventory disclosure');
  await page.goto(BASE+'#electrical');
  await page.locator('[data-reference="signals"]').click();
  const openBeforePrint=await page.locator('.electrical-reference details').evaluateAll(es=>es.map(el=>el.open));
  await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
  assert.ok(await page.locator('.electrical-reference details').evaluateAll(es=>es.every(el=>el.open)),'print includes every electrical topic and table');
  await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
  assert.deepEqual(await page.locator('.electrical-reference details').evaluateAll(es=>es.map(el=>el.open)),openBeforePrint,'restore electrical topic selection after print');
  // Check the project path instead of accidentally succeeding at a domain root.
  assert.equal((await page.request.get(new URL('/index.html',BASE).href)).status(),404);
  assert.equal((await page.request.get(new URL('Index.html',BASE).href)).status(),404);
  await page.setViewportSize({width:1100,height:1400});
  await page.emulateMedia({media:'print',reducedMotion:'reduce'});
  for(const route of ['#step-print-plates','#step-eye-windows','#electrical','references.html','repeat-build.html']){
   await page.goto(new URL(route,BASE).href);await page.evaluate(()=>document.fonts.ready);
   await page.locator('img[src]').evaluateAll(async es=>{for(const e of es)e.loading='eager';await Promise.all(es.map(e=>e.decode()));});
   const label=route.replace('#','').replace('.html','');
   await capture({path:path.join(OUT,label+'-print.png'),fullPage:true});
   await page.pdf({path:path.join(OUT,label+'-print.pdf'),format:'A4',printBackground:true});
  }
  for(const img of images)assert.ok(!img.startsWith('assets/products/'),'Unlicensed product photo shown: '+img);
  for(const rejected of ['assets/community/speaker-stack.svg','assets/community/eye-fasteners.svg','assets/horn-joint.svg','assets/r17/wago-clamp-detail.png','assets/community/pebble-retention.svg'])assert.ok(!images.has(rejected),'Placeholder assembly diagram returned: '+rejected);
  assert.deepEqual(errors,[]);
  assert.deepEqual([...externalRequests],[],'Guide made third-party browser requests');
  fs.writeFileSync(path.join(OUT,'browser.json'),JSON.stringify({status:'PASS',base:BASE,checks,links:[...links],images:[...images],errors,externalRequests:[...externalRequests],staleProgressIgnored:true},null,2));console.log('PASS',checks.length,'routes/viewports',links.size,'links',images.size,'images');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
