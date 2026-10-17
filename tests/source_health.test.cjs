'use strict';
const {test} = require('node:test');
const assert=require('node:assert/strict');
const {assessSourceHealth,SOURCE_LABELS}=require('../docs/source_health.js');

const NOW=Date.parse('2026-10-17T10:00:00Z');
function report(overrides={}) {
  const sources={};
  for(const key of Object.keys(SOURCE_LABELS))
    sources[key]={state:'fresh',date:'2026-10-17',reason:''};
  return {
    schema:'wp21-health-v1',
    all_sources_fresh:true,
    generated_at_utc:'2026-10-17T09:30:00+00:00',
    sources,...overrides,
  };
}
test('all seven sources must be accounted for as fresh',()=>{
  const s=assessSourceHealth(report(),NOW);
  assert.equal(s.state,'fresh');
  assert.match(s.message,/7 von 7/);
  assert.match(s.message,/keine automatische Zähleränderung/);
});
test('cached source outage shows a visible degraded status, not fake success',()=>{
  const d=report();
  d.sources['dip_live_21.json']={state:'stale',date:'2026-10-14',reason:'cached'};
  d.sources['rechtsfolgen_21.json']={state:'missing',date:'',reason:'No report'};
  d.all_sources_fresh=false;
  const x=assessSourceHealth(d,NOW);
  assert.equal(x.state,'degraded');
  assert.match(x.message,/5 von 7/);
  assert.match(x.message,/DIP-Vorgänge \(veraltet\)/);
  assert.match(x.message,/Einspruchshinweise \(fehlt\)/);
});
test('old health report cannot silently claim current sources',()=>{
  const d=report();
  d.generated_at_utc='2026-10-14T10:00:00Z';
  const x=assessSourceHealth(d,NOW);
  assert.equal(x.state,'stale');
  assert.match(x.message,/überholt/);
});
test('future source report cannot claim current health',()=>{
  const d=report();
  d.generated_at_utc='2026-10-17T11:00:00Z';
  assert.throws(()=>assessSourceHealth(d,NOW),/Prüfzeitpunkt/);
});
test('missing, unknown, malformed health entries fail closed',()=>{
  const unknown=report();
  delete unknown.sources['scan_21.json'];
  assert.throws(()=>assessSourceHealth(unknown,NOW),/Quellenstatusformat/);
  const bad=report();
  bad.sources['dip_prueffalle_21.json'].state='certified_sanctions';
  assert.throws(()=>assessSourceHealth(bad,NOW),/Quellenstatus-Eintrag/);
  const wrong=report({all_sources_fresh:false});
  assert.throws(()=>assessSourceHealth(wrong,NOW),/Widersprüchliche/);
});
test('raw health-monitor response never authorizes public counts',()=>{
  const output=assessSourceHealth(report(),NOW);
  assert.equal(output.public_counter_delta,undefined);
  assert.equal(output.automatically_confirmed_sanctions,undefined);
});
