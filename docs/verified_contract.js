'use strict';

// Reviewed ledger contract for the public 1.0 website. This file is loaded
// BEFORE app.js; automatic XML/DIP hints must never enter ranking records.
function validatePublishedDataset(period, payload) {
  const invalid = reason => { throw new Error('Ungültige geprüfte Daten: ' + reason); };
  if (!['20', '21'].includes(period) || !payload || typeof payload !== 'object' ||
      !payload.meta || typeof payload.meta !== 'object' ||
      !Array.isArray(payload.records) || payload.records.length > 2000)
    invalid('Struktur');
  const meta = payload.meta;
  if (meta.legislature !== Number(period) || meta.provisional !== true ||
      !Number.isInteger(meta.count) || meta.count < 1 || meta.count !== payload.records.length ||
      !Number.isInteger(meta.events) || meta.events < 1 || meta.events > meta.count ||
      !Number.isInteger(meta.people) || meta.people < 1 || meta.people > meta.count ||
      !Number.isInteger(meta.rescinded_excluded) || meta.rescinded_excluded < 0 ||
      typeof meta.snapshot_date !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(meta.snapshot_date) ||
      !Number.isFinite(Date.parse(meta.snapshot_date))) invalid('Metadaten');
  if (period === '21' && (meta.incomplete !== true ||
      !/(unvollständig|keine vollständige statistik)/i.test(meta.note || ''))) invalid('Teilmenge nicht gekennzeichnet');
  if (period === '20' && (meta.official_total !== meta.count ||
      !Number.isInteger(meta.official_beatrix_von_storch) ||
      !Number.isInteger(meta.verified_beatrix_von_storch) ||
      meta.official_beatrix_von_storch <= meta.verified_beatrix_von_storch))
    invalid('Amtliche Personendifferenz ohne Warnung');
  const events = new Set();
  const people = new Set();
  const earliest = period === '20' ? '2021-10-26' : '2025-03-25';
  for (const row of payload.records) {
    if (!row || typeof row !== 'object' ||
        typeof row.event_id !== 'string' || !/^[A-Za-z0-9_-]{5,90}$/.test(row.event_id) ||
        !Number.isInteger(row.session) || row.session < 1 || row.session > 450 ||
        typeof row.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(row.date) ||
        !Number.isFinite(Date.parse(row.date)) || row.date < earliest ||
        row.date > meta.snapshot_date ||
        typeof row.person !== 'string' || !row.person.trim() || row.person.length > 120 ||
        typeof row.group !== 'string' || !row.group.trim() || row.group.length > 120 ||
        typeof row.source !== 'string') invalid('Einzelbeleg');
    const filename = period + String(row.session).padStart(3, '0');
    const pdf = new RegExp('^https://dserver\\.bundestag\\.de/btp/' +
      period + '/' + filename + '\\.pdf#page=[1-9]\\d*$');
    if (!pdf.test(row.source)) invalid('Nichtamtlicher oder falscher Protokolllink');
    events.add(row.event_id);
    people.add(row.person);
  }
  if (events.size !== meta.events || people.size !== meta.people)
    invalid('Ereignisse/Personen inkonsistent');
  return payload;
}

if (typeof module !== 'undefined' && module.exports)
  module.exports = { validatePublishedDataset };
