'use strict';

const ITEMS_PER_PAGE = 15;
const GROUP_NAMES = {
  'Die Linke': 'Die Linke (Fraktion und Gruppe)',
  'Die Linke (Gruppe)': 'Die Linke (Fraktion und Gruppe)',
};
const $ = id => document.getElementById(id);
const state = { datasets: {}, records: [], visible: ITEMS_PER_PAGE, period: '20' };

function normalized(value) {
  return String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('de');
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function dateDE(iso) {
  const [year, month, day] = iso.split('-');
  return `${day}.${month}.${year}`;
}
function counted(records, mapper) {
  const map = new Map();
  for (const row of records) {
    const key = mapper(row);
    map.set(key, (map.get(key) || 0) + 1);
  }
  return [...map].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'de'));
}
function applyFilterAndScroll(filterName, value) {
  $('search').value = '';
  $('group-filter').value = '';
  $(filterName).value = value;
  state.visible = ITEMS_PER_PAGE;
  renderRecords();
  $('eintraege').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}
function ranking(container, entries, kind) {
  const root = $(container);
  root.replaceChildren();
  const max = entries[0]?.[1] || 1;
  entries.forEach(([name, count], index) => {
    const button = el('button', 'bar-row');
    button.type = 'button';
    button.setAttribute('aria-label', `${name}: ${count} geprüfte Ordnungsrufe. Einträge anzeigen`);
    const heading = el('span', 'bar-heading');
    heading.append(el('span', 'bar-title', `${String(index + 1).padStart(2, '0')}  ${name}`), el('span', 'bar-value', count));
    const rail = el('span', 'bar-rail');
    const fill = el('span', 'bar-fill');
    fill.style.width = `${100 * count / max}%`;
    rail.append(fill);
    button.append(heading, rail);
    button.addEventListener('click', () => applyFilterAndScroll(kind === 'person' ? 'search' : 'group-filter', name));
    root.append(button);
  });
}
function filteredRecords() {
  const search = normalized($('search').value.trim());
  const group = $('group-filter').value;
  const result = state.records.filter(row => {
    const matchesSearch = !search || normalized(row.person).includes(search) ||
      String(row.session).includes(search) || `${state.period}/${String(row.session).padStart(3, '0')}`.includes(search);
    const matchesGroup = !group || (group === 'Die Linke (Fraktion und Gruppe)'
      ? row.group === 'Die Linke' || row.group === 'Die Linke (Gruppe)'
      : row.group === group);
    return matchesSearch && matchesGroup;
  });
  const sort = $('sort').value;
  result.sort((a,b) => {
    if (sort === 'person') return a.person.localeCompare(b.person,'de') || b.date.localeCompare(a.date);
    return (sort === 'oldest' ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date)) ||
      a.person.localeCompare(b.person,'de');
  });
  return result;
}
function renderRecords() {
  const rows = filteredRecords();
  const shown = rows.slice(0,state.visible);
  $('result-count').textContent = String(rows.length);
  $('showing-count').textContent = `${shown.length} von ${rows.length} Einträgen angezeigt`;
  $('load-more').hidden = shown.length >= rows.length;
  $('empty-state').hidden = rows.length !== 0;
  const body = $('records-body');
  body.replaceChildren();
  for (const item of shown) {
    const tr = document.createElement('tr');
    tr.append(el('td','date',dateDE(item.date)),el('td','person',item.person),
      el('td','group',item.group),el('td','session',`${state.period}/${String(item.session).padStart(3,'0')}`));
    const cell = document.createElement('td');
    const link = el('a','source-link','Protokoll ↗');
    link.href = item.source;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label',`Plenarprotokoll ${state.period}/${String(item.session).padStart(3,'0')} für ${item.person} öffnen`);
    cell.append(link);
    tr.append(cell);
    body.append(tr);
  }
}
function addOptions(groups) {
  const select = $('group-filter');
  select.replaceChildren(el('option','','Alle Zugehörigkeiten'));
  select.firstChild.value = '';
  for (const name of groups) {
    const option = el('option','',name);
    option.value = name;
    select.append(option);
  }
  if (groups.includes('Die Linke (Gruppe)')) {
    const option = el('option','','Die Linke (Fraktion + Gruppe)');
    option.value = 'Die Linke (Fraktion und Gruppe)';
    select.append(option);
  }
}
function activate(period) {
  const payload = state.datasets[period];
  if (!payload) return;
  state.period = period;
  state.records = payload.records;
  state.visible = ITEMS_PER_PAGE;
  $('search').value = '';
  $('sort').value = 'newest';
  for (const p of ['20','21']) {
    const button = $(`period-${p}`);
    button.setAttribute('aria-pressed',String(p === period));
    button.classList.toggle('is-active',p === period);
  }
  $('hero-period').textContent = `${period}. WAHLPERIODE`;
  $('section-period').textContent = period === '20' ? '2021—2025' : 'SEIT 2025 · NOCH UNVOLLSTÄNDIG';
  $('metric-total').textContent = payload.meta.count;
  $('metric-events').textContent = payload.meta.events;
  $('metric-people').textContent = payload.meta.people;
  $('metric-rescinded').textContent = payload.meta.rescinded_excluded;
  $('metric-foot-total').textContent = period === '20'
    ? '20. Wahlperiode · 2021–2025' : '21. Wahlperiode · Geprüfte Teilmenge, keine Gesamtzahl';
  $('metric-total-label').textContent = period === '20' ? 'WIRKSAME ORDNUNGSRUFE' : 'BISHER EINZELN GEPRÜFT';
  $('metric-foot-rescinded').textContent = period === '20'
    ? 'Nicht in der Gesamtzahl enthalten' : 'In dieser Teilmenge; kein Vollständigkeitsanspruch';
  $('ranking-caption').textContent = period === '20'
    ? 'Alle Angaben basieren auf den einzeln belegten, wirksamen Maßnahmen der 20. Wahlperiode.'
    : 'Ausschließlich die bisher manuell geprüften Beispiele. Diese Ranglisten sind noch nicht repräsentativ.';
  $('footer-period').textContent = period === '20'
    ? '20. WAHLPERIODE · DATENSTAND 14.10.2026'
    : '21. WAHLPERIODE · UNVOLLSTÄNDIGE ERFASSUNG';
  $('wp20-note').hidden = period !== '20';
  $('wp21-note').hidden = period !== '21';
  $('wp21-scan').hidden = period !== '21';
  $('wp21-activity').hidden = period !== '21';
  $('period-methodology').textContent = period === '20' ? '20. Wahlperiode' : '20. und 21. Wahlperiode';
  const groupNames=[...new Set(state.records.map(row=>row.group))].sort((a,b)=>a.localeCompare(b,'de'));
  addOptions(groupNames);
  ranking('people-ranking',counted(state.records,row=>row.person).slice(0,10),'person');
  ranking('group-ranking',counted(state.records,row=>GROUP_NAMES[row.group]||row.group),'group');
  renderRecords();
  const url = new URL(window.location.href);
  url.searchParams.set('wp',period);
  window.history.replaceState(null,'',url.pathname+url.search+url.hash);
}
async function showScan() {
  const box = $('wp21-scan-detail');
  try {
    const response = await fetch('./data/scan_21.json',{cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const scan = await response.json();
    if (scan.status !== 'bereit' || !Number.isInteger(scan.untersuchte_sitzungen)) throw new Error('Scan unvollständig');
    const timestamp = new Date(scan.zuletzt_geprueft_utc);
    box.textContent = `Automatischer Quellencheck: ${scan.untersuchte_sitzungen} Plenarprotokolle durchsucht, ${scan.textstellen_zur_pruefung} Textstellen zur manuellen Prüfung markiert. Letzter erfolgreicher Suchlauf: ${timestamp.toLocaleDateString('de-DE')}. Diese Hinweise sind keine bestätigten Maßnahmen.`;
  } catch (_) {
    box.textContent = 'Noch kein erfolgreicher automatischer Suchlauf veröffentlicht. Die einzeln geprüften Einträge bleiben weiterhin abrufbar.';
  }
}
async function showActivityFeed() {
  const container = $('wp21-activity-items');
  const label = $('wp21-activity-meta');
  const classNames = {
    possible_grant: 'Mögliche Erteilung',
    named_group_confirmation: 'Mögliche Gruppenvergabe',
    appeal_or_retrospective: 'Einspruch oder Rückblick',
    warning_or_conditional: 'Warnung oder Vorbehalt'
  };
  try {
    const response = await fetch('./data/hinweise_21.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const feed = await response.json();
    const meta = feed.meta;
    if (!meta || meta.legislature !== 21 || meta.status !== 'unverified_text_locations' ||
        !Array.isArray(feed.items) || feed.items.length > 40 ||
        !Number.isInteger(meta.sessions_scanned) || !Number.isInteger(meta.all_text_locations)) {
      throw new Error('Ungültiges Feed-Format');
    }
    const timestamp = new Date(meta.last_scan_utc);
    if (!Number.isFinite(timestamp.getTime())) throw new Error('Ungültiges Prüfdatum');
    label.textContent = `Letzter erfolgreicher Suchlauf: ${timestamp.toLocaleDateString('de-DE')}. ` +
      `${meta.all_text_locations} Suchtreffer in ${meta.sessions_scanned} Protokollen. ` +
      'Angezeigte Textstellen sind keine bestätigten Ordnungsrufe.';
    container.replaceChildren();
    for (const item of feed.items) {
      if (!Number.isInteger(item.session) || item.session < 1 || item.session > 450 ||
          !Object.prototype.hasOwnProperty.call(classNames, item.kind) ||
          item.source !== `https://dserver.bundestag.de/btp/21/21${String(item.session).padStart(3,'0')}.pdf` ||
          typeof item.excerpt !== 'string' || item.excerpt.length > 220 ||
          !/^\d{4}-\d{2}-\d{2}$/.test(item.date)) throw new Error('Ungültiger Suchtreffer');
      const card = el('li','activity-item');
      const top = el('div','activity-top');
      top.append(el('span','activity-type',classNames[item.kind]),
                 el('span','activity-date',`${dateDE(item.date)} · 21/${String(item.session).padStart(3,'0')}`));
      const snippet = el('p','activity-excerpt',item.excerpt);
      const link = el('a','source-link','Plenarprotokoll öffnen ↗');
      link.href = item.source;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      card.append(top,snippet,link);
      container.append(card);
    }
    if (!feed.items.length) container.append(el('li','activity-empty','Keine prüfbedürftigen Treffer im veröffentlichten Suchlauf.'));
  } catch (error) {
    console.warn('Aktivitätsfeed nicht verfügbar',error);
    label.textContent = 'Noch kein erfolgreicher Suchlauf verfügbar. Die bestätigten Daten bleiben unverändert.';
    container.replaceChildren();
  }
}

async function showAutoTriage() {
  const status = $('wp21-triage-detail');
  try {
    const response = await fetch('./data/autopruefung_21.json', {cache:'no-store'});
    if (!response.ok) throw new Error('Kein Prüfbericht');
    const audit = await response.json();
    const fields = ['gescannte_sitzungen','bereits_einzeln_belegte_massnahmen',
      'davon_referenz_person_sitzung_erkannt','davon_referenz_person_sitzung_nicht_erkannt',
      'offene_personenhinweise','referenz_person_sitzung_kombinationen',
      'referenz_mehrfachvergaben_ohne_parser_nachweis','automatisch_freigegebene_ordnungsrufe'];
    if (audit.wahlperiode !== 21 || audit.status !== 'automatische_vorpruefung_ohne_freigabe' ||
        fields.some(key => !Number.isInteger(audit[key]) || audit[key] < 0) ||
        audit.automatisch_freigegebene_ordnungsrufe !== 0 ||
        audit.davon_referenz_person_sitzung_erkannt + audit.davon_referenz_person_sitzung_nicht_erkannt !== audit.referenz_person_sitzung_kombinationen) {
      throw new Error('Ungültiger Prüfbericht');
    }
    status.textContent = 'Automatischer Qualitätsabgleich: ' +
      audit.davon_referenz_person_sitzung_erkannt + ' von ' +
      audit.referenz_person_sitzung_kombinationen + ' eindeutigen Person/Sitzung-Kombinationen wiedererkannt (aus ' +
      audit.bereits_einzeln_belegte_massnahmen + ' einzeln belegten Maßnahmen); ' +
      audit.offene_personenhinweise + ' weitere automatische Personenhinweise zur Prüfung. ' +
      'Dies ist kein Nachweis für richtige Einzelzuordnung. Keine automatische Freigabe für die Ranglisten.';
  } catch (_) {
    status.textContent = 'Automatischer Personenabgleich noch nicht verfügbar. Die belegten Zähler bleiben unverändert.';
  }
}

async function showLegalSignals() {
  const box = $('wp21-legal-detail');
  try {
    const response = await fetch('./data/rechtsfolgen_21.json', {cache:'no-store'});
    if (!response.ok) throw new Error('Kein Bericht');
    const data = await response.json();
    if (data.wahlperiode !== 21 || data.status !== 'ungepruefte_rechtsfolgen_hinweise' ||
        !Number.isInteger(data.textstellen_gesamt) || data.textstellen_gesamt < 0 ||
        data.automatisch_zurueckgenommene_massnahmen !== 0 ||
        data.automatisch_zurueckgewiesene_einsprueche !== 0) {
      throw new Error('Ungültige Daten');
    }
    const timestamp = new Date(data.letzter_Quellenscan_utc);
    if (!Number.isFinite(timestamp.getTime())) throw new Error('Ungültiges Datum');
    box.textContent = 'Einspruchs- und Rücknahmeprüfung: ' +
      data.textstellen_gesamt + ' mögliche Rechtsfolgen-Textstellen in amtlichen Protokollen, ' +
      'Stand ' + timestamp.toLocaleDateString('de-DE') +
      '. Keine automatische Rücknahme oder endgültige Einspruchsentscheidung; Fundstellen müssen geprüft werden.';
  } catch (_) {
    box.textContent = 'Einspruchs- und Rücknahmeprüfung noch nicht verfügbar. Bestätigte Einträge bleiben unverändert.';
  }
}

async function showDipSample() {
  const label = $('wp21-dip-detail');
  try {
    const response = await fetch('./data/dip_kontrolle_21.json', {cache:'no-store'});
    if (!response.ok) throw new Error('DIP-Vergleich noch nicht verfügbar');
    const data = await response.json();
    const counts = ['dip_protokoll_personen_kombinationen',
      'dip_dokumentierte_urspruengliche_rufe_in_stichprobe',
      'davon_in_teilbestand_einzeln_belegt', 'noch_nicht_in_teilbestand_belegt'];
    if (data.wahlperiode !== 21 ||
        data.status !== 'ausgewaehlte_dip_positivkontrollen_ohne_gesamtzahl' ||
        !/^\d{4}-\d{2}-\d{2}$/.test(data.dip_referenzstand) ||
        counts.some(name => !Number.isInteger(data[name]) || data[name] < 0) ||
        data.davon_in_teilbestand_einzeln_belegt + data.noch_nicht_in_teilbestand_belegt !==
          data.dip_dokumentierte_urspruengliche_rufe_in_stichprobe ||
        data.automatisch_freigegebene_ordnungsrufe !== 0) throw new Error('Ungültiger DIP-Vergleich');
    let status = 'Amtlicher DIP-Positivvergleich (Auswahl vom ' +
      dateDE(data.dip_referenzstand) + '): ' +
      data.davon_in_teilbestand_einzeln_belegt + ' von ' +
      data.dip_dokumentierte_urspruengliche_rufe_in_stichprobe +
      ' dort dokumentierten ursprünglichen Erteilungen in unserer einzeln geprüften Auswahl; ' +
      data.noch_nicht_in_teilbestand_belegt + ' noch nicht aufgenommen. ' +
      'Keine vollständige amtliche Gesamtzahl und keine Aussage über spätere Rücknahmen.';
    if (data.parser_geprueft === true &&
        Number.isInteger(data.dip_person_sitzung_per_parser_gefunden) &&
        Number.isInteger(data.dip_person_sitzung_vom_parser_verpasst)) {
      status += ' Parser erkennt ' + data.dip_person_sitzung_per_parser_gefunden +
        ' von ' + data.dip_protokoll_personen_kombinationen +
        ' DIP-Person/Sitzung-Kombinationen; das ist kein Nachweis einer einzelnen Maßnahme.';
    }
    label.textContent = status;
  } catch (_) {
    label.textContent = 'Der unabhängige DIP-Stichprobenvergleich ist derzeit nicht verfügbar. Die bestätigten Zahlen bleiben unverändert.';
  }
}

function start() {
  for(const id of ['search','group-filter','sort']) {
    $(id).addEventListener(id === 'search' ? 'input' : 'change',() => {state.visible=ITEMS_PER_PAGE;renderRecords();});
  }
  $('reset').addEventListener('click',()=>{
    $('search').value='';$('group-filter').value='';$('sort').value='newest';
    state.visible=ITEMS_PER_PAGE;renderRecords();
  });
  $('load-more').addEventListener('click',()=>{state.visible+=ITEMS_PER_PAGE;renderRecords();});
  for(const period of ['20','21']) {
    $(`period-${period}`).addEventListener('click',()=>activate(period));
  }
  Promise.all([
    fetch('./data/ordnungsrufe.json',{cache:'no-cache'}),
    fetch('./data/ordnungsrufe_21.json',{cache:'no-cache'})
  ]).then(async responses=>{
    if(responses.some(r=>!r.ok)) throw new Error('Datenabruf fehlgeschlagen');
    const [twenty,twentyOne]=await Promise.all(responses.map(r=>r.json()));
    for(const [period,payload] of [['20',twenty],['21',twentyOne]]) {
      if(!payload.meta || !Array.isArray(payload.records) || payload.meta.count !== payload.records.length
          || payload.meta.legislature !== Number(period)) throw new Error(`Datenfehler: ${period}`);
      state.datasets[period]=payload;
    }
    const initial=new URL(window.location.href).searchParams.get('wp')==='21'?'21':'20';
    activate(initial);
    showScan();
    showActivityFeed();
    showAutoTriage();
    showLegalSignals();
    showDipSample();
  }).catch(err=>{
    console.error('Daten nicht geladen',err);
    $('people-ranking').textContent='Die Daten konnten nicht geladen werden.';
    $('group-ranking').textContent='Die Daten konnten nicht geladen werden.';
    $('records-body').replaceChildren();
    const tr=el('tr','');const td=el('td','','Die Daten konnten nicht geladen werden. Bitte die Seite erneut laden.');
    td.colSpan=5;tr.append(td);$('records-body').append(tr);
  });
}
start();
