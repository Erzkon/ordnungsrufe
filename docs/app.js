'use strict';

const ITEMS_PER_PAGE = 15;
const GROUP_NAMES = {
  'Die Linke': 'Die Linke (Fraktion und Gruppe)',
  'Die Linke (Gruppe)': 'Die Linke (Fraktion und Gruppe)',
};

const $ = (id) => document.getElementById(id);
const state = { records: [], visible: ITEMS_PER_PAGE };

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
    const k = mapper(row);
    map.set(k, (map.get(k) || 0) + 1);
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
    button.setAttribute('aria-label', `${name}: ${count} Ordnungsrufe. Einträge anzeigen`);
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
  const filtered = state.records.filter((row) => {
    const matchesSearch = !search || normalized(row.person).includes(search) || String(row.session).includes(search);
    const matchesGroup = !group || (group === 'Die Linke (Fraktion und Gruppe)'
      ? (row.group === 'Die Linke' || row.group === 'Die Linke (Gruppe)')
      : row.group === group);
    return matchesSearch && matchesGroup;
  });
  const sort = $('sort').value;
  filtered.sort((a, b) => {
    if (sort === 'person') return a.person.localeCompare(b.person, 'de') || b.date.localeCompare(a.date);
    return (sort === 'oldest' ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date))
      || a.person.localeCompare(b.person, 'de');
  });
  return filtered;
}
function renderRecords() {
  const rows = filteredRecords();
  const shown = rows.slice(0, state.visible);
  $('result-count').textContent = rows.length;
  $('showing-count').textContent = `${shown.length} von ${rows.length} Einträgen angezeigt`;
  $('load-more').hidden = shown.length >= rows.length;
  $('empty-state').hidden = rows.length !== 0;
  const body = $('records-body');
  body.replaceChildren();
  for (const item of shown) {
    const tr = document.createElement('tr');
    tr.append(el('td', 'date', dateDE(item.date)), el('td', 'person', item.person),
      el('td', 'group', item.group), el('td', 'session', `20/${String(item.session).padStart(3, '0')}`));
    const cell = document.createElement('td');
    const link = el('a', 'source-link', 'Protokoll ↗');
    link.href = item.source;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', `Plenarprotokoll 20/${String(item.session).padStart(3, '0')} für ${item.person} öffnen`);
    cell.append(link);
    tr.append(cell);
    body.append(tr);
  }
}
function addOptions(groups) {
  const select = $('group-filter');
  for (const name of groups) {
    const option = el('option', '', name);
    option.value = name;
    select.append(option);
  }
  if (groups.includes('Die Linke') || groups.includes('Die Linke (Gruppe)')) {
    const option = el('option', '', 'Die Linke (Fraktion + Gruppe)');
    option.value = 'Die Linke (Fraktion und Gruppe)';
    select.append(option);
  }
}
function initialize(payload) {
  if (!Array.isArray(payload.records) || !payload.meta || payload.records.length !== payload.meta.count) {
    throw new Error('Unvollständiger Datenexport');
  }
  state.records = payload.records;
  $('metric-total').textContent = payload.meta.count;
  $('metric-events').textContent = payload.meta.events;
  $('metric-people').textContent = payload.meta.people;
  $('metric-rescinded').textContent = payload.meta.rescinded_excluded;
  const groupNames = [...new Set(state.records.map((row) => row.group))].sort((a, b) => a.localeCompare(b, 'de'));
  addOptions(groupNames);
  ranking('people-ranking', counted(state.records, (row) => row.person).slice(0, 10), 'person');
  ranking('group-ranking', counted(state.records, (row) => GROUP_NAMES[row.group] || row.group), 'group');
  for (const id of ['search', 'group-filter', 'sort']) {
    $(id).addEventListener(id === 'search' ? 'input' : 'change', () => {
      state.visible = ITEMS_PER_PAGE;
      renderRecords();
    });
  }
  $('reset').addEventListener('click', () => {
    $('search').value = '';
    $('group-filter').value = '';
    $('sort').value = 'newest';
    state.visible = ITEMS_PER_PAGE;
    renderRecords();
  });
  $('load-more').addEventListener('click', () => {
    state.visible += ITEMS_PER_PAGE;
    renderRecords();
  });
  renderRecords();
}

fetch('./data/ordnungsrufe.json', { cache: 'no-cache' })
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(initialize)
  .catch((err) => {
    console.error('Ordnungsruf-Daten konnten nicht geladen werden:', err);
    $('people-ranking').textContent = 'Die Daten konnten nicht geladen werden.';
    $('group-ranking').textContent = 'Die Daten konnten nicht geladen werden.';
    $('records-body').replaceChildren(el('tr', '', ''));
    const td = el('td', '', 'Die Daten konnten nicht geladen werden. Bitte die Seite erneut laden.');
    td.colSpan = 5;
    $('records-body').firstElementChild.append(td);
    $('result-count').textContent = '0';
    $('showing-count').textContent = 'Keine Daten verfügbar';
  });
