'use strict';

// Real browser smoke of the PR-only static site. Never deploys or edits ledgers.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const os=require('node:os');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const puppeteer=require('puppeteer-core');
const axe=require('axe-core');

const ROOT=path.resolve(process.env.V1_BROWSER_DOCROOT || path.resolve(__dirname,'..','docs'));
const OUT=path.resolve(process.env.V1_BROWSER_OUT || '.audit/browser_smoke');
const HAS_PUBLISHED_HEALTH=fs.existsSync(path.join(ROOT,'data','quellenstatus_21.json'));
const HEALTH_STATES=HAS_PUBLISHED_HEALTH?['fresh','degraded','stale']:['missing'];
const TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8',
  '.svg':'image/svg+xml'};
function chromePath() {
  const options=[process.env.CHROME_BIN,
    '/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium',
    '/opt/google/chrome/chrome'];
  for (const p of options) if(p && fs.existsSync(p)) return p;
  for(const name of ['google-chrome','chromium']){
    try{return execFileSync('which',[name],{encoding:'utf8'}).trim();}catch(_){}
  }
  throw new Error('Chromium/Chrome on GitHub runner is unavailable');
}
function startServer() {
  return new Promise(resolve=>{
    const server=http.createServer((request,response)=>{
      try {
        const url=new URL(request.url,'http://127.0.0.1');
        const relative=decodeURIComponent(url.pathname).replace(/^\/+/,'')||'index.html';
        const full=path.resolve(ROOT,relative);
        if (!full.startsWith(ROOT+path.sep) || !fs.existsSync(full) ||
            !fs.statSync(full).isFile()) {
          response.writeHead(404,{'Content-Type':'text/plain'});response.end('Missing source feed');return;
        }
        response.writeHead(200,{'Content-Type':TYPES[path.extname(full)]||'application/octet-stream',
          'Cache-Control':'no-store'});
        fs.createReadStream(full).pipe(response);
      } catch (_) {response.writeHead(400);response.end('Bad request');}
    });
    server.listen(0,'127.0.0.1',()=>resolve({server,url:'http://127.0.0.1:'+server.address().port+'/'}));
  });
}
async function textOf(page,selector) {
  return page.$eval(selector,el=>el.textContent.trim());
}
async function visible(page,selector) {
  return page.$eval(selector,el=>!el.hidden && getComputedStyle(el).display!=='none');
}
async function readyCount(page,count) {
  await page.waitForFunction(
    number=>document.querySelector('#metric-total')?.textContent.trim()===number,
    {timeout:12000},String(count));
}
async function main() {
  fs.mkdirSync(OUT,{recursive:true});
  const {server,url}=await startServer();
  let browser;
  const steps=[];
  const fail=(name,reason)=>{steps.push({name,status:'FAIL',reason:String(reason)});throw new Error(name+': '+reason);};
  const pass=name=>steps.push({name,status:'PASS'});
  try {
    browser=await puppeteer.launch({headless:true,executablePath:chromePath(),
      args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
    const page=await browser.newPage();
    const browserErrors=[];
    page.on('pageerror',error=>browserErrors.push(error.message));
    await page.setViewport({width:1366,height:900,deviceScaleFactor:1});
    await page.goto(url,{waitUntil:'load'});
    await readyCount(page,135);
    assert.equal(await textOf(page,'#metric-events'),'123');
    assert.match(await textOf(page,'#hero-snapshot'),/14\.10\.2026/);
    assert.equal(await visible(page,'#wp20-note'),true);
    assert.equal(await visible(page,'#wp21-note'),false);
    pass('Desktop historical baseline 135/123 and dated discrepancy');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>
      document.activeElement?.classList.contains('skip-link')),true);
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(()=>location.hash),'#inhalt');
    assert.equal(await page.evaluate(()=>document.activeElement?.id),'inhalt');
    pass('Keyboard skip link focuses the main landmark');
    await page.screenshot({path:path.join(OUT,'desktop_wp20.png'),fullPage:true});

    await page.focus('#period-21');
    await page.keyboard.press('Enter');
    await readyCount(page,8);
    assert.equal(await page.$eval('#period-21',e=>e.getAttribute('aria-pressed')),'true');
    assert.match(await textOf(page,'#period-announcement'),/Unvollständige Auswahl, keine Gesamtzahl/);
    pass('Keyboard period switch announces incomplete WP21 sample');
    assert.match(await textOf(page,'#metric-total-label'),/BISHER EINZELN GEPRÜFT/);
    assert.equal(await visible(page,'#wp21-note'),true);
    assert.equal(await visible(page,'#wp20-note'),false);
    assert.match(await textOf(page,'#ranking-caption'),/nicht repräsentativ/);
    assert.match(await textOf(page,'#footer-period'),/UNVOLLSTÄNDIGE ERFASSUNG/);
    assert.equal(new URL(page.url()).searchParams.get('wp'),'21');
    pass('Switch to partial WP21 never claims overall count');

    await page.waitForFunction(states=>{
      const box=document.querySelector('#wp21-health');
      return box && states.includes(box.dataset.state) &&
        !box.textContent.includes('wird geladen');
    },{timeout:8000},HEALTH_STATES);
    if(!HAS_PUBLISHED_HEALTH) {
      assert.match(await textOf(page,'#wp21-health'),/nicht verfügbar/);
      pass('PR preview visibly discloses unavailable source monitor');
    } else {
      assert.match(await textOf(page,'#wp21-health'),/Quellencheck|Quellenüberwachung/);
      pass('Production source-health state is truthfully displayed in the browser');
    }

    await page.type('#search','Diese Person gibt es hier garantiert nicht');
    assert.equal(await textOf(page,'#result-count'),'0');
    assert.equal(await visible(page,'#empty-state'),true);
    await page.click('#reset');
    assert.equal(await textOf(page,'#result-count'),'8');
    pass('Search, empty state and reset work');
    await page.click('#period-20');
    await readyCount(page,135);
    await page.type('#search','Beatrix von Storch');
    assert.equal(await textOf(page,'#result-count'),'18');
    pass('Named-person historical filter respects individually reviewed count');
    await page.focus('#people-ranking .bar-row');
    await page.keyboard.press('Enter');
    const filterFocus=await page.evaluate(()=>({
      id:document.activeElement?.id,value:document.querySelector('#search').value
    }));
    assert.equal(filterFocus.id,'search');
    assert.ok(filterFocus.value.length>0);
    pass('Keyboard ranking filter transfers focus to the search control');

    await page.setViewport({width:390,height:844,deviceScaleFactor:2,isMobile:true,
      hasTouch:true});
    await page.goto(url+'?wp=21',{waitUntil:'load'});
    await readyCount(page,8);
    await page.waitForFunction(states=>{
      const box=document.querySelector('#wp21-health');
      return box && states.includes(box.dataset.state) &&
        !box.textContent.includes('wird geladen');
    },{timeout:8000},HEALTH_STATES);
    const geometry=await page.evaluate(()=>({
      viewport:document.documentElement.clientWidth,
      width:document.documentElement.scrollWidth,
      metaVisible:!document.querySelector('#wp21-note').hidden,
    }));
    if(geometry.width>geometry.viewport+3)
      fail('Mobile width','Horizontal page overflow: '+JSON.stringify(geometry));
    assert.equal(geometry.metaVisible,true);
    await page.screenshot({path:path.join(OUT,'mobile_wp21.png'),fullPage:true});
    pass('Mobile 390px partial WP21 fits viewport');
    await page.focus('.table-scroller');
    const region=await page.$eval('.table-scroller',box=>({
      focused:document.activeElement===box,
      overflow:box.scrollWidth>box.clientWidth,
      role:box.getAttribute('role')
    }));
    assert.equal(region.focused,true);
    assert.equal(region.role,'region');
    assert.equal(region.overflow,true);
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(()=>
      document.querySelector('.table-scroller').scrollLeft>0,{timeout:4000});
    pass('Mobile horizontal table is keyboard focusable and scrollable');

    await page.setViewport({width:320,height:720,deviceScaleFactor:2,
      isMobile:true,hasTouch:true});
    await page.goto(url+'?wp=20',{waitUntil:'load'});
    await readyCount(page,135);
    const narrow=await page.evaluate(()=>({
      viewport:document.documentElement.clientWidth,
      width:document.documentElement.scrollWidth,
      tableScroll:document.querySelector('.table-scroller').scrollWidth>
        document.querySelector('.table-scroller').clientWidth,
      total:document.querySelector('#metric-total').textContent.trim()
    }));
    if(narrow.width>narrow.viewport+3)
      fail('320px reflow','Unexpected whole-page overflow '+JSON.stringify(narrow));
    assert.equal(narrow.tableScroll,true);
    assert.equal(narrow.total,'135');
    pass('320px narrow reflow preserves verified totals and horizontal table access');
    await page.screenshot({path:path.join(OUT,'narrow_wp20.png'),fullPage:true});

    const firstRowHandle=await page.$('#records-body tr');
    await page.focus('#load-more');
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(node=>
      document.querySelector('#records-body tr')===node,firstRowHandle),true);
    pass('Loading more records preserves the existing table row DOM nodes');
    assert.equal(await textOf(page,'#showing-count'),'30 von 135 Einträgen angezeigt');
    assert.equal(await page.evaluate(()=>document.activeElement?.id),'load-more');
    assert.equal(await textOf(page,'#metric-total'),'135');
    pass('Keyboard load-more preserves focus and verified total');
    // Complete the remaining pages with Enter. On the final activation,
    // the button becomes hidden and focus must not disappear.
    for(let count=45;count<=135;count+=15){
      await page.keyboard.press('Enter');
      assert.equal(await textOf(page,'#showing-count'),
        count+' von 135 Einträgen angezeigt');
      assert.equal(await textOf(page,'#metric-total'),'135');
      if(count<135){
        assert.equal(await page.evaluate(()=>document.activeElement?.id),'load-more');
      } else {
        const end=await page.evaluate(()=>({
          hidden:document.querySelector('#load-more').hidden,
          focusTag:document.activeElement?.tagName,
          focusIndex:[...document.querySelectorAll('#records-body tr')]
            .indexOf(document.activeElement),
          rowCount:document.querySelectorAll('#records-body tr').length
        }));
        assert.equal(end.hidden,true);
        assert.equal(end.focusTag,'TR');
        assert.equal(end.focusIndex,120);
        assert.equal(end.rowCount,135);
      }
    }
    pass('Final keyboard pagination retains focus on first newly revealed row');

    // Microsoft/Windows high-contrast emulation: selected period and focus
    // must remain distinguishable without relying only on fill colours.
    // Puppeteer's high-level media API does not expose forced-colors.
    // DevTools Protocol does; keep test pinned to real Chromium support.
    const session=await page.createCDPSession();
    await session.send('Emulation.setEmulatedMedia',{
      features:[{name:'forced-colors',value:'active'}]
    });
    const contrast=await page.evaluate(()=>{
      const active=document.querySelector('#period-20');
      const rail=document.querySelector('#people-ranking .bar-rail');
      return {emulated:matchMedia('(forced-colors: active)').matches,
        selectedOutline:getComputedStyle(active).outlineStyle,
        railBorder:getComputedStyle(rail).borderStyle};
    });
    assert.equal(contrast.emulated,true);
    assert.notEqual(contrast.selectedOutline,'none');
    assert.notEqual(contrast.railBorder,'none');
    pass('Forced-colors mode distinguishes selected period and chart boundaries');
    await session.send('Emulation.setEmulatedMedia',{
      features:[{name:'forced-colors',value:'none'}]
    });
    await session.detach();

    await page.setViewport({width:390,height:844,deviceScaleFactor:2,
      isMobile:true,hasTouch:true});
    await page.goto(url+'?wp=21',{waitUntil:'load'});
    await readyCount(page,8);
    const srcs=await page.$$eval('#records-body a.source-link',links=>
      links.map(link=>({href:link.href,target:link.target,rel:link.rel})));
    assert.ok(srcs.length>0);
    assert.ok(srcs.every(link=>link.href.startsWith('https://dserver.bundestag.de/') &&
      link.target==='_blank' && link.rel.includes('noopener') &&
      link.rel.includes('noreferrer')));
    pass('Displayed official source links open safely');

    // Inject only a source-health response: no published sanctions dataset,
    // source monitor cache or filesystem input is changed.
    const sourceIds=[
      'scan_21.json','autopruefung_21.json','rechtsfolgen_21.json',
      'dip_live_21.json','dip_positionen_21.json','dip_prueffalle_21.json',
      'vollstaendigkeit_21.json'
    ];
    const syntheticSourceHealth=kind=>{
      const today=new Date().toISOString().slice(0,10);
      const sources=Object.fromEntries(sourceIds.map(key=>[
        key,{state:'fresh',date:today,reason:''}
      ]));
      const payload={
        schema:'wp21-health-v1',all_sources_fresh:true,
        generated_at_utc:new Date().toISOString(),sources
      };
      if(kind==='degraded'){
        sources['dip_positionen_21.json']={
          state:'missing',date:'',reason:'Missing workflow artifact'
        };
        payload.all_sources_fresh=false;
      } else if(kind==='stale'){
        payload.generated_at_utc=new Date(Date.now()-72*3600_000).toISOString();
      } else if(kind==='invalid'){
        sources['dip_prueffalle_21.json'].state='unreviewed-as-confirmed';
      } else if(kind==='future'){
        payload.generated_at_utc=new Date(Date.now()+3600_000).toISOString();
      }
      return payload;
    };
    const monitoredScenarios=[
      {kind:'fresh',state:'fresh',message:/7 von 7/},
      {kind:'degraded',state:'degraded',message:/DIP-Verfahrensschritte \(fehlt\)/},
      {kind:'stale',state:'stale',message:/Quellenüberwachung veraltet/},
      {kind:'invalid',state:'missing',message:/nicht verfügbar/},
      {kind:'future',state:'missing',message:/nicht verfügbar/}
    ];
    for(const scenario of monitoredScenarios){
      const monitored=await browser.newPage();
      const payload=syntheticSourceHealth(scenario.kind);
      try{
        await monitored.setRequestInterception(true);
        monitored.on('request',req=>{
          if(req.url().endsWith('/data/quellenstatus_21.json')){
            req.respond({status:200,contentType:'application/json',
              body:JSON.stringify(payload)});
          }else req.continue();
        });
        await monitored.goto(url+'?wp=21',{waitUntil:'load'});
        await readyCount(monitored,8);
        await monitored.waitForFunction((wanted)=>{
          const status=document.querySelector('#wp21-health');
          return status?.dataset.state===wanted &&
            !status.hidden && !status.textContent.includes('wird geladen') &&
            status.textContent.length>40;
        },{timeout:12000},scenario.state);
        const result=await monitored.evaluate(()=>({
          state:document.querySelector('#wp21-health').dataset.state,
          message:document.querySelector('#wp21-health').textContent,
          live:document.querySelector('#wp21-health').getAttribute('aria-live'),
          role:document.querySelector('#wp21-health').getAttribute('role'),
          count:document.querySelector('#metric-total').textContent.trim(),
          disclaimer:document.querySelector('#ranking-caption').textContent
        }));
        assert.equal(result.state,scenario.state);
        assert.match(result.message,scenario.message);
        assert.equal(result.live,'polite');
        assert.equal(result.role,'status');
        assert.equal(result.count,'8');
        assert.match(result.disclaimer,/nicht repräsentativ/);
        if(scenario.kind==='degraded'||scenario.kind==='invalid'){
          await monitored.addScriptTag({content:axe.source});
          const audit=await monitored.evaluate(async()=>{
            const result=await window.axe.run(document,{
              runOnly:{type:'tag',values:[
                'wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice'
              ]},
              resultTypes:['violations']
            });
            return result.violations.map(v=>({id:v.id,nodes:v.nodes.length}));
          });
          assert.deepEqual(audit,[]);
        }
        pass('Simulated '+scenario.kind+' source monitor stays truthful and counter-safe');
      }finally{await monitored.close();}
    }

    // Deliberately tamper the partial-term JSON in network transit to verify
    // fail-closed UI behavior: no historical or current number may be shown.
    const broken=await browser.newPage();
    const partial=JSON.parse(fs.readFileSync(path.join(ROOT,'data','ordnungsrufe_21.json'),'utf8'));
    partial.meta.incomplete=false;
    await broken.setRequestInterception(true);
    broken.on('request',req=>{
      if(req.url().endsWith('/data/ordnungsrufe_21.json')){
        req.respond({status:200,contentType:'application/json',body:JSON.stringify(partial)});
      }else req.continue();
    });
    await broken.goto(url+'?wp=21',{waitUntil:'load'});
    await broken.waitForFunction(
      ()=>document.querySelector('#people-ranking')?.textContent.includes('Daten konnten nicht geladen werden'),
      {timeout:12000});
    assert.equal(await textOf(broken,'#metric-total'),'—');
    assert.equal(await visible(broken,'#data-error'),true);
    assert.equal(await broken.$eval('#data-error',node=>node.getAttribute('role')),'alert');
    assert.match(await textOf(broken,'#data-error'),/keine ungeprüften Zahlen/);
    await broken.addScriptTag({content:axe.source});
    const tamperedViolations=await broken.evaluate(async()=>{
      const report=await window.axe.run(document,{
        runOnly:{type:'tag',values:[
          'wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice'
        ]},resultTypes:['violations']
      });
      return report.violations.map(v=>v.id);
    });
    assert.deepEqual(tamperedViolations,[]);
    pass('Tampered unlabelled WP21 input raises an accessible alert and blocks counts');
    await broken.close();

    // Simulated slow network: until both ledgers are verified, all interactive
    // controls must be disabled and no public count may be implied.
    const delayed=await browser.newPage();
    let unblock;
    const delayedRequest=new Promise(resolve=>{unblock=resolve;});
    try{
      await delayed.setRequestInterception(true);
      delayed.on('request',async req=>{
        if(req.url().endsWith('/data/ordnungsrufe_21.json')){
          await delayedRequest;
        }
        await req.continue();
      });
      await delayed.goto(url+'?wp=20',{waitUntil:'load'});
      const waiting=await delayed.evaluate(()=>({
        count:document.querySelector('#metric-total').textContent.trim(),
        result:document.querySelector('#result-count').textContent.trim(),
        waiting:document.querySelector('#records-body').textContent.includes('Einträge werden geladen'),
        locked:['search','group-filter','sort','reset','load-more',
                'period-20','period-21'].every(id=>document.getElementById(id).disabled)
      }));
      assert.equal(waiting.count,'—');
      assert.equal(waiting.result,'—');
      assert.equal(waiting.waiting,true);
      assert.equal(waiting.locked,true);
      unblock();
      await readyCount(delayed,135);
      assert.equal(await delayed.evaluate(()=>
        ['search','group-filter','sort','reset','load-more',
         'period-20','period-21'].every(id=>!document.getElementById(id).disabled)),true);
      pass('Delayed verified dataset keeps controls locked and counts blank until ready');
    }finally{
      unblock();
      await delayed.close();
    }

    // Real HTTP fetch failure must not be treated as a valid empty dataset.
    const missing=await browser.newPage();
    try{
      await missing.setRequestInterception(true);
      missing.on('request',req=>{
        if(req.url().endsWith('/data/ordnungsrufe_20.json') ||
           req.url().endsWith('/data/ordnungsrufe.json')){
          req.respond({status:503,contentType:'text/plain',
            body:'Temporary test-only failure'});
        }else req.continue();
      });
      await missing.goto(url+'?wp=20',{waitUntil:'load'});
      await missing.waitForFunction(()=>!document.querySelector('#data-error').hidden,
        {timeout:10000});
      const blocked=await missing.evaluate(()=>({
        total:document.querySelector('#metric-total').textContent.trim(),
        result:document.querySelector('#result-count').textContent.trim(),
        sourceLinks:document.querySelectorAll('#records-body a.source-link').length,
        locked:['search','group-filter','sort','reset','load-more',
                'period-20','period-21'].every(id=>document.getElementById(id).disabled)
      }));
      assert.equal(blocked.total,'—');
      assert.equal(blocked.result,'—');
      assert.equal(blocked.sourceLinks,0);
      assert.equal(blocked.locked,true);
      pass('HTTP source outage fails closed without zero counts or official links');
    }finally{await missing.close();}

    // These are temporary interception-only mutations, never writes to
    // either protected published dataset. Prove failures in each legislature.
    const immutableInputs=[
      {
        name:'WP20 missing official personal discrepancy',
        path:'ordnungsrufe.json',
        tamper:payload=>{
          payload.meta.official_beatrix_von_storch=
            payload.meta.verified_beatrix_von_storch;
        }
      },
      {
        name:'WP20 unauthorised source origin',
        path:'ordnungsrufe.json',
        tamper:payload=>{
          payload.records[0].source='https://example.invalid/fake.pdf#page=1';
        }
      },
      {
        name:'WP21 count and evidence mismatch',
        path:'ordnungsrufe_21.json',
        tamper:payload=>{payload.meta.count+=1;}
      }
    ];
    for(const bad of immutableInputs){
      const compromised=await browser.newPage();
      const tampered=JSON.parse(fs.readFileSync(
        path.join(ROOT,'data',bad.path),'utf8'));
      bad.tamper(tampered);
      try{
        await compromised.setRequestInterception(true);
        compromised.on('request',req=>{
          if(req.url().endsWith('/data/'+bad.path)){
            req.respond({status:200,contentType:'application/json',
              body:JSON.stringify(tampered)});
          } else req.continue();
        });
        await compromised.goto(url+'?wp='+(
          bad.path==='ordnungsrufe.json'?'20':'21'),{waitUntil:'load'});
        await compromised.waitForFunction(()=>
          !document.querySelector('#data-error').hidden,{timeout:10000});
        assert.equal(await textOf(compromised,'#metric-total'),'—');
        assert.equal(await textOf(compromised,'#result-count'),'—');
        assert.match(await textOf(compromised,'#data-error'),/keine ungeprüften Zahlen/);
        const stateBefore=await compromised.evaluate(()=>({
          inputs:['search','group-filter','sort','reset','load-more',
                  'period-20','period-21'].every(id=>document.getElementById(id).disabled),
          notesHidden:document.querySelector('#wp20-note').hidden&&
            document.querySelector('#wp21-note').hidden,
          metric:document.querySelector('#metric-total').textContent.trim()
        }));
        assert.equal(stateBefore.inputs,true);
        assert.equal(stateBefore.notesHidden,true);
        await compromised.$eval('#search',node=>{
          node.value='Stephan';
          node.dispatchEvent(new Event('input',{bubbles:true}));
        });
        assert.equal(await textOf(compromised,'#result-count'),'—');
        assert.equal(await textOf(compromised,'#metric-total'),'—');
        assert.equal(await compromised.$eval('#records-body',el=>
          el.querySelectorAll('a.source-link').length),0);
        pass('Fail-closed verified dataset: '+bad.name);
      }finally{await compromised.close();}
    }
    assert.deepEqual(browserErrors,[],'Uncaught browser JavaScript exceptions');
    pass('No uncaught JavaScript errors in valid views');
    const report={schema:'ordnungsrufe-v1-browser-smoke-v1',
      result:'pass',checks:steps,
      viewports:['1366x900 desktop WP20','390x844 mobile WP21',
        '320x720 narrow WP20'],
      legal_effect_inferred:false,counter_files_changed:false,
      screenshots:['desktop_wp20.png','mobile_wp21.png','narrow_wp20.png'],
      source_health_on_render:HAS_PUBLISHED_HEALTH
        ? 'generated_manifest_displayed' : 'missing_manifest_disclosed_in_PR_preview',
      publication:'none_PR_only'};
    fs.writeFileSync(path.join(OUT,'report.json'),JSON.stringify(report,null,2)+'\n');
    console.log('V1_BROWSER_SMOKE_PASS',steps.length,'checks',
      'no publication, 135/123 historical, 8 partial 21st');
  }catch(error){
    fs.writeFileSync(path.join(OUT,'report.json'),
      JSON.stringify({schema:'ordnungsrufe-v1-browser-smoke-v1',result:'fail',steps,
        error:String(error)},null,2)+'\n');
    console.error('V1_BROWSER_SMOKE_FAILURE',error);
    process.exitCode=1;
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
