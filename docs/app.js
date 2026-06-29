'use strict';
const $ = (s, r = document) => r.querySelector(s);
const el = (h) => { const d = document.createElement('div'); d.innerHTML = h.trim(); return d.firstChild; };
const pct = (x) => (x == null ? '–' : Math.round(x * 100) + '%');
const flag = (iso, cls = '') =>
  `<img class="flag ${cls}" loading="lazy" alt="" src="https://flagcdn.com/${iso}.svg" onerror="this.style.visibility='hidden'">`;
const fmtDate = (s) => new Date(s + 'T12:00:00Z')
  .toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

async function load(name) {
  const r = await fetch(`data/${name}.json?t=${Date.now()}`);
  if (!r.ok) throw new Error(name);
  return r.json();
}

function probBar(p, t1, t2) {
  const [h, d, a] = p;
  return `<div class="pbar">
    <div class="ph" style="width:${h * 100}%" title="${t1} win">${h >= .12 ? pct(h) : ''}</div>
    <div class="pd" style="width:${d * 100}%" title="Draw">${d >= .12 ? 'X ' + pct(d) : ''}</div>
    <div class="pa" style="width:${a * 100}%" title="${t2} win">${a >= .12 ? pct(a) : ''}</div>
  </div>`;
}

function factorChips(fs) {
  if (!fs || !fs.length) return '';
  return `<div class="factors">` + fs.map(f =>
    `<span class="chip ${f.favors || ''}"><span class="ic">${f.icon}</span>${f.text}</span>`).join('') + `</div>`;
}

function matchCard(m, played) {
  const t1 = `<div class="team home">${flag(m.iso1)}<span class="nm">${m.team1}</span></div>`;
  const t2 = `<div class="team away">${flag(m.iso2)}<span class="nm">${m.team2}</span></div>`;
  let mid;
  if (played) {
    const [hs, as] = m.actual_score;
    const v = m.correct ? `<span class="verdict ok">✓ called</span>` : `<span class="verdict no">✗ missed</span>`;
    mid = `<div class="score">${hs}–${as}<div class="pred">pred ${m.pred_score[0]}–${m.pred_score[1]} ${v}</div></div>`;
  } else {
    mid = `<div class="vs">${m.pred_score[0]}–${m.pred_score[1]}<div class="pred" style="font-size:10px">model line</div></div>`;
  }
  const temp = m.apparent_temp != null ? `&nbsp;·&nbsp;🌡️ ${m.apparent_temp}°C` : '';
  return el(`<div class="match">
    <div class="match-top"><span class="rnd">${m.round || 'Match'}</span>
      <span>${fmtDate(m.date)} · ${m.venue || m.city || ''}${temp}</span></div>
    <div class="teams">${t1}${mid}${t2}</div>
    ${probBar(m.probs, m.team1, m.team2)}
    ${factorChips(m.factors)}
  </div>`);
}

function renderPredictions(preds) {
  const sec = $('#predictions'); sec.innerHTML = '';
  const up = preds.filter(p => !p.played).sort((a, b) => a.date.localeCompare(b.date));
  if (!up.length) { sec.appendChild(el(`<div class="note">No scheduled matches with known teams right now — knockout pairings appear here as each round is drawn. See the bracket for live odds.</div>`)); return; }
  sec.appendChild(el(`<h2 class="sec">Next ${up.length} matches — model forecast</h2>`));
  up.forEach(m => sec.appendChild(matchCard(m, false)));
}

function renderResults(results) {
  const sec = $('#results'); sec.innerHTML = '';
  sec.appendChild(el(`<h2 class="sec">Recent results — predicted vs actual <span class="delayed">scores may be delayed</span></h2>`));
  results.forEach(m => sec.appendChild(matchCard(m, true)));
}

function renderOdds(table, bracket) {
  const sec = $('#odds'); sec.innerHTML = '';
  sec.appendChild(el(`<h2 class="sec">Championship odds — ${(table[0]?.champion * 100 || 0).toFixed(0)}% favourite ${table[0]?.team || ''}</h2>`));
  table.filter(t => t.champion > 0.001).slice(0, 16).forEach((t, i) => {
    sec.appendChild(el(`<div class="odds-row">
      <div class="rk">${i + 1}</div>${flag(t.iso, 'big')}
      <div class="nm">${t.team}<small>${t.conf} · Elo ${t.elo}</small></div>
      <div class="odds-bars"><div class="subpct">final ${pct(t.reach_final)}<br>semi ${pct(t.reach_sf)}</div>
        <div class="bigpct">${(t.champion * 100).toFixed(1)}%</div></div>
    </div>`));
  });
  // bracket by round
  sec.appendChild(el(`<h2 class="sec">Knockout bracket</h2>`));
  const order = ['Round of 32', 'Round of 16', 'Quarter-final', 'Semi-final', 'Match for third place', 'Final'];
  const byRound = {}; bracket.forEach(m => (byRound[m.round] = byRound[m.round] || []).push(m));
  const grid = el(`<div class="grid2"></div>`);
  order.filter(r => byRound[r]).forEach(r => {
    const col = el(`<div class="round-col"><h3>${r}</h3></div>`);
    byRound[r].forEach(m => col.appendChild(bracketMatch(m)));
    grid.appendChild(col);
  });
  sec.appendChild(grid);
}

function bracketMatch(m) {
  const slot = (s, won) => s.placeholder
    ? `<div class="row ph"><span>${s.placeholder}</span></div>`
    : `<div class="row ${won ? 'win' : ''}"><span>${flag(s.iso)}${s.team}</span>
       <span class="od">${s.champion != null ? pct(s.champion) : ''}</span></div>`;
  let w1 = false, w2 = false;
  if (m.score) { w1 = m.score[0] >= m.score[1]; w2 = !w1; }
  const sc = m.score ? `<span class="od">${m.score[0]}–${m.score[1]}</span>` : `<span class="od">${fmtDate(m.date)}</span>`;
  return el(`<div class="bm">${slot(m.team1, w1)}${slot(m.team2, w2)}<div style="text-align:right">${sc}</div></div>`);
}

function renderStandings(groups) {
  const sec = $('#standings'); sec.innerHTML = '';
  sec.appendChild(el(`<h2 class="sec">Group stage — final tables (top 2 + 8 best 3rd advance)</h2>`));
  const grid = el(`<div class="grid2"></div>`);
  Object.entries(groups).forEach(([g, rows]) => {
    const body = rows.map((r, i) => `<tr class="${i < 2 ? 'qual' : ''}">
      <td class="tm">${flag(r.iso)}${r.team}</td><td>${r.P}</td><td>${r.W}</td>
      <td>${r.D}</td><td>${r.L}</td><td>${r.GF}:${r.GA}</td><td><b>${r.Pts}</b></td></tr>`).join('');
    grid.appendChild(el(`<div><h2 class="sec" style="margin:6px 2px">${g}</h2>
      <table><tr><th style="text-align:left">Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF:GA</th><th>Pts</th></tr>${body}</table></div>`));
  });
  sec.appendChild(grid);
}

function sparkline(series, w = 640, h = 120) {
  if (!series.length) return '';
  const xs = series.map((_, i) => i), ys = series.map(s => s.rps);
  const minY = Math.min(...ys, 0.15), maxY = Math.max(...ys, 0.25);
  const X = i => 30 + i / (xs.length - 1 || 1) * (w - 40);
  const Y = v => h - 22 - (v - minY) / (maxY - minY) * (h - 40);
  const path = series.map((s, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(s.rps).toFixed(1)}`).join(' ');
  const ref = Y(0.2282);
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%">
    <line x1="30" y1="${ref}" x2="${w}" y2="${ref}" stroke="#445" stroke-dasharray="4 4" />
    <text x="34" y="${ref - 4}" fill="#6b7796" font-size="10">naive baseline 0.228</text>
    <path d="${path}" fill="none" stroke="#18e0a0" stroke-width="2.5" />
    <text x="30" y="14" fill="#8a97b4" font-size="11">running RPS (lower = better)</text>
    <text x="${w - 4}" y="${Y(ys[ys.length - 1]) - 6}" fill="#18e0a0" font-size="12" text-anchor="end" font-weight="700">${ys[ys.length - 1].toFixed(3)}</text>
  </svg>`;
}

function calibration(bins, w = 420, h = 260) {
  const P = (v) => 30 + v * (w - 50), Q = (v) => h - 30 - v * (h - 50);
  let dots = bins.map(b => `<circle cx="${P(b.conf)}" cy="${Q(b.acc)}" r="${4 + Math.sqrt(b.n)}" fill="#4aa8ff" fill-opacity=".7" />
     <text x="${P(b.conf)}" y="${Q(b.acc) - 8 - Math.sqrt(b.n)}" fill="#8a97b4" font-size="9" text-anchor="middle">n=${b.n}</text>`).join('');
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:440px">
    <line x1="${P(0.3)}" y1="${Q(0.3)}" x2="${P(1)}" y2="${Q(1)}" stroke="#445" stroke-dasharray="4 4"/>
    <text x="${P(0.62)}" y="${Q(0.55)}" fill="#5b6" font-size="9" transform="rotate(0)">perfect calibration</text>
    ${dots}
    <text x="${w / 2}" y="${h - 6}" fill="#8a97b4" font-size="11" text-anchor="middle">predicted favourite probability</text>
    <text x="12" y="${h / 2}" fill="#8a97b4" font-size="11" text-anchor="middle" transform="rotate(-90 12 ${h / 2})">actual hit rate</text>
  </svg>`;
}

function renderAccuracy(acc) {
  const sec = $('#accuracy'); sec.innerHTML = '';
  if (!acc.n) { sec.appendChild(el(`<div class="note">No completed matches scored yet.</div>`)); return; }
  sec.appendChild(el(`<h2 class="sec">How the model is doing — ${acc.n} matches scored</h2>`));
  sec.appendChild(el(`<div class="kpis">
    <div class="kpibox"><div class="v" style="color:#18e0a0">${acc.rps}</div><div class="l">RPS (lower better)</div></div>
    <div class="kpibox"><div class="v">${(acc.accuracy * 100).toFixed(0)}%</div><div class="l">outcomes called</div></div>
    <div class="kpibox"><div class="v">${acc.n_correct}/${acc.n}</div><div class="l">correct results</div></div>
    <div class="kpibox"><div class="v">${acc.log_loss}</div><div class="l">log-loss</div></div>
    <div class="kpibox"><div class="v">${(acc.ece * 100).toFixed(1)}%</div><div class="l">calibration error</div></div>
  </div>`));
  sec.appendChild(el(`<div class="chartbox"><h3>Running prediction skill</h3>
    <p>Mean Ranked Probability Score across played matches, in date order. Below the dashed line beats a naive base-rate forecast.</p>
    ${sparkline(acc.running_rps)}</div>`));
  sec.appendChild(el(`<div class="chartbox"><h3>Calibration</h3>
    <p>When the model says a favourite has X% chance, do they win X% of the time? Dots near the diagonal = honest probabilities.</p>
    ${calibration(acc.calibration)}</div>`));
  sec.appendChild(el(`<div class="note">In-tournament sample is small (${acc.n} matches), so these wobble. The model's calibration on 3 years of held-out internationals is far tighter (ECE ≈ 1.4%) — see the Model tab.</div>`));
}

function renderModel(b) {
  const sec = $('#model'); sec.innerHTML = '';
  sec.appendChild(el(`<h2 class="sec">Benchmark — walk-forward over ${b.n_matches.toLocaleString()} internationals (${b.date_from} → ${b.date_to})</h2>`));
  const rows = Object.entries(b.models).map(([m, s]) =>
    `<tr class="${m === b.best_model ? 'qual' : ''}"><td class="tm">${m}${m === b.best_model ? ' ⭐' : ''}</td>
     <td><b>${s.rps}</b></td><td>${s.log_loss}</td><td>${s.brier}</td><td>${(s.accuracy * 100).toFixed(1)}%</td><td>${(s.ece * 100).toFixed(1)}%</td></tr>`).join('');
  sec.appendChild(el(`<table><tr><th style="text-align:left">Model</th><th>RPS</th><th>log-loss</th><th>Brier</th><th>Acc</th><th>ECE</th></tr>${rows}</table>`));
  sec.appendChild(el(`<p class="note">Rolling-origin validation (train only on the past, predict the next window, advance). RPS is the standard score for ordered home/draw/away forecasts — lower is better; a naive base-rate model sits at ${b.models.baseline.rps}.</p>`));
  sec.appendChild(el(`<h2 class="sec">Does each feature actually help? (ablation)</h2>`));
  const ab = Object.entries(b.ablation.groups).map(([g, d]) =>
    `<tr><td class="tm">${g}</td><td>${d.rps_without}</td><td style="color:${d.delta > 0 ? '#18e0a0' : '#ff5a6a'}">${d.delta > 0 ? '+' : ''}${d.delta}</td></tr>`).join('');
  sec.appendChild(el(`<table><tr><th style="text-align:left">Feature group removed</th><th>RPS without it</th><th>cost of removing</th></tr>${ab}</table>`));
  sec.appendChild(el(`<p class="note">Positive "cost" = the model gets worse without that feature, i.e. it helps. Elo dominates; form, rest and the altitude-gap feature add small but real signal — exactly what the literature predicts (altitude only bites at the two Mexican venues). Weather, travel and the diaspora crowd are 2026-only factors shown on each match card.</p>`));
}

function renderHistory(hist) {
  const sec = $('#history'); sec.innerHTML = '';
  sec.appendChild(el(`<h2 class="sec">Past World Cup champions</h2>`));
  const grid = el(`<div class="grid2"></div>`);
  hist.forEach(h => grid.appendChild(el(`<div class="odds-row">
    <div class="rk">${h.year}</div>${flag(h.iso, 'big')}
    <div class="nm">${h.champion}</div><div class="bigpct" style="font-size:16px">🏆</div></div>`)));
  sec.appendChild(grid);
}

function tabs() {
  $('#tabs').addEventListener('click', e => {
    const b = e.target.closest('.tab'); if (!b) return;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
    b.classList.add('active'); $('#' + b.dataset.t).classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

async function main() {
  tabs();
  try {
    const [meta, preds, results, champ, bracket, standings, accuracy, history, bench] =
      await Promise.all(['meta', 'predictions', 'results', 'championship', 'bracket',
        'standings', 'accuracy', 'history', 'benchmark'].map(load));
    $('#sub').textContent = `${meta.matches_played}/104 played · updated ${meta.updated_utc.replace('T', ' ').replace('Z', ' UTC')}`;
    $('#headstat').innerHTML =
      `<div class="kpi"><div class="v good">${accuracy.rps ?? '–'}</div><div class="l">live RPS</div></div>
       <div class="kpi"><div class="v">${accuracy.accuracy != null ? (accuracy.accuracy * 100).toFixed(0) + '%' : '–'}</div><div class="l">called</div></div>
       <div class="kpi"><div class="v">${champ[0] ? (champ[0].champion * 100).toFixed(0) + '%' : '–'}</div><div class="l">${champ[0]?.team || 'favourite'}</div></div>`;
    renderPredictions(preds);
    renderResults(results);
    renderOdds(champ, bracket);
    renderStandings(standings);
    renderAccuracy(accuracy);
    renderModel(bench);
    renderHistory(history);
  } catch (e) {
    document.querySelector('.active').innerHTML = `<div class="note">Couldn't load data (${e.message}). If this is a fresh deploy, the pipeline may not have run yet.</div>`;
  }
}
main();
