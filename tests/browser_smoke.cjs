'use strict';

// Real browser smoke of the PR-only static site. Never deploys or edits ledgers.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const os=require('node:os');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const puppeteer=require('puppeteer-core');

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

    await page.focus('#load-more');
    await page.keyboard.press('Enter');
    assert.equal(await textOf(page,'#showing-count'),'30 von 135 Einträgen angezeigt');
    assert.equal(await page.evaluate(()=>document.activeElement?.id),'load-more');
    assert.equal(await textOf(page,'#metric-total'),'135');
    pass('Keyboard load-more preserves focus and verified total');

    // Microsoft/Windows high-contrast emulation: selected period and focus
    // must remain distinguishable without relying only on fill colours.
    await page.emulateMediaFeatures([{name:'forced-colors',value:'active'}]);
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
    await page.emulateMediaFeatures([{name:'forced-colors',value:'none'}]);

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
    pass('Tampered unlabelled WP21 input blocks both rankings');
    await broken.close();
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
