'use strict';

// Read-only public health display for the daily Bundestag XML/DIP feed.
// This deliberately does not contain any count of legally effective grants.
const SOURCE_LABELS = Object.freeze({
  'scan_21.json':'Plenarprotokolle',
  'autopruefung_21.json':'Personen-Vorprüfung',
  'rechtsfolgen_21.json':'Einspruchshinweise',
  'dip_live_21.json':'DIP-Vorgänge',
  'dip_positionen_21.json':'DIP-Verfahrensschritte',
  'dip_prueffalle_21.json':'DIP-Prüffälle',
  'vollstaendigkeit_21.json':'Vollständigkeitsprüfung',
});
const SOURCE_STATES = new Set(['fresh','stale','missing','invalid']);
function assessSourceHealth(report, now = Date.now()) {
  if (!report || report.schema !== 'wp21-health-v1' ||
      typeof report.all_sources_fresh !== 'boolean' ||
      typeof report.generated_at_utc !== 'string' ||
      !report.sources || typeof report.sources !== 'object' ||
      Array.isArray(report.sources) ||
      Object.keys(report.sources).length !== Object.keys(SOURCE_LABELS).length)
    throw new Error('Quellenstatusformat ungültig');
  const checked = Date.parse(report.generated_at_utc);
  if (!Number.isFinite(checked) || !Number.isFinite(now) ||
      checked > now + 5 * 60 * 1000) throw new Error('Ungültiger Prüfzeitpunkt');
  const delayed = now - checked > 48 * 60 * 60 * 1000;
  const bad = [];
  let fresh = 0;
  for (const [key,label] of Object.entries(SOURCE_LABELS)) {
    const item = report.sources[key];
    if (!item || !SOURCE_STATES.has(item.state) ||
        typeof item.date !== 'string' || typeof item.reason !== 'string' ||
        (item.date && !/^\d{4}-\d{2}-\d{2}$/.test(item.date)))
      throw new Error('Quellenstatus-Eintrag ungültig');
    if (item.state === 'fresh') fresh++;
    else bad.push(label + ' (' +
      ({missing:'fehlt',invalid:'ungültig',stale:'veraltet'})[item.state] + ')');
  }
  if (report.all_sources_fresh !== (fresh === Object.keys(SOURCE_LABELS).length))
    throw new Error('Widersprüchliche Quellenfreigabe');
  const date = new Date(checked).toLocaleDateString('de-DE');
  if (delayed) {
    return {
      state:'stale',
      message:'Quellenüberwachung veraltet (letzter Bericht ' + date +
        '). Die automatischen Hinweise können überholt sein. ' +
        'Einzeln geprüfte Maßnahmen bleiben davon unberührt.',
    };
  }
  if (bad.length) {
    return {
      state:'degraded',
      message:'Automatischer Quellencheck: ' + fresh + ' von 7 Teilprüfungen aktuell. ' +
        bad.join('; ') + '. Letzte Prüfung ' + date + '. ' +
        'Keine automatische Bestätigung oder Zähleränderung.',
    };
  }
  return {
    state:'fresh',
    message:'Automatischer Quellencheck: 7 von 7 Teilprüfungen aktuell ' +
      '(Bericht vom ' + date + '). Ergebnisse bleiben unbestätigte Prüfhinweise; ' +
      'keine automatische Zähleränderung.',
  };
}

if (typeof module !== 'undefined' && module.exports)
  module.exports = {assessSourceHealth,SOURCE_LABELS};
