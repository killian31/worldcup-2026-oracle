import { useState } from 'react'
import {
  ChevronRight, Flame, Mountain, Home, Moon, Star, MapPin, Thermometer, Zap,
} from 'lucide-react'
import type { Prediction } from '@/lib/types'
import { cn, fmtDate } from '@/lib/utils'
import { Badge, Card, Flag, ProbBar } from './ui'

const FACTOR_ICON: Record<string, typeof Flame> = {
  '🔥': Flame, '⛰️': Mountain, '🏟️': Home, '😴': Moon, '⭐': Star,
}
const FACTOR_LABEL: Record<string, string> = {
  elo: 'Elo rating gap', form: 'Recent form', rest: 'Rest / fatigue',
  context: 'Match context', altitude: 'Altitude',
}

/** An "upset" = the model's pick is the lower-Elo side, or no side is >50%. */
function upsetInfo(m: Prediction) {
  const favIdx = m.probs[0] >= m.probs[2] ? 0 : 2
  const lowerEloIsHome = m.elo[0] < m.elo[1]
  const pickIdx = m.probs.indexOf(Math.max(...m.probs))
  const pickUnderdog = (pickIdx === 0 && lowerEloIsHome) || (pickIdx === 2 && !lowerEloIsHome)
  const underdogProb = lowerEloIsHome ? m.probs[0] : m.probs[2]
  const tossup = Math.max(...m.probs) < 0.45
  void favIdx
  return { pickUnderdog, tossup, underdogProb, underdog: lowerEloIsHome ? m.team1 : m.team2 }
}

export function MatchCard({ m }: { m: Prediction }) {
  const [open, setOpen] = useState(false)
  const up = upsetInfo(m)

  return (
    <Card className="p-4 animate-fade">
      <div className="mb-3 flex items-center justify-between text-[11px] uppercase tracking-wide text-muted">
        <span className="font-display font-semibold text-brand">{m.round || 'Match'}</span>
        <span className="flex items-center gap-1.5">
          {fmtDate(m.date)}
          {m.venue && <><MapPin className="h-3 w-3" /> {m.venue}</>}
          {m.apparent_temp != null && <><Thermometer className="h-3 w-3" /> {m.apparent_temp}°C</>}
        </span>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <Flag iso={m.iso1} className="h-6 w-9" />
          <span className="truncate text-[17px] font-bold">{m.team1}</span>
        </div>
        <Mid m={m} />
        <div className="flex min-w-0 flex-row-reverse items-center gap-2.5 text-right">
          <Flag iso={m.iso2} className="h-6 w-9" />
          <span className="truncate text-[17px] font-bold">{m.team2}</span>
        </div>
      </div>

      {(up.pickUnderdog || up.tossup) && (
        <div className="mt-3 flex items-center gap-2">
          {up.pickUnderdog && (
            <Badge tone="upset"><Zap className="h-3 w-3" /> Upset pick: {up.underdog}</Badge>
          )}
          {up.tossup && !up.pickUnderdog && (
            <Badge tone="upset"><Zap className="h-3 w-3" /> Toss-up — no clear favourite</Badge>
          )}
        </div>
      )}

      <ProbBar probs={m.probs} t1={m.team1} t2={m.team2} />
      {m.market_probs && m.model_probs && <MarketRow m={m} />}

      {m.factors.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {m.factors.map((f, i) => {
            const Icon = FACTOR_ICON[f.icon] ?? Star
            return (
              <span key={i} className={cn(
                'inline-flex items-center gap-1.5 rounded-lg border bg-card2 px-2.5 py-1 text-[11.5px] text-muted',
                f.favors === 'home' && 'border-home/30', f.favors === 'away' && 'border-away/30',
                f.favors === 'none' && 'border-line')}>
                <Icon className="h-3.5 w-3.5 shrink-0" /> {f.text}
              </span>
            )
          })}
        </div>
      )}

      <button onClick={() => setOpen(!open)}
        className="mt-3 flex items-center gap-1 text-xs font-semibold text-brand hover:text-brand/80 transition-colors">
        <ChevronRight className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-90')} />
        Why this prediction?
      </button>
      {open && <Why m={m} />}
    </Card>
  )
}

function MarketRow({ m }: { m: Prediction }) {
  const mk = m.market_probs!, mo = m.model_probs!
  // biggest divergence between our model and the market
  const d = [mo[0] - mk[0], mo[1] - mk[1], mo[2] - mk[2]]
  const i = d.map(Math.abs).indexOf(Math.max(...d.map(Math.abs)))
  const side = ['home win', 'a draw', 'away win'][i]
  const edge = Math.abs(d[i]) >= 0.06
    ? `Model ${d[i] > 0 ? 'higher' : 'lower'} than market on ${side} (${d[i] > 0 ? '+' : ''}${Math.round(d[i] * 100)}%)`
    : 'Model agrees with the market'
  return (
    <div className="mt-2 flex items-center gap-2 text-[11px] text-muted">
      <span className="font-semibold uppercase tracking-wide text-away">Market</span>
      <span className="tnum">{Math.round(mk[0] * 100)}% · {Math.round(mk[1] * 100)}% · {Math.round(mk[2] * 100)}%</span>
      <span className="ml-auto">{edge}</span>
    </div>
  )
}

function Mid({ m }: { m: Prediction }) {
  if (m.played && m.actual_score) {
    const [hs, as] = m.actual_score
    return (
      <div className="text-center">
        <div className="font-display text-3xl font-bold tnum">{hs}–{as}</div>
        <div className="text-[10px] text-muted tnum">projected {m.pred_score[0]}–{m.pred_score[1]}</div>
        <div className="mt-1 flex justify-center gap-1">
          <Badge tone={m.correct ? 'good' : 'bad'}>{m.correct ? '✓ result' : '✗ result'}</Badge>
          {m.exact_hit && <Badge tone="good">🎯 exact</Badge>}
        </div>
      </div>
    )
  }
  return (
    <div className="text-center">
      <div className="font-display text-2xl font-bold tnum text-muted">{m.pred_score[0]}–{m.pred_score[1]}</div>
      <div className="text-[10px] text-muted">projected score</div>
      <div className="text-[10px] text-muted tnum">xG {m.exp_goals[0]}–{m.exp_goals[1]}</div>
    </div>
  )
}

function Why({ m }: { m: Prediction }) {
  const c = m.explain.contributions
  const maxAbs = Math.max(0.01, ...c.map((x) => Math.abs(x.delta)))
  return (
    <div className="mt-3 border-t border-line pt-3 text-[12.5px] text-muted animate-fade">
      <div className="space-y-1">
        <div><b className="text-fg">Elo</b> {m.team1} <span className="tnum">{m.elo[0]}</span> · {m.team2} <span className="tnum">{m.elo[1]}</span>
          <span className="text-muted"> (gap {m.elo[0] - m.elo[1] > 0 ? '+' : ''}{m.elo[0] - m.elo[1]})</span></div>
        <div><b className="text-fg">Form</b> last-5 avg pts — {m.team1} <span className="tnum">{m.form[0]}</span> · {m.team2} <span className="tnum">{m.form[1]}</span></div>
        {m.squad && <div><b className="text-fg">Squad</b> {m.team1} <span className="tnum">{m.squad.home}</span> ({m.squad.home_big5} big-5) · {m.team2} <span className="tnum">{m.squad.away}</span> ({m.squad.away_big5} big-5)</div>}
      </div>
      <div className="mt-2.5 mb-1.5">What shifted {m.team1}'s win chance vs an even match:</div>
      <div className="space-y-1.5">
        {c.filter((x) => Math.abs(x.delta) >= 0.002).map((x) => (
          <div key={x.factor} className="grid grid-cols-[120px_1fr_44px] items-center gap-2">
            <span>{FACTOR_LABEL[x.factor] ?? x.factor}</span>
            <span className="relative h-2.5 rounded bg-card2">
              <span className={cn('absolute top-0 h-2.5 rounded', x.delta > 0 ? 'left-0 bg-home' : 'right-0 bg-away')}
                style={{ width: `${(Math.abs(x.delta) / maxAbs) * 100}%` }} />
            </span>
            <span className={cn('text-right text-[11px] font-bold tnum', x.delta > 0 ? 'text-home' : 'text-away')}>
              {x.delta > 0 ? '+' : ''}{(x.delta * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
