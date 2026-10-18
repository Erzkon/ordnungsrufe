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
    return {
      viewport:width+'x'+height,
      period,
      incomplete_21st:period==='21',
      reflow,
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
        violations:result.violations.map(v=>({
          id:v.id,impact:v.impact,count:v.count,targets:v.nodes.map(n=>n.target)
        })),incomplete:result.incomplete.map(v=>({
          id:v.id,impact:v.impact,count:v.count,targets:v.nodes.slice(0,12).map(n=>n.target)
        }))
      }));
    }
    const violations=results.flatMap(x=>x.violations.map(v=>({
      period:x.period,viewport:x.viewport,...v
    })));
    const report={schema:'ordnungsrufe-axe-accessibility-v1',enforce:ENFORCE,
      analysis_only:true,statistic_files_changed:false,
      ruleTags:TAGS,views:results,violationsTotal:violations.length,
      reflowChecks:results.length,
      reducedMotionChecks:results.filter(x=>x.reflow.reducedMotion).length,
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
