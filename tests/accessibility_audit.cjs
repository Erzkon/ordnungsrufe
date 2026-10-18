'use strict';
// Real rendered accessibility audit. Review-only: no counters, source data or deploy mutation.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {execFileSync}=require('node:child_process');
const puppeteer=require('puppeteer-core');
const axe=require('axe-core');

const ROOT=path.resolve(process.env.V1_BROWSER_DOCROOT || path.join(__dirname,'..','docs'));
const OUT=path.resolve(process.env.V1_ACCESSIBILITY_OUT || '.audit/browser_smoke/accessibility');
const ENFORCE=process.env.AXE_ENFORCE==='1';
const TAGS=['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice'];

function chromePath(){
  for(const candidate of [process.env.CHROME_BIN,'/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable','/usr/bin/chromium']){
    if(candidate && fs.existsSync(candidate))return candidate;
  }
  for(const name of ['google-chrome','chromium']){
    try{return execFileSync('which',[name],{encoding:'utf8'}).trim();}catch(_){}
  }
  throw new Error('Chrome/Chromium not installed');
}
function localServer(){
  return new Promise(resolve=>{
    const server=http.createServer((req,res)=>{
      try{
        const relative=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname)
          .replace(/^\/+/,'')||'index.html';
        const file=path.resolve(ROOT,relative);
        if(!file.startsWith(ROOT+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){
          res.writeHead(404);res.end('Missing');return;
        }
        const ext=path.extname(file);
        res.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript',
          '.json':'application/json','.css':'text/css','.svg':'image/svg+xml'}[ext]||'text/plain')+'; charset=utf-8',
          'Cache-Control':'no-store'});
        fs.createReadStream(file).pipe(res);
      }catch(_){res.writeHead(400);res.end('Bad request');}
    });
    server.listen(0,'127.0.0.1',()=>resolve({server,url:'http://127.0.0.1:'+server.address().port+'/'}));
  });
}
async function inspectAccessibilityTree(page,period){
  // These names and roles are computed by Chromium's accessibility engine.
  // This checks browser semantics, not speech output from NVDA/VoiceOver.
  const cdp=await page.createCDPSession();
  try{
    await cdp.send('DOM.enable');
    await cdp.send('Accessibility.enable');
    const root=(await cdp.send('DOM.getDocument',{depth:1})).root.nodeId;
    async function read(selector){
      const matched=await cdp.send('DOM.querySelector',{nodeId:root,selector});
      if(!matched.nodeId)throw new Error('AX_NODE_MISSING '+selector);
      const details=await cdp.send('Accessibility.getPartialAXTree',{
        nodeId:matched.nodeId,fetchRelatives:false
      });
      const node=details.nodes.find(n=>!n.ignored&&n.role?.value);
      if(!node)throw new Error('AX_NODE_IGNORED '+selector);
      const props=Object.fromEntries((node.properties||[]).map(p=>[
        p.name,p.value?.value
      ]));
      return {role:node.role.value,name:node.name?.value||'',properties:props};
    }
    const main=await read('#inhalt');
    const chosen=await read('#period-'+period);
    const other=await read('#period-'+(period==='20'?'21':'20'));
    const live=await read('#period-announcement');
    const statusText=await page.$eval('#period-announcement',el=>el.textContent||'');
    const search=await read('#search');
    const group=await read('#group-filter');
    const source=await read('#records-body a.source-link');
    const ranking=await read('#people-ranking .bar-row');
    const table=await read('.table-scroller');
    const checks={
      main:main.role==='main',
      chosen:chosen.role==='button'&&chosen.properties.pressed==='true',
      other:other.role==='button'&&other.properties.pressed==='false',
      switchStatus:live.role==='status'&&live.properties.live==='polite'&&
        statusText.includes(period+'. Wahlperiode')&&
        (period!=='21'||statusText.includes('Unvollständige Auswahl')),
      search:search.role==='searchbox'&&search.name.includes('PERSON ODER SITZUNG'),
      group:group.role==='combobox'&&group.name.includes('ZUGEHÖRIGKEIT'),
      source:source.role==='link'&&source.name.includes('Protokoll')&&
        source.name.includes('Sitzung'),
      ranking:ranking.role==='button'&&ranking.name.includes('Einträge anzeigen'),
      table:table.role==='region'&&table.name.includes('Horizontale Maßnahmen-Tabelle')
    };
    const failed=Object.entries(checks).filter(([,ok])=>!ok).map(([name])=>name);
    const snapshot={period,checks,statusText,main,chosen,other,live,search,group,source,ranking,table};
    if(failed.length)throw new Error('ACCESSIBILITY_TREE_MISMATCH '+
      JSON.stringify({failed,snapshot}));
    return snapshot;
  } finally {await cdp.detach();}
}

async function auditPage(browser,url,period,width,height){
  const page=await browser.newPage();
  try {
    await page.setViewport({width,height,deviceScaleFactor:width<600?2:1,
      isMobile:width<600,hasTouch:width<600});
    if(width===320)await page.emulateMediaFeatures([
      {name:'prefers-reduced-motion',value:'reduce'}
    ]);
    await page.goto(url+'?wp='+period,{waitUntil:'load'});
    await page.waitForFunction(expected=>{
      return document.querySelector('#metric-total')?.textContent.trim()===expected &&
        document.querySelector('#records-body')?.querySelectorAll('tr').length>0;
    },{timeout:18000},period==='20'?'135':'8');
    await page.waitForFunction(()=>{
      const el=document.querySelector('#wp21-health');
      return el && (el.hidden || !el.textContent.includes('wird geladen'));
    },{timeout:12000});
    // WCAG 1.4.10 reflow proxy: at 320 CSS pixels, content must not widen
    // the document. A scrollable, keyboard-focusable data table is exempt.
    const reflow=await page.evaluate(()=>{
      const doc=document.documentElement;
      const table=document.querySelector('.table-scroller');
      const button=document.querySelector('.hero-actions .button');
      return {
        viewport:doc.clientWidth,documentWidth:doc.scrollWidth,
        tableScrollable:table.scrollWidth>table.clientWidth,
        tableFocusable:table.tabIndex===0,
        reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches,
        scrollBehavior:getComputedStyle(doc).scrollBehavior,
        buttonTransition:getComputedStyle(button).transitionDuration
      };
    });
    if(reflow.documentWidth>reflow.viewport+3){
      throw new Error('WCAG reflow horizontal document overflow: '+
        JSON.stringify({period,width,...reflow}));
    }
    if(width===320 && (!reflow.reducedMotion || reflow.scrollBehavior!=='auto' ||
      reflow.buttonTransition!=='0s')){
      throw new Error('Reduced-motion preference not respected: '+
        JSON.stringify({period,width,...reflow}));
    }
    if(width<=390 && (!reflow.tableScrollable || !reflow.tableFocusable)){
      throw new Error('Mobile records table must stay scrollable and keyboard focusable');
    }
    const semantics=await inspectAccessibilityTree(page,period);
    await page.addScriptTag({content:axe.source});
    const result=await page.evaluate(async tags=>window.axe.run(document,{
      runOnly:{type:'tag',values:tags},
      resultTypes:['violations','incomplete','passes','inapplicable']
    }),TAGS);
    const sample=rule=>({
      id:rule.id,impact:rule.impact,description:rule.help,
      helpUrl:rule.helpUrl,count:rule.nodes.length,
      nodes:rule.nodes.slice(0,90).map(node=>({
        target:node.target,html:node.html.slice(0,280),
        failureSummary:node.failureSummary?.slice(0,420)||null
      }))
    });
    let filteredState=null;
    if(width===1366||width===390){
      // Run the same WCAG rules after live filtering changes the DOM.
      const query='Kein solches Mitglied: Axe-Leerzustand';
      await page.click('#search');
      await page.type('#search',query);
      await page.waitForFunction(()=>document.querySelector('#result-count')?.textContent==='0',
        {timeout:6000});
      const empty=await page.evaluate(()=>({
        focus:document.activeElement?.id,
        emptyVisible:!document.querySelector('#empty-state').hidden,
        total:document.querySelector('#metric-total').textContent.trim(),
        displayed:document.querySelector('#showing-count').textContent.trim()
      }));
      if(empty.focus!=='search'||!empty.emptyVisible||empty.total!==(period==='20'?'135':'8')){
        throw new Error('A11Y_FILTERED_STATE_INVALID '+JSON.stringify({period,width,...empty}));
      }
      const changed=await page.evaluate(async tags=>window.axe.run(document,{
        runOnly:{type:'tag',values:tags},
        resultTypes:['violations','incomplete']
      }),TAGS);
      filteredState={
        state:'empty-search',total:empty.total,focused:empty.focus,
        violationRules:changed.violations.map(sample),
        incompleteRules:changed.incomplete.map(sample)
      };
      if(changed.violations.length){
        // Do not throw before persisting a report; keep fail-closed via
        // violationsTotal/ENFORCE after both normal and dynamic rules run.
        console.log('A11Y_FILTERED_AXE_VIOLATIONS',JSON.stringify({
          period,width,violations:filteredState.violationRules.map(v=>v.id)
        }));
      } else {
        console.log('AXE_DYNAMIC_EMPTY_PASS',JSON.stringify({
          period,width,violations:0,incomplete:changed.incomplete.length
        }));
      }
    }
    return {
      viewport:width+'x'+height,
      period,
      filteredState,
      incomplete_21st:period==='21',
      reflow,
      semantics,
      checkedRules:result.violations.length+result.passes.length+result.incomplete.length,
      violations:result.violations.map(sample),
      incomplete:result.incomplete.map(sample),
      violationNodes:result.violations.reduce((n,v)=>n+v.nodes.length,0)
    };
  } finally {await page.close();}
}
async function main(){
  fs.mkdirSync(OUT,{recursive:true});
  const {server,url}=await localServer();
  let browser;
  try{
    browser=await puppeteer.launch({headless:true,executablePath:chromePath(),
      args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
    // 640px ~ desktop 200% CSS reflow; 320px ~ desktop 400% CSS reflow.
    // These viewports are proxies, not an actual Chrome optical-zoom audit.
    const targets=[
      ['20',1366,900],['21',1366,900],
      ['20',640,900],['21',640,900],
      ['20',390,844],['21',390,844],
      ['20',320,720],['21',320,720]
    ];
    const results=[];
    for(const [period,width,height] of targets){
      const result=await auditPage(browser,url,period,width,height);
      results.push(result);
      console.log('AXE_VIEW',JSON.stringify({
        period,width,height,reflow:result.reflow,
        semantics:Object.keys(result.semantics.checks),
        violations:result.violations.map(v=>({
          id:v.id,impact:v.impact,count:v.count,targets:v.nodes.map(n=>n.target)
        })),incomplete:result.incomplete.map(v=>({
          id:v.id,impact:v.impact,count:v.count,targets:v.nodes.slice(0,12).map(n=>n.target)
        }))
      }));
    }
    const violations=results.flatMap(x=>[
      ...x.violations.map(v=>({
        period:x.period,viewport:x.viewport,state:'base',...v
      })),
      ...(x.filteredState?.violationRules||[]).map(v=>({
        period:x.period,viewport:x.viewport,state:'empty-search',...v
      }))
    ]);
    const report={schema:'ordnungsrufe-axe-accessibility-v1',enforce:ENFORCE,
      analysis_only:true,statistic_files_changed:false,
      ruleTags:TAGS,views:results,violationsTotal:violations.length,
      reflowChecks:results.length,
      reducedMotionChecks:results.filter(x=>x.reflow.reducedMotion).length,
      accessibilityTreeChecks:results.reduce((n,x)=>n+
        Object.keys(x.semantics.checks).length,0),
      filteredStateChecks:results.filter(x=>x.filteredState).length,
      violationNodes:results.reduce((n,v)=>n+v.violationNodes,0),
      manualScreenReaderReviewStillRequired:true};
    fs.writeFileSync(path.join(OUT,'axe_report.json'),JSON.stringify(report,null,2)+'\n');
    const summary=[
      '# Axe automated accessibility review',
      'Views: '+results.length+'; WCAG A/AA and best-practice tags',
      'Violations (rules × views): '+report.violationsTotal+
        ', affected node observations: '+report.violationNodes,
      ...violations.map(v=>'- '+v.viewport+' WP'+v.period+' '+v.id+' ('+v.impact+'): '+
        v.count+' node(s) '+v.nodes.map(n=>n.target.join(' ')).join(', ')),
      '',
      'These automated results do not establish WCAG conformance or replace manual screen-reader testing.'
    ];
    fs.writeFileSync(path.join(OUT,'summary.md'),summary.join('\n')+'\n');
    console.log('AXE_AUDIT_SUMMARY',JSON.stringify({
      views:results.length,reflowChecks:report.reflowChecks,
      reducedMotionChecks:report.reducedMotionChecks,
      accessibilityTreeChecks:report.accessibilityTreeChecks,
      filteredStateChecks:report.filteredStateChecks,
      violations:report.violationsTotal,
      nodes:report.violationNodes,enforced:ENFORCE
    }));
    if(ENFORCE&&violations.length)process.exitCode=1;
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
}
main().catch(error=>{console.error('AXE_AUDIT_ERROR',error);process.exitCode=1;});
