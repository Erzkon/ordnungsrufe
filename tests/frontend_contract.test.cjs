'use strict';

const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {validatePublishedDataset} = require('../docs/verified_contract.js');

const dir = path.join(__dirname,'..','docs','data');
const load = period => JSON.parse(fs.readFileSync(
  path.join(dir,period === '20' ? 'ordnungsrufe.json' : 'ordnungsrufe_21.json'),
  'utf8'
));
const clone = data => JSON.parse(JSON.stringify(data));

test('both real approved ledger JSON snapshots pass the client-side contract', () => {
  for (const period of ['20','21']) {
    const x=load(period);
    assert.equal(validatePublishedDataset(period,x),x);
  }
});
test('the 21st term can never silently turn into an unlabelled total', () => {
  const x=load('21');x.meta.incomplete=false;
  assert.throws(()=>validatePublishedDataset('21',x),/Teilmenge/);
});
test('public count cannot drift from verified records', () => {
  const x=load('20');x.meta.count++;
  assert.throws(()=>validatePublishedDataset('20',x),/Metadaten/);
});
test('twentieth-term published discrepancy must stay visible', () => {
  const x=load('20');x.meta.official_beatrix_von_storch=x.meta.verified_beatrix_von_storch;
  assert.throws(()=>validatePublishedDataset('20',x),/Personendifferenz/);
});
test('count cannot be substituted by a different election period', () => {
  const x=load('21');
  assert.throws(()=>validatePublishedDataset('20',x),/Metadaten/);
});
test('untrusted or wrong-sitting parliamentary PDF link is rejected', () => {
  for (const malicious of (
      'https://evil.example/btp/20/20009.pdf#page=10',
      'javascript:alert(1)',
      'https://dserver.bundestag.de/btp/21/21090.pdf#page=30',
      'https://dserver.bundestag.de/btp/20/20999.pdf#page=1'
  )) {
    const x=load('20');x.records[0].source=malicious;
    assert.throws(()=>validatePublishedDataset('20',x),/Protokolllink/);
  }
});
test('duplicates or swapped people are blocked by cross-check of metadata', () => {
  const x=load('21');x.records[0].person=x.records[1].person;
  assert.throws(()=>validatePublishedDataset('21',x),/Ereignisse\/Personen/);
});
test('invalid event/sitting/date cannot reach ranking DOM', () => {
  const mutate = [
    row => {row.session=0;},
    row => {row.event_id='';},
    row => {row.date='2030-12-01';},
    row => {row.group='';},
  ];
  for(const fn of mutate) {
    const x=load('21');fn(x.records[0]);
    assert.throws(()=>validatePublishedDataset('21',x),/Einzelbeleg/);
  }
});
test('automatic review feeds never enter the confirmed dataset contract', () => {
  const fake={meta:{legislature:21,count:1},records:[{status:'unverified_text_locations'}]};
  assert.throws(()=>validatePublishedDataset('21',fake));
});
