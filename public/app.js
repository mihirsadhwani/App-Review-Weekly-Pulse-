'use strict';
/* Weekly Review Pulse: single-page frontend. Talks to the FastAPI backend in main.py. */

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}️‍]/gu;
const clean = s => String(s ?? '').replace(EMOJI, '').trim();
const esc = s => clean(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const icon = (n, fill = false) => `<span class="ms${fill ? ' fill' : ''}">${n}</span>`;
const badge = (t, kind = 'secondary', ic = '') => `<span class="badge ${kind}">${ic ? icon(ic) : ''}${esc(t)}</span>`;
const usd = v => (v == null || isNaN(v)) ? '-' : (v >= 1 ? '$' + v.toFixed(2) : '$' + v.toFixed(4));
const num = v => Number(v || 0).toLocaleString('en-US');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const palette = () => [1, 2, 3, 4, 5].map(i => css('--chart-' + i));
const avg = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
const wrapLabel = (s, w = 24) => {
  const words = String(s).split(' '); const lines = []; let cur = '';
  words.forEach(word => { if ((cur + ' ' + word).trim().length > w) { if (cur) lines.push(cur); cur = word; } else cur = (cur + ' ' + word).trim(); });
  if (cur) lines.push(cur);
  return lines.join('<br>');
};
const fmtDt = iso => {
  const d = new Date(iso);
  return isNaN(d) ? '-' : d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).replace(',', '');
};
const timeAgo = iso => {
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (isNaN(secs)) return '';
  if (secs < 60) return 'just now';
  for (const [unit, n] of [['day', 86400], ['hour', 3600], ['min', 60]]) {
    if (secs >= n) { const v = Math.floor(secs / n); return `${v} ${unit}${v > 1 && unit !== 'min' ? 's' : ''} ago`; }
  }
  return '';
};
const sentiment = a => a < 2.5 ? ['Negative', 'destructive', 'trending_down'] : a < 3.5 ? ['Mixed', 'warning', 'trending_flat'] : ['Positive', 'success', 'trending_up'];
const stars = n => `<span class="stars">${[0, 1, 2, 3, 4].map(i => `<span class="ms fill${i < n ? '' : ' off'}">star</span>`).join('')}</span>`;
const notice = (kind, text) => `<div class="notice ${kind}">${icon({ ok: 'check_circle', bad: 'error', warn: 'warning', info: 'info' }[kind], true)}<span>${esc(text)}</span></div>`;
const card = (title, ic, body, desc = '') => `<div class="card"><p class="card-title">${icon(ic)}${title}</p>${desc ? `<p class="card-desc">${desc}</p>` : ''}<div class="card-body">${body}</div></div>`;
const empty = (ic, title, text) => `<div class="empty">${icon(ic)}<b>${title}</b>${text}</div>`;
const table = (headers, rows, { numCols = [], hideMobile = [], cls = '' } = {}) => {
  const c = i => `${numCols.includes(i) ? 'num ' : ''}${hideMobile.includes(i) ? 'hm' : ''}`;
  return `<div class="tbl-wrap"><table class="tbl ${cls}"><thead><tr>${headers.map((h, i) => `<th class="${c(i)}">${h}</th>`).join('')}</tr></thead><tbody>` +
    rows.map(r => `<tr>${r.map((v, i) => `<td class="${c(i)}">${v}</td>`).join('')}</tr>`).join('') + '</tbody></table></div>';
};
const kpis = items => `<div class="kpi-grid">${items.map(([ic, l, v, h]) => `<div class="kpi"><div class="kpi-top"><span class="kpi-label">${l}</span>${icon(ic)}</div><div class="kpi-value">${esc(v)}</div><div class="kpi-hint">${esc(h)}</div></div>`).join('')}</div>`;
const pageHead = (title, desc, right = '') => `<div class="page-head"><div><h1 class="page-title">${title}</h1><p class="page-desc">${desc}</p></div><div>${right}</div></div>`;
const renderMd = md => DOMPurify.sanitize(marked.parse(clean(md), { breaks: true }));
const download = (name, text, type = 'text/plain') => {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

// ---------------------------------------------------------------------------
// API client and persistence
// ---------------------------------------------------------------------------
let ACCESS = '';
try { ACCESS = sessionStorage.getItem('pulse_key') || ''; } catch (e) { /* storage blocked */ }

async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (ACCESS) headers['X-Access-Key'] = ACCESS;
  let res;
  try { res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined }); }
  catch (e) { throw new Error('Network error. Check your connection and try again.'); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON body */ }
  if (res.status === 401) {
    ACCESS = ''; try { sessionStorage.removeItem('pulse_key'); } catch (e) { /* ignore */ }
    if (S.config && S.config.authRequired) renderLogin();
    throw new Error('Access key required.');
  }
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === 'string' ? d : d ? JSON.stringify(d) : res.status === 504 ? 'The request timed out.' : `Request failed (${res.status}).`);
  }
  return data;
}

const LS_RUNS = 'pulse_runs_v1';
const local = {
  all() { try { return JSON.parse(localStorage.getItem(LS_RUNS) || '[]'); } catch (e) { return []; } },
  save(bundle) {
    let arr = local.all().filter(x => x.id !== bundle.id); arr.unshift(bundle); arr = arr.slice(0, 10);
    while (arr.length) { try { localStorage.setItem(LS_RUNS, JSON.stringify(arr)); return; } catch (e) { arr.pop(); } }
  },
};
const SUMMARY = ['id', 'started_at', 'finished_at', 'source', 'weeks', 'status', 'review_count', 'raw_count', 'theme_count', 'tokens', 'cost_usd', 'error', 'calls'];
const summarize = b => Object.fromEntries(SUMMARY.map(k => [k, b[k] ?? null]));

async function loadRuns() {
  const localAll = local.all();
  let server = [];
  try { server = (await api('/api/runs')).runs || []; } catch (e) { /* server history is optional */ }
  const byId = new Map();
  server.forEach(r => byId.set(r.id, r));
  localAll.forEach(b => byId.set(b.id, summarize(b)));
  S.runs = [...byId.values()].sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''));
  const latest = S.runs.find(r => r.status === 'completed');
  S.current = latest ? await getBundle(latest.id) : null;
}
async function getBundle(id) {
  const l = local.all().find(b => b.id === id);
  if (l) return l;
  try { return await api('/api/runs/' + encodeURIComponent(id)); } catch (e) { return null; }
}
async function saveRun(bundle) {
  local.save(bundle);
  try { await api('/api/runs/' + encodeURIComponent(bundle.id), { method: 'PUT', body: bundle }); } catch (e) { /* local copy is enough */ }
}

// ---------------------------------------------------------------------------
// State and shell
// ---------------------------------------------------------------------------
const S = {
  config: null, runs: [], current: null, flash: '', timers: [],
  live: { auto: false, count: 50, rating: 'All', seen: null, fresh: new Set(), data: [], updated: null, error: '' },
  pipeline: { running: false, states: {}, source: 'Play Store', csv: '', csvName: '' },
};
const STEPS = [['collect', 'Collect reviews'], ['clean', 'Clean and scrub PII'], ['analyze', 'Discover and classify themes'],
  ['insight', 'Select quotes and actions'], ['pulse', 'Compose weekly pulse']];
const NAV = [
  ['Analyze', [['overview', 'Overview', 'dashboard'], ['reviews', 'Reviews', 'rate_review'], ['report', 'Report', 'description']]],
  ['Operate', [['pipeline', 'Pipeline', 'play_circle'], ['history', 'Run history', 'history']]],
];

function clearTimers() { S.timers.forEach(clearInterval); S.timers = []; }
const view = () => $('#view');

function shell() {
  const dark = document.documentElement.dataset.theme === 'dark';
  $('#app').innerHTML = `
  <div class="shell">
    <div class="backdrop" id="backdrop"></div>
    <aside class="sidebar" id="sidebar">
      <div class="brand"><div class="mark">${icon('monitoring')}</div><div><div class="brand-title">Weekly Review Pulse</div><div class="brand-sub">Groww Mutual Fund</div></div></div>
      ${NAV.map(([g, items]) => `<div class="nav-label">${g}</div>` + items.map(([id, label, ic]) =>
        `<a class="nav-link" href="#/${id}" data-page="${id}">${icon(ic)}<span>${label}</span>${id === 'reviews' ? '<span class="pill live">LIVE</span>' : ''}${id === 'history' ? '<span class="pill count" id="runs-count"></span>' : ''}</a>`).join('')).join('')}
      <div class="sidebar-foot">
        <div class="switch-row" id="theme-toggle"><span class="left">${icon('dark_mode')}Dark mode</span><span class="switch${dark ? ' on' : ''}"></span></div>
        <div class="powered">Powered by Google Gemini</div>
      </div>
    </aside>
    <main class="main">
      <div class="topbar"><button class="icon-btn" id="menu-btn" aria-label="Open menu">${icon('menu')}</button><span class="topbar-title">Weekly Review Pulse</span></div>
      <div class="container" id="view"></div>
    </main>
  </div>`;
  $('#menu-btn').onclick = () => toggleMenu();
  $('#backdrop').onclick = () => toggleMenu(false);
  $('#theme-toggle').onclick = () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('pulse_theme', next); } catch (e) { /* ignore */ }
    $('#theme-toggle .switch').classList.toggle('on', next === 'dark');
    route();
  };
  $$('.nav-link').forEach(a => a.addEventListener('click', () => toggleMenu(false)));
}
function toggleMenu(open) {
  const sb = $('#sidebar'); const on = open ?? !sb.classList.contains('open');
  sb.classList.toggle('open', on); $('#backdrop').classList.toggle('show', on);
}
function updateNav(page) {
  $$('.nav-link').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  const c = $('#runs-count'); if (c) { c.textContent = S.runs.length || ''; c.style.display = S.runs.length ? '' : 'none'; }
}
function flash() { const f = S.flash; S.flash = ''; return f ? notice('ok', f) : ''; }

function tabs(root, defs, onChange) {
  const bar = $('.tabs', root);
  const open = id => {
    $$('button', bar).forEach(b => b.classList.toggle('on', b.dataset.tab === id));
    $$('.tab-pane', root).forEach(p => { p.hidden = p.dataset.tab !== id; });
    if (onChange) onChange(id);
  };
  $$('button', bar).forEach(b => b.onclick = () => open(b.dataset.tab));
  open(defs[0][0]);
}
const tabBar = defs => `<div class="tabs">${defs.map(([id, label, ic]) => `<button data-tab="${id}">${icon(ic)}${label}</button>`).join('')}</div>`;

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------
function plot(id, traces, layout = {}, height = 280) {
  const el = document.getElementById(id); if (!el) return;
  const base = {
    height, margin: { t: 10, b: 10, l: 10, r: 10 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Manrope, sans-serif', size: 12, color: css('--foreground') },
    hoverlabel: { bgcolor: css('--card'), bordercolor: css('--border'), font: { family: 'Manrope, sans-serif', color: css('--foreground') } },
  };
  Plotly.newPlot(el, traces, { ...base, ...layout }, { displayModeBar: false, responsive: true });
}
const axis = () => ({ showgrid: true, gridcolor: css('--border'), zeroline: false, automargin: true, tickfont: { color: css('--muted-foreground') } });
const noaxis = () => ({ showgrid: false, zeroline: false, automargin: true, tickfont: { color: css('--muted-foreground') } });
const chartCard = (title, ic, id, desc = '', h = 280) => `<div class="card"><p class="card-title">${icon(ic)}${title}</p>${desc ? `<p class="card-desc">${desc}</p>` : ''}<div class="chart" id="${id}" style="height:${h}px"></div></div>`;

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------
function pageOverview() {
  const b = S.current;
  const last = S.runs.find(r => r.status === 'completed');
  const headRight = last ? badge(`Last run ${fmtDt(last.finished_at)}`, 'outline', 'schedule') : badge('No runs yet', 'outline');
  let html = pageHead('Overview', 'Customer feedback themes from Google Play reviews of the Groww Mutual Fund app.', headRight) + flash();
  if (!b || !b.themes || !b.themes.length) {
    view().innerHTML = html + card('Overview', 'insights', empty('inbox', 'No analysis yet', 'Open Pipeline in the sidebar and run your first analysis.'));
    return;
  }
  const themes = b.themes;
  const ratingsOf = t => (t.reviews || []).map(r => r.rating).filter(x => typeof x === 'number');
  const all = themes.flatMap(ratingsOf);
  const total = themes.reduce((s, t) => s + (t.review_count || 0), 0) || 1;
  const negShare = all.length ? all.filter(x => x <= 2).length / all.length * 100 : 0;
  const colors = themes.map((_, i) => palette()[i % 5]);
  html += kpis([
    ['rate_review', 'Reviews analysed', num(b.review_count), 'After cleaning and PII scrubbing'],
    ['category', 'Themes', String(themes.length), 'Discovered by Gemini'],
    ['star', 'Average rating', all.length ? avg(all).toFixed(2) : '-', 'Out of 5'],
    ['warning', 'Negative reviews', all.length ? Math.round(negShare) + '%' : '-', 'Rated 1 or 2 stars'],
  ]);
  html += `<div class="grid-2">${chartCard('Theme distribution', 'donut_large', 'ch-donut', 'Share of classified reviews by theme.', 380)}${chartCard('Sentiment mix by theme', 'sentiment_satisfied', 'ch-mix', 'Share of negative, neutral and positive ratings inside each theme.', 380)}</div>`;
  html += `<div class="grid-2">${chartCard('Average rating by theme', 'star', 'ch-avg', 'Lower is worse. Red is below 2.5, amber below 3.5.', 340)}${chartCard('Review volume over time', 'show_chart', 'ch-vol', 'Reviews with average rating.', 340)}</div>`;
  html += `<div class="grid-3-1">${chartCard('Rating distribution', 'bar_chart', 'ch-dist', '', 240)}${chartCard('Negative review share', 'warning', 'ch-gauge', 'Ratings of 1 or 2 stars.', 240)}</div>`;
  html += card('Theme breakdown', 'category', `<div class="tgrid">${themes.map((t, i) => {
    const r = ratingsOf(t); const pct = (t.review_count || 0) / total * 100;
    const [sl, sk, si] = r.length ? sentiment(avg(r)) : ['No ratings', 'secondary', 'remove'];
    let q = (t.quotes || [''])[0] || ''; if (q.length > 150) q = q.slice(0, 150).trimEnd() + '...';
    return `<div class="tcard"><div class="tcard-top"><span class="theme-dot" style="background:${colors[i]}"></span><span class="theme-name">${esc(t.label)}</span></div>
      <div class="tcard-stats"><div><span class="tcard-n">${t.review_count || 0}</span><span class="tcard-l">mentions</span></div><div><span class="tcard-n">${Math.round(pct)}%</span><span class="tcard-l">of reviews</span></div>${badge(sl, sk, si)}</div>
      <div class="progress"><span style="width:${pct.toFixed(1)}%;background:${colors[i]}"></span></div><p class="theme-desc">${esc(t.description || '')}</p>${q ? `<div class="quote">&ldquo;${esc(q)}&rdquo;</div>` : ''}</div>`;
  }).join('')}</div>`, 'Each theme with its volume, sentiment and a representative quote.');
  if ((b.actions || []).length) {
    html += card('Product action ideas', 'lightbulb', `<div class="agrid">${b.actions.map((a, i) => `<div class="agrid-item"><div class="action-n">${i + 1}</div><p class="action-title">${esc(a.title)}</p><p class="action-body">${esc(a.rationale)}</p></div>`).join('')}</div>`, 'Three prioritised recommendations derived from the themes above.');
  }
  view().innerHTML = html;

  const labels = themes.map(t => t.label); const wl = labels.map(l => wrapLabel(l));
  plot('ch-donut', [{ type: 'pie', labels, values: themes.map(t => t.review_count || 0), hole: .66, sort: false, marker: { colors, line: { color: css('--card'), width: 3 } },
    textinfo: 'percent', textfont: { color: '#fff', size: 11 }, hovertemplate: '%{label}<br>%{value} reviews (%{percent})<extra></extra>' }],
  { showlegend: true, legend: { orientation: 'h', x: .5, xanchor: 'center', y: -.05, font: { size: 11 } },
    annotations: [{ text: `<b>${total}</b><br><span style="font-size:11px">reviews</span>`, showarrow: false, font: { size: 24 } }] }, 380);
  const mix = (fn) => themes.map(t => { const r = ratingsOf(t); return r.length ? r.filter(fn).length / r.length * 100 : 0; });
  plot('ch-mix', [['Negative (1-2)', mix(x => x <= 2), css('--destructive')], ['Neutral (3)', mix(x => x === 3), css('--warning')], ['Positive (4-5)', mix(x => x >= 4), css('--success')]]
    .map(([name, x, color]) => ({ type: 'bar', orientation: 'h', y: wl, x, name, marker: { color }, hovertemplate: '%{y}<br>' + name + ': %{x:.0f}%<extra></extra>' })),
  { barmode: 'stack', legend: { orientation: 'h', y: -.15, font: { size: 11 } }, xaxis: { range: [0, 100], ticksuffix: '%', ...axis() }, yaxis: { autorange: 'reversed', ...noaxis() } }, 380);
  const avgs = themes.map(t => avg(ratingsOf(t)));
  plot('ch-avg', [{ type: 'bar', orientation: 'h', y: wl, x: avgs, marker: { color: avgs.map(a => a < 2.5 ? css('--destructive') : a < 3.5 ? css('--warning') : css('--success')) },
    text: avgs.map(a => a.toFixed(2)), textposition: 'outside', textfont: { color: css('--foreground') }, hovertemplate: '%{y}: %{x:.2f}<extra></extra>' }],
  { xaxis: { range: [0, 5.5], ...axis() }, yaxis: { autorange: 'reversed', ...noaxis() } }, 340);
  // volume over time
  const dated = themes.flatMap(t => t.reviews || []).filter(r => r.review_date && typeof r.rating === 'number');
  const days = new Set(dated.map(r => r.review_date.slice(0, 10)));
  const keyLen = days.size > 1 ? 10 : 13;
  const groups = {};
  dated.forEach(r => { const k = r.review_date.slice(0, keyLen); (groups[k] = groups[k] || []).push(r.rating); });
  const keys = Object.keys(groups).sort();
  const lab = k => keyLen === 10 ? new Date(k).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : k.slice(11) + ':00';
  plot('ch-vol', [{ type: 'bar', x: keys.map(lab), y: keys.map(k => groups[k].length), name: 'Reviews', marker: { color: css('--chart-1') } },
    { type: 'scatter', mode: 'lines+markers', x: keys.map(lab), y: keys.map(k => avg(groups[k])), name: 'Avg rating', yaxis: 'y2', line: { color: css('--warning'), width: 2.5 } }],
  { xaxis: { type: 'category', ...noaxis() }, yaxis: axis(), yaxis2: { overlaying: 'y', side: 'right', range: [0, 5], dtick: 1, showgrid: false, tickfont: { color: css('--muted-foreground') } },
    legend: { orientation: 'h', y: -.2, font: { size: 11 } } }, 340);
  const dist = [1, 2, 3, 4, 5].map(n => all.filter(x => x === n).length);
  plot('ch-dist', [{ type: 'bar', x: [1, 2, 3, 4, 5].map(n => n + ' star'), y: dist, marker: { color: [css('--destructive'), css('--destructive'), css('--warning'), css('--success'), css('--success')] } }],
    { xaxis: noaxis(), yaxis: axis() }, 240);
  plot('ch-gauge', [{ type: 'indicator', mode: 'gauge+number', value: negShare, number: { suffix: '%', font: { size: 34 } },
    gauge: { axis: { range: [0, 100], tickvals: [0, 50, 100], ticksuffix: '%', tickfont: { color: css('--muted-foreground'), size: 10 } }, bar: { color: css('--destructive'), thickness: .3 }, bgcolor: css('--muted'), borderwidth: 0 } }], {}, 240);
}

// ---------------------------------------------------------------------------
// Reviews (live feed + analysis dataset)
// ---------------------------------------------------------------------------
function pageReviews() {
  view().innerHTML = pageHead('Reviews', 'Live Google Play reviews, and the dataset used in the latest analysis.') + flash() +
    `<div id="rv-root">${tabBar([['live', 'Live feed', 'sensors'], ['data', 'Analysis dataset', 'database']])}
      <div class="tab-pane" data-tab="live">${liveShell()}</div><div class="tab-pane" data-tab="data">${datasetShell()}</div></div>`;
  tabs($('#rv-root'), [['live'], ['data']]);
  wireLive(); wireDataset();
  if (!S.live.data.length) liveLoad(false);
  else liveDraw();
  setupLiveTimer();
}
function liveShell() {
  return `<div class="live-controls">
    <label class="toggle-field" id="live-auto-wrap"><span class="switch${S.live.auto ? ' on' : ''}" id="live-switch"></span>Auto-refresh every 30 seconds</label>
    <div class="field"><label>Reviews</label><select class="select" id="live-count">${[25, 50, 100].map(n => `<option${n === S.live.count ? ' selected' : ''}>${n}</option>`).join('')}</select></div>
    <div class="field"><label>Rating</label><select class="select" id="live-rating">${['All', 1, 2, 3, 4, 5].map(n => `<option${String(n) === String(S.live.rating) ? ' selected' : ''}>${n}</option>`).join('')}</select></div>
    <button class="btn" id="live-refresh">${icon('refresh')}Refresh now</button></div><div id="live-card"></div>`;
}
function wireLive() {
  $('#live-auto-wrap').onclick = () => { S.live.auto = !S.live.auto; $('#live-switch').classList.toggle('on', S.live.auto); setupLiveTimer(); liveDraw(); };
  $('#live-count').onchange = e => { S.live.count = +e.target.value; S.live.seen = null; S.live.fresh = new Set(); liveLoad(true); };
  $('#live-rating').onchange = e => { S.live.rating = e.target.value; liveDraw(); };
  $('#live-refresh').onclick = () => liveLoad(true);
}
function setupLiveTimer() {
  clearTimers();
  if (S.live.auto) S.timers.push(setInterval(() => { if (!document.hidden && location.hash.includes('reviews')) liveLoad(true); }, 30000));
}
async function liveLoad(fresh) {
  try {
    const d = await api(`/api/live?count=${S.live.count}${fresh ? '&fresh=true' : ''}`);
    const ids = d.reviews.map(r => r.reviewId);
    if (S.live.seen) ids.filter(i => !S.live.seen.has(i)).forEach(i => S.live.fresh.add(i));
    S.live.seen = new Set([...(S.live.seen || []), ...ids]);
    S.live.data = d.reviews; S.live.updated = new Date(); S.live.error = '';
  } catch (e) { S.live.error = e.message; }
  liveDraw();
}
function liveDraw() {
  const el = $('#live-card'); if (!el) return;
  if (S.live.error) { el.innerHTML = notice('bad', S.live.error); return; }
  if (!S.live.data.length) { el.innerHTML = card('Latest Google Play reviews', 'sensors', '<p class="muted">Loading reviews...</p>'); return; }
  const data = S.live.data; const rows = data.filter(r => S.live.rating === 'All' || r.rating === +S.live.rating);
  const a = avg(data.map(r => r.rating)); const low = data.filter(r => r.rating <= 2).length;
  const status = `<span class="live-dot${S.live.auto ? '' : ' off'}"></span>${S.live.auto ? 'Live' : 'Paused'}`;
  const nNew = S.live.fresh.size;
  el.innerHTML = card(`Latest Google Play reviews ${nNew ? badge(nNew + ' new this session', 'secondary') : ''}`, 'sensors',
    rows.length ? rows.map(r => `<div class="rv"><div class="rv-head">${stars(r.rating)}${S.live.fresh.has(r.reviewId) ? badge('New', 'success') : ''}<span class="rv-meta">${timeAgo(r.review_date)} &middot; ${esc(new Date(r.review_date).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }))}</span></div><p class="rv-text">${esc(r.review_text)}</p></div>`).join('')
      : empty('search_off', 'No reviews match', 'Try a different rating filter.'),
    `${status} &middot; updated ${S.live.updated.toLocaleTimeString('en-GB')} &middot; newest ${data.length} reviews, average ${a.toFixed(2)}, ${low} rated 2 stars or below. Fetched directly from Google Play and not stored.`);
}
function datasetShell() {
  const b = S.current;
  if (!b || !b.themes) return card('Analysis dataset', 'database', empty('inbox', 'No analysis yet', 'Run the pipeline to see the dataset used in the analysis.'));
  const incl = b.review_count || 0; const raw = b.raw_count || incl;
  const themes = [...new Set(b.themes.map(t => t.label))];
  return kpis([['inbox', 'Collected', num(raw), 'Raw reviews from the last fetch'], ['check_circle', 'Included', num(incl), 'Used for theme analysis'], ['filter_alt', 'Filtered out', num(Math.max(raw - incl, 0)), 'Low-signal, duplicate or outside window']]) +
    `<div class="filters"><div class="field"><label>Search</label><input class="input" id="ds-q" placeholder="Search review text"></div>
      <div class="field"><label>Rating</label><select class="select" id="ds-rating">${['All', 1, 2, 3, 4, 5].map(n => `<option>${n}</option>`).join('')}</select></div>
      <div class="field"><label>Theme</label><select class="select" id="ds-theme"><option>All</option>${themes.map(t => `<option>${esc(t)}</option>`).join('')}</select></div></div>
    <div class="card"><div id="ds-table"></div><p class="caption" id="ds-count"></p><div class="actions-row"><button class="btn" id="ds-csv">${icon('download')}Download CSV</button></div></div>`;
}
function wireDataset() {
  const b = S.current; if (!b || !b.themes || !$('#ds-q')) return;
  const rows = b.themes.flatMap(t => (t.reviews || []).map(r => ({ date: (r.review_date || '').slice(0, 10), rating: r.rating, text: clean(r.review_text), theme: t.label })));
  let view_ = rows;
  const draw = () => {
    const q = $('#ds-q').value.toLowerCase(), rt = $('#ds-rating').value, th = $('#ds-theme').value;
    view_ = rows.filter(r => (!q || r.text.toLowerCase().includes(q)) && (rt === 'All' || r.rating === +rt) && (th === 'All' || r.theme === th));
    $('#ds-table').innerHTML = table(['Date', 'Rating', 'Review', 'Theme'], view_.slice(0, 300).map(r => [esc(r.date), r.rating, esc(r.text), esc(r.theme)]), { numCols: [1], cls: 'rev' });
    $('#ds-count').textContent = `Showing ${view_.length} of ${rows.length} included reviews. Personal details are masked.`;
  };
  ['input', 'change'].forEach(ev => ['#ds-q', '#ds-rating', '#ds-theme'].forEach(s => $(s).addEventListener(ev, draw)));
  $('#ds-csv').onclick = () => download('reviews.csv', 'Date,Rating,Review,Theme\n' + view_.map(r => [r.date, r.rating, r.text, r.theme].map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n'), 'text/csv');
  draw();
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------
function pageReport() {
  const b = S.current;
  let html = pageHead('Report', 'The weekly pulse and its email draft.') + flash();
  if (!b || !b.pulse_md) { view().innerHTML = html + card('Weekly pulse', 'description', empty('description', 'No report generated', "Run the pipeline to produce this week's pulse.")); return; }
  const words = b.pulse_md.split(/\s+/).filter(Boolean).length;
  html += `<div id="rp-root">${tabBar([['pulse', 'Weekly pulse', 'article'], ['email', 'Email', 'mail']])}
    <div class="tab-pane" data-tab="pulse">${card(`Weekly pulse ${badge(words + ' words', 'secondary')}`, 'article', `<div class="md">${renderMd(b.pulse_md)}</div>
      <div class="actions-row"><button class="btn" id="dl-md">${icon('download')}Markdown</button><button class="btn" id="dl-txt">${icon('download')}Plain text</button></div>`)}</div>
    <div class="tab-pane" data-tab="email"><div class="card"><div class="field"><label>Recipient</label><input class="input" id="em-to" type="email" placeholder="${S.config.defaultRecipient ? 'Leave blank to use the default recipient' : 'name@company.com'}"></div>
      <div class="actions-row"><button class="btn" id="em-draft">${icon('edit_note')}Generate draft</button><button class="btn primary" id="em-send">${icon('send')}Send email</button></div>
      <div id="em-msg" style="margin-top:14px"></div><div id="em-out"></div></div></div></div>`;
  view().innerHTML = html;
  tabs($('#rp-root'), [['pulse'], ['email']]);
  $('#dl-md').onclick = () => download('weekly_pulse.md', b.pulse_md, 'text/markdown');
  $('#dl-txt').onclick = () => download('weekly_pulse.txt', b.pulse_txt || b.pulse_md);
  const doEmail = async send => {
    const to = $('#em-to').value.trim();
    if (send && !to && !S.config.defaultRecipient) { $('#em-msg').innerHTML = notice('warn', 'Enter a recipient to send.'); return; }
    if (send && !confirm(`Send this report${to ? ' to ' + to : ''}?`)) return;
    $('#em-draft').disabled = $('#em-send').disabled = true; $('#em-msg').innerHTML = notice('info', 'Drafting with Gemini...');
    try {
      const r = await api('/api/email', { method: 'POST', body: { pulse_md: b.pulse_md, pulse_txt: b.pulse_txt, recipient: to || null, send } });
      b.calls = (b.calls || []).concat(r.calls || []); b.tokens = (b.tokens || 0) + (r.calls || []).reduce((s, c) => s + c.prompt_tokens + c.output_tokens, 0);
      b.cost_usd = +((b.cost_usd || 0) + (r.calls || []).reduce((s, c) => s + c.cost_usd, 0)).toFixed(6); saveRun(b);
      $('#em-msg').innerHTML = send ? notice('ok', `Email sent${to ? ' to ' + to : ''}.`) : notice('info', 'Draft saved. Nothing was sent.');
      $('#em-out').innerHTML = `<p class="card-title" style="margin:14px 0 10px">${icon('mail')}Draft preview</p><div class="draft">${esc(r.draft)}</div>`;
    } catch (e) { $('#em-msg').innerHTML = notice('bad', 'Email failed: ' + e.message); }
    $('#em-draft').disabled = $('#em-send').disabled = false;
  };
  $('#em-draft').onclick = () => doEmail(false); $('#em-send').onclick = () => doEmail(true);
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------
const stepperHtml = () => STEPS.map(([k, label]) => {
  const st = S.pipeline.states[k] || 'pending';
  const g = { pending: 'radio_button_unchecked', running: 'progress_activity', done: 'check_circle', failed: 'error' }[st];
  return `<div class="step ${st}">${icon(g, st === 'done')}<span>${label}</span></div>`;
}).join('');
const drawStepper = () => { const el = $('#stepper'); if (el) el.innerHTML = stepperHtml(); };

function pagePipeline() {
  const p = S.pipeline;
  view().innerHTML = pageHead('Pipeline', 'Collect reviews, analyse them with Gemini and generate the weekly pulse.') + flash() + `
  <div class="grid-3-2"><div class="card"><p class="card-title">${icon('cloud_download')}Review ingestion</p>
    <p class="card-desc">Fetch public Google Play reviews automatically, or upload a CSV as a fallback.</p>
    <div class="seg" id="src">${['Play Store', 'CSV upload'].map(s => `<button data-s="${s}" class="${p.source === s ? 'on' : ''}">${s}</button>`).join('')}</div>
    <div class="row">
      <div class="field"><label>Review window</label><select class="select" id="win">${['Last 4 weeks', 'Last 8 weeks', 'Last 12 weeks', 'No date filter'].map((w, i) => `<option${(p.source === 'CSV upload' ? i === 3 : i === 1) ? ' selected' : ''}>${w}</option>`).join('')}</select></div>
      <div class="field" id="cnt-wrap"><label>Reviews to fetch: <span class="range-val" id="cnt-val">500</span></label><input type="range" id="cnt" min="100" max="1000" step="50" value="500"></div>
    </div>
    <div id="csv-wrap" style="margin-top:12px" hidden><label class="dropzone${p.csvName ? ' has' : ''}" id="dz">${p.csvName ? icon('description') + ' ' + esc(p.csvName) : 'Click to choose a CSV (columns: rating, review_text; optional reviewId, review_date)'}<input type="file" id="csv" accept=".csv,text/csv"></label></div>
    <div id="run-msg" style="margin-top:16px"></div>
    <div style="margin-top:14px"><button class="btn primary block" id="run">${icon('play_arrow')}Run analysis</button></div>
    ${S.config.geminiReady ? '' : '<p class="caption">Set GEMINI_API_KEY in the deployment environment to enable analysis.</p>'}</div>
    <div class="card"><p class="card-title">${icon('account_tree')}Pipeline status</p><p class="card-desc">Phases 1 to 5. Email delivery is in the Report page.</p><div id="stepper">${stepperHtml()}</div></div></div>`;
  const sync = () => {
    const csv = p.source === 'CSV upload';
    $('#cnt-wrap').hidden = csv; $('#csv-wrap').hidden = !csv;
    $$('#src button').forEach(b => b.classList.toggle('on', b.dataset.s === p.source));
    $('#run').disabled = p.running || !S.config.geminiReady || (csv && !p.csv);
  };
  $$('#src button').forEach(b => b.onclick = () => { p.source = b.dataset.s; if (p.source === 'CSV upload') $('#win').selectedIndex = 3; else $('#win').selectedIndex = 1; sync(); });
  $('#cnt').oninput = e => { $('#cnt-val').textContent = e.target.value; };
  $('#csv').onchange = e => {
    const f = e.target.files[0]; if (!f) return;
    const rd = new FileReader(); rd.onload = () => { p.csv = rd.result; p.csvName = f.name; $('#dz').classList.add('has'); $('#dz').firstChild.textContent = f.name; sync(); }; rd.readAsText(f);
  };
  $('#run').onclick = () => {
    const w = $('#win').value; const weeks = w === 'No date filter' ? null : parseInt(w.match(/\d+/)[0], 10);
    startRun({ source: p.source === 'CSV upload' ? 'csv' : 'scrape', count: +$('#cnt').value, weeks, csv: p.csv });
  };
  sync();
}

async function startRun({ source, count, weeks, csv }) {
  const p = S.pipeline; if (p.running) return;
  p.running = true; p.states = {}; drawStepper();
  const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const rec = { id: `run_${stamp.slice(0, 8)}_${stamp.slice(8)}_${Math.random().toString(16).slice(2, 6)}`, started_at: new Date().toISOString(), source, weeks, status: 'running',
    review_count: 0, raw_count: 0, theme_count: 0, tokens: 0, cost_usd: 0, error: null, calls: [] };
  const runBtn = $('#run'); if (runBtn) runBtn.disabled = true;
  const set = (k, st) => { p.states[k] = st; drawStepper(); };
  const add = r => { rec.calls.push(...(r.calls || [])); };
  let current = 'collect';
  try {
    set('collect', 'running'); const col = await api('/api/pipeline/collect', { method: 'POST', body: { source, count, csv } }); set('collect', 'done');
    current = 'clean'; set('clean', 'running'); const cl = await api('/api/pipeline/clean', { method: 'POST', body: { reviews: col.reviews, weeks } });
    if (!cl.reviews.length) throw new Error('No usable reviews remained after cleaning. Try a longer review window.');
    rec.raw_count = cl.raw_count; rec.review_count = cl.reviews.length; set('clean', 'done');
    current = 'analyze'; set('analyze', 'running'); const an = await api('/api/pipeline/analyze', { method: 'POST', body: { reviews: cl.reviews } }); add(an); set('analyze', 'done');
    current = 'insight'; set('insight', 'running'); const ins = await api('/api/pipeline/insights', { method: 'POST', body: { themes: an.themes } }); add(ins); set('insight', 'done');
    current = 'pulse'; set('pulse', 'running');
    const pu = await api('/api/pipeline/pulse', { method: 'POST', body: { themes: an.themes, insights: { themes: ins.themes, action_ideas: ins.action_ideas } } }); add(pu); set('pulse', 'done');
    const quotes = Object.fromEntries(ins.themes.map(t => [t.theme_id, t.quotes || []]));
    Object.assign(rec, { status: 'completed', theme_count: an.themes.length, themes: an.themes.map(t => ({ ...t, quotes: quotes[t.theme_id] || [] })),
      actions: ins.action_ideas || [], pulse_md: pu.markdown, pulse_txt: pu.text });
    S.flash = `Analysis complete: ${rec.review_count} reviews and ${rec.theme_count} themes. See Run history for usage and cost.`;
  } catch (e) {
    set(current, 'failed'); rec.status = 'failed'; rec.error = e.message;
    const m = $('#run-msg'); if (m) m.innerHTML = notice('bad', 'Run failed: ' + e.message);
  }
  rec.finished_at = new Date().toISOString();
  rec.tokens = rec.calls.reduce((s, c) => s + c.prompt_tokens + c.output_tokens, 0);
  rec.cost_usd = +rec.calls.reduce((s, c) => s + c.cost_usd, 0).toFixed(6);
  await saveRun(rec); await loadRuns(); p.running = false; updateNav('pipeline');
  if (rec.status === 'completed') location.hash = '#/overview'; else { const b = $('#run'); if (b) b.disabled = false; }
}

// ---------------------------------------------------------------------------
// Run history (runs + usage and cost)
// ---------------------------------------------------------------------------
function pageHistory() {
  view().innerHTML = pageHead('Run history', 'Every pipeline run with its status and volume, plus Gemini usage and API cost.') + flash() +
    `<div id="hs-root">${tabBar([['runs', 'Runs', 'history'], ['usage', 'Usage and cost', 'payments']])}<div class="tab-pane" data-tab="runs">${runsHtml()}</div><div class="tab-pane" data-tab="usage">${usageHtml()}</div></div>`;
  tabs($('#hs-root'), [['runs'], ['usage']], id => { if (id === 'usage') drawUsageCharts(); });
  const sel = $('#arch-sel');
  if (sel) { const load = async () => { const b = await getBundle(sel.value); $('#arch').innerHTML = b && b.pulse_md ? card('Archived weekly pulse', 'article', `<div class="md">${renderMd(b.pulse_md)}</div><div class="actions-row"><button class="btn" id="arch-dl">${icon('download')}Download</button></div>`) : '<p class="caption">No archived pulse found for this run.</p>';
    const d = $('#arch-dl'); if (d) d.onclick = () => download(`${sel.value}_weekly_pulse.md`, b.pulse_md, 'text/markdown'); }; sel.onchange = load; load(); }
}
function runsHtml() {
  if (!S.runs.length) return card('Runs', 'history', empty('history', 'No runs recorded', 'Completed and failed runs appear here.'));
  const st = { completed: badge('Completed', 'success', 'check_circle'), failed: badge('Failed', 'destructive', 'error'), running: badge('Running', 'warning', 'progress_activity') };
  let html = card('Runs', 'history', table(['Run', 'Started', 'Source', 'Reviews', 'Themes', 'Tokens', 'Cost', 'Status'],
    S.runs.slice(0, 25).map(r => [esc(r.id), fmtDt(r.started_at), r.source === 'csv' ? 'CSV upload' : 'Play Store', r.review_count || 0, r.theme_count || 0, num(r.tokens), usd(r.cost_usd), st[r.status] || '']),
    { numCols: [3, 4, 5, 6], hideMobile: [2, 4, 5] }));
  const done = S.runs.filter(r => r.status === 'completed');
  if (done.length) html += `<div class="field" style="margin-bottom:12px"><label>Open archived run</label><select class="select" id="arch-sel">${done.map(r => `<option>${esc(r.id)}</option>`).join('')}</select></div><div id="arch"></div>`;
  const err = S.runs.find(r => r.status === 'failed' && r.error);
  if (err) html += `<p class="caption">Most recent failure (${esc(err.id)}): ${esc(err.error)}</p>`;
  return html;
}
const allCalls = () => S.runs.flatMap(r => (r.calls || []).map(c => ({ ...c, run: r.id })));
function usageHtml() {
  const calls = allCalls(); const done = S.runs.filter(r => r.status === 'completed' && r.cost_usd);
  const avgRun = done.length ? avg(done.map(r => r.cost_usd)) : null;
  const total = calls.reduce((s, c) => s + c.cost_usd, 0); const tokens = calls.reduce((s, c) => s + c.prompt_tokens + c.output_tokens, 0);
  let html = kpis([['payments', 'Total spend', usd(total), `${num(calls.length)} API calls`], ['receipt_long', 'Average cost per run', usd(avgRun), done.length ? `Across ${done.length} priced runs` : 'No priced runs yet'],
    ['calendar_month', 'Projected monthly', avgRun ? usd(avgRun * 52 / 12) : '-', 'One weekly run, about 4.3 per month'], ['token', 'Total tokens', num(tokens), 'Input plus output, including thinking']]);
  html += card('Model pricing', 'sell', table(['Model', 'Used for', 'Input per 1M', 'Output per 1M'], S.config.pricing.map(p => [esc(p.model), esc(p.role), '$' + p.input.toFixed(2), '$' + p.output.toFixed(2)]), { numCols: [2, 3], hideMobile: [1] }), esc(S.config.pricingNote));
  if (!calls.length) return html + card('Spend breakdown', 'bar_chart', empty('payments', 'No API calls recorded', 'Run the pipeline to start tracking cost.'));
  const by = {}; calls.forEach(c => { const g = by[c.step] = by[c.step] || { n: 0, i: 0, o: 0, c: 0 }; g.n++; g.i += c.prompt_tokens; g.o += c.output_tokens; g.c += c.cost_usd; });
  const steps = Object.entries(by).sort((a, b) => b[1].c - a[1].c);
  html += `<div class="grid-2">${chartCard('Spend by step', 'bar_chart', 'ch-step', '', 260)}${chartCard('Daily spend', 'show_chart', 'ch-day', '', 260)}</div>`;
  html += card('Cost by step', 'functions', table(['Step', 'Calls', 'Input tokens', 'Output tokens', 'Cost'], steps.map(([k, g]) => [esc(k), g.n, num(g.i), num(g.o), usd(g.c)]), { numCols: [1, 2, 3, 4], hideMobile: [1, 2] }));
  html += `<details class="more"><summary>Recent API calls</summary><div style="margin-top:12px">${table(['Time', 'Step', 'Model', 'Input', 'Output', 'Cost'],
    calls.sort((a, b) => (b.ts || '').localeCompare(a.ts || '')).slice(0, 50).map(c => [fmtDt(c.ts), esc(c.step), esc(c.model), num(c.prompt_tokens), num(c.output_tokens), usd(c.cost_usd)]), { numCols: [3, 4, 5], hideMobile: [2] })}</div></details>`;
  return html + '<p class="caption">Estimates use Google\'s published prices and may differ from your invoice. Check Google AI Studio billing for the authoritative figure.</p>';
}
function drawUsageCharts() {
  const calls = allCalls(); if (!calls.length || !$('#ch-step')) return;
  const by = {}; calls.forEach(c => { by[c.step] = (by[c.step] || 0) + c.cost_usd; });
  const steps = Object.entries(by).sort((a, b) => b[1] - a[1]);
  plot('ch-step', [{ type: 'bar', orientation: 'h', y: steps.map(s => s[0]), x: steps.map(s => s[1]), marker: { color: css('--chart-1') }, hovertemplate: '%{y}: $%{x:.4f}<extra></extra>' }],
    { yaxis: { autorange: 'reversed', ...noaxis() }, xaxis: { tickprefix: '$', ...axis() } }, 260);
  const day = {}; calls.forEach(c => { const k = (c.ts || '').slice(0, 10); day[k] = (day[k] || 0) + c.cost_usd; });
  const keys = Object.keys(day).sort();
  plot('ch-day', [{ type: 'bar', x: keys.map(k => new Date(k).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })), y: keys.map(k => day[k]), marker: { color: css('--chart-2') }, hovertemplate: '%{x}: $%{y:.4f}<extra></extra>' }],
    { xaxis: { type: 'category', ...noaxis() }, yaxis: { tickprefix: '$', ...axis() } }, 260);
}

// ---------------------------------------------------------------------------
// Router, login, boot
// ---------------------------------------------------------------------------
const PAGES = { overview: pageOverview, reviews: pageReviews, report: pageReport, pipeline: pagePipeline, history: pageHistory };
function route() {
  if (!view()) return;
  clearTimers();
  const page = (location.hash.replace('#/', '') || 'overview').split('?')[0];
  const fn = PAGES[page] || pageOverview;
  updateNav(PAGES[page] ? page : 'overview');
  try { fn(); } catch (e) { view().innerHTML = notice('bad', 'Something went wrong rendering this page: ' + e.message); console.error(e); }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);

function renderLogin(msg = '') {
  $('#app').innerHTML = `<div class="container login">${card('Sign in', 'lock', `${msg ? notice('bad', msg) : ''}<div class="field"><label>Access password</label><input class="input" id="pw" type="password" autocomplete="current-password"></div>
    <div style="margin-top:14px"><button class="btn primary block" id="login">Continue</button></div>`, 'This deployment is protected. Enter the access password to continue.')}</div>`;
  const go = async () => {
    const pw = $('#pw').value;
    try { await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }) }).then(r => { if (!r.ok) throw new Error('Incorrect password.'); });
      ACCESS = pw; try { sessionStorage.setItem('pulse_key', pw); } catch (e) { /* ignore */ } boot(); }
    catch (e) { renderLogin(e.message); }
  };
  $('#login').onclick = go; $('#pw').onkeydown = e => { if (e.key === 'Enter') go(); }; $('#pw').focus();
}

async function boot() {
  try { S.config = await api('/api/config'); }
  catch (e) { $('#app').innerHTML = `<div class="container">${notice('bad', 'Could not load the app configuration: ' + e.message)}</div>`; return; }
  if (S.config.authRequired && !ACCESS) { renderLogin(); return; }
  shell();
  try { await loadRuns(); } catch (e) { /* history is optional */ }
  route();
}
boot();
