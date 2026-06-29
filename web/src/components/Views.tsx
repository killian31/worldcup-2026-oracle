import { useState } from 'react'
import { ChevronDown, Star, Trophy } from 'lucide-react'
import type { Accuracy, Benchmark, HistoryRow, SquadTeam, Standings, TeamOdds } from '@/lib/types'
import { cn, pct } from '@/lib/utils'
import { Card, Flag, SectionTitle, Stat } from './ui'

const BIG5 = new Set(['ENG', 'ESP', 'ITA', 'GER', 'FRA'])

export function OddsView({ odds }: { odds: TeamOdds[] }) {
  const top = odds.filter((t) => t.champion > 0.001).slice(0, 16)
  return (
    <div>
      <SectionTitle>Championship odds — {top[0] ? `${pct(top[0].champion)} favourite ${top[0].team}` : ''}</SectionTitle>
      <div className="space-y-2">
        {top.map((t, i) => (
          <Card key={t.team} className="grid grid-cols-[28px_44px_1fr_auto] items-center gap-3 px-4 py-2.5">
            <span className="text-center font-display text-muted tnum">{i + 1}</span>
            <Flag iso={t.iso} className="h-7 w-11" />
            <div>
              <div className="font-bold">{t.team}</div>
              <div className="text-[11px] text-muted">{t.conf} · Elo <span className="tnum">{t.elo}</span></div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right text-[11px] text-muted tnum">final {pct(t.reach_final)}<br />semi {pct(t.reach_sf)}</div>
              <div className="w-16 text-right font-display text-2xl font-bold text-brand tnum">{pct(t.champion, 1)}</div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

export function StandingsView({ standings }: { standings: Standings }) {
  return (
    <div>
      <SectionTitle>Group stage — final tables (top 2 + 8 best 3rd advance)</SectionTitle>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(standings).map(([g, rows]) => (
          <div key={g}>
            <h3 className="mb-2 font-display text-sm uppercase tracking-wide text-muted">{g}</h3>
            <Card className="overflow-hidden">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-bg/40 text-[10px] uppercase tracking-wide text-muted">
                    <th className="px-2.5 py-2 text-left">Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th className="pr-2.5">Pts</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.team} className={cn('border-t border-line tnum', i < 2 && 'shadow-[inset_3px_0_0_rgb(var(--home))]')}>
                      <td className="flex items-center gap-2 px-2.5 py-1.5 text-left font-semibold"><Flag iso={r.iso} className="h-3.5 w-5" />{r.team}</td>
                      <td className="text-center">{r.P}</td><td className="text-center">{r.W}</td><td className="text-center">{r.D}</td>
                      <td className="text-center">{r.L}</td><td className="text-center">{r.GD > 0 ? '+' : ''}{r.GD}</td>
                      <td className="pr-2.5 text-center font-bold">{r.Pts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
        ))}
      </div>
    </div>
  )
}

export function SquadsView({ squads }: { squads: SquadTeam[] }) {
  return (
    <div>
      <SectionTitle>Squads — who's in each team (sorted by squad strength)</SectionTitle>
      <Card className="mb-3 p-3 text-[12px] text-muted">
        Squad strength = league quality of each player's club (a free, dependency-free proxy that
        correlates ~0.67 with Elo), used as a 2026-only overlay. Per-player live "form" has no free
        feed post-2026, so it isn't modelled individually.
      </Card>
      <div className="space-y-2">{squads.map((s) => <SquadCard key={s.team} s={s} />)}</div>
    </div>
  )
}

function SquadCard({ s }: { s: SquadTeam }) {
  const [open, setOpen] = useState(false)
  const POS: [string, string][] = [['GK', 'Goalkeepers'], ['DF', 'Defenders'], ['MF', 'Midfielders'], ['FW', 'Forwards']]
  return (
    <Card>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <Flag iso={s.iso} className="h-7 w-11" />
        <span className="text-base font-bold">{s.team}</span>
        <span className="ml-auto flex items-center gap-3 text-[12px] text-muted tnum">
          str <b className="text-brand">{s.strength}</b> · {s.n_big5}/26 big-5 · age {s.avg_age} · cup {pct(s.champion)}
          <ChevronDown className={cn('h-4 w-4 transition-transform', open && 'rotate-180')} />
        </span>
      </button>
      {open && (
        <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2 lg:grid-cols-4 animate-fade">
          {POS.map(([k, label]) => {
            const pl = s.players.filter((p) => p.pos === k)
            if (!pl.length) return null
            return (
              <div key={k}>
                <h4 className="mb-1.5 text-[11px] uppercase tracking-wide text-brand">{label}</h4>
                {pl.map((p) => (
                  <div key={p.name} className="flex justify-between gap-2 border-b border-white/5 py-1 text-[13px]">
                    <span className="truncate">{p.name}</span>
                    <span className="shrink-0 text-right text-[11px] text-muted">
                      {p.club_country && BIG5.has(p.club_country) && <Star className="mr-1 inline h-3 w-3 text-brand" />}
                      {p.age ?? ''}
                    </span>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function Sparkline({ series }: { series: { date: string; rps: number }[] }) {
  if (!series.length) return null
  const w = 640, h = 130
  const ys = series.map((s) => s.rps)
  const minY = Math.min(...ys, 0.15), maxY = Math.max(...ys, 0.25)
  const X = (i: number) => 34 + (i / (series.length - 1 || 1)) * (w - 44)
  const Y = (v: number) => h - 22 - ((v - minY) / (maxY - minY)) * (h - 40)
  const path = series.map((s, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(s.rps).toFixed(1)}`).join(' ')
  const ref = Y(0.2282)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
      <line x1="34" y1={ref} x2={w} y2={ref} stroke="#445" strokeDasharray="4 4" />
      <text x="38" y={ref - 4} fill="#6b7796" fontSize="10">naive baseline 0.228</text>
      <path d={path} fill="none" stroke="rgb(24 224 160)" strokeWidth="2.5" />
      <text x="34" y="14" fill="#8a97b4" fontSize="11">running RPS (lower = better)</text>
      <text x={w - 4} y={Y(ys[ys.length - 1]) - 6} fill="rgb(24 224 160)" fontSize="12" textAnchor="end" fontWeight="700">{ys[ys.length - 1].toFixed(3)}</text>
    </svg>
  )
}

function Calibration({ bins }: { bins: { conf: number; acc: number; n: number }[] }) {
  const w = 420, h = 260
  const P = (v: number) => 30 + v * (w - 50), Q = (v: number) => h - 30 - v * (h - 50)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-[440px]">
      <line x1={P(0.3)} y1={Q(0.3)} x2={P(1)} y2={Q(1)} stroke="#445" strokeDasharray="4 4" />
      {bins.map((b, i) => (
        <g key={i}>
          <circle cx={P(b.conf)} cy={Q(b.acc)} r={4 + Math.sqrt(b.n)} fill="rgb(74 168 255)" fillOpacity="0.7" />
          <text x={P(b.conf)} y={Q(b.acc) - 8 - Math.sqrt(b.n)} fill="#8a97b4" fontSize="9" textAnchor="middle">n={b.n}</text>
        </g>
      ))}
      <text x={w / 2} y={h - 6} fill="#8a97b4" fontSize="11" textAnchor="middle">predicted favourite probability</text>
      <text x="12" y={h / 2} fill="#8a97b4" fontSize="11" textAnchor="middle" transform={`rotate(-90 12 ${h / 2})`}>actual hit rate</text>
    </svg>
  )
}

export function AccuracyView({ acc }: { acc: Accuracy }) {
  if (!acc.n) return <Card className="p-4 text-muted">No completed matches scored yet.</Card>
  return (
    <div>
      <SectionTitle>How the model is doing — {acc.n} matches scored</SectionTitle>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat value={pct(acc.accuracy)} label="result called (W/D/L)" tone="good" />
        <Stat value={pct(acc.exact_accuracy)} label="exact score hit" tone="away" />
        <Stat value={acc.rps} label="RPS (lower better)" />
        <Stat value={`${acc.n_correct}/${acc.n}`} label="correct results" />
        <Stat value={pct(acc.ece, 1)} label="calibration error" />
      </div>
      <Card className="my-4 p-3.5 text-[12px] text-muted">
        Two bars: <b className="text-fg">result</b> = did we call the winner/draw (the model's real
        strength, {pct(acc.accuracy)}). <b className="text-fg">Exact score</b> is genuinely hard —
        even bookmakers land only ~10–13%; we hit {pct(acc.exact_accuracy)} (avg {acc.avg_goal_err} goals
        off). The model predicts a <i>distribution</i> of scores; the "most likely" one is shown per
        match, but the probabilities are where the signal is.
      </Card>
      <Card className="mb-4 p-4">
        <h3 className="text-[13px] text-muted">Running prediction skill</h3>
        <p className="mb-3 text-[12px] text-muted">Mean RPS across played matches, in date order. Below the dashed line beats a naive base-rate forecast.</p>
        <Sparkline series={acc.running_rps} />
      </Card>
      <Card className="p-4">
        <h3 className="text-[13px] text-muted">Calibration</h3>
        <p className="mb-3 text-[12px] text-muted">When the model says a favourite has X% chance, do they win X% of the time? Dots near the diagonal = honest probabilities.</p>
        <Calibration bins={acc.calibration} />
      </Card>
    </div>
  )
}

export function ModelView({ b }: { b: Benchmark }) {
  return (
    <div>
      <SectionTitle>Benchmark — walk-forward over {b.n_matches.toLocaleString()} internationals ({b.date_from} → {b.date_to})</SectionTitle>
      <Card className="mb-4 overflow-hidden">
        <table className="w-full text-[13px] tnum">
          <thead><tr className="bg-bg/40 text-[10px] uppercase tracking-wide text-muted">
            <th className="px-3 py-2 text-left">Model</th><th>RPS</th><th>log-loss</th><th>Brier</th><th>Acc</th><th className="pr-3">ECE</th>
          </tr></thead>
          <tbody>
            {Object.entries(b.models).map(([m, s]) => (
              <tr key={m} className={cn('border-t border-line', m === b.best_model && 'shadow-[inset_3px_0_0_rgb(var(--home))]')}>
                <td className="px-3 py-2 text-left font-semibold">{m}{m === b.best_model && <Trophy className="ml-1 inline h-3.5 w-3.5 text-brand" />}</td>
                <td className="text-center font-bold">{s.rps}</td><td className="text-center">{s.log_loss}</td>
                <td className="text-center">{s.brier}</td><td className="text-center">{pct(s.accuracy, 1)}</td><td className="pr-3 text-center">{pct(s.ece, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <SectionTitle>Does each feature actually help? (ablation)</SectionTitle>
      <Card className="overflow-hidden">
        <table className="w-full text-[13px] tnum">
          <thead><tr className="bg-bg/40 text-[10px] uppercase tracking-wide text-muted">
            <th className="px-3 py-2 text-left">Feature group removed</th><th>RPS without</th><th className="pr-3">cost of removing</th>
          </tr></thead>
          <tbody>
            {Object.entries(b.ablation.groups).map(([g, d]) => (
              <tr key={g} className="border-t border-line">
                <td className="px-3 py-2 text-left">{g}</td><td className="text-center">{d.rps_without}</td>
                <td className={cn('pr-3 text-center font-semibold', d.delta > 0 ? 'text-home' : 'text-upset')}>{d.delta > 0 ? '+' : ''}{d.delta}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card className="mt-4 p-3.5 text-[12px] text-muted">
        Positive cost = the model is worse without it. Elo dominates; form, rest and altitude add small
        real signal. We also tested whether the model is "too safe": softening it to predict more upsets
        (temperature &gt; 1) <b className="text-fg">worsened</b> accuracy, and the upset calibration is
        near-perfect (when a favourite is 55% likely they win ~55% of the time). So the model isn't being
        over-cautious — the upsets are already priced into the probabilities.
      </Card>
    </div>
  )
}

export function HistoryView({ history }: { history: HistoryRow[] }) {
  return (
    <div>
      <SectionTitle>Past World Cup champions</SectionTitle>
      <div className="grid gap-2 sm:grid-cols-2">
        {history.map((h) => (
          <Card key={h.year} className="flex items-center gap-3 px-4 py-2.5">
            <span className="font-display text-muted tnum">{h.year}</span>
            <Flag iso={h.iso} className="h-7 w-11" />
            <span className="font-bold">{h.champion}</span>
            <Trophy className="ml-auto h-4 w-4 text-brand" />
          </Card>
        ))}
      </div>
    </div>
  )
}
