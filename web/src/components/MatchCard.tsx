import { useState } from 'react'
import {
  ChevronRight, Flame, Mountain, Home, Moon, Star, MapPin, Thermometer, Zap,
} from 'lucide-react'
import type { FormMatch, Prediction } from '@/lib/types'
import { cn, fmtDate } from '@/lib/utils'
import { Badge, Card, Flag, ProbBar } from './ui'

const RES_BG: Record<FormMatch['res'], string> = { W: 'bg-home', D: 'bg-draw', L: 'bg-upset' }

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

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-3">
        <TeamName name={m.team1} iso={m.iso1} form={m.form1} side="home" />
        <Mid m={m} />
        <TeamName name={m.team2} iso={m.iso2} form={m.form2} side="away" />
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

function TeamName({ name, iso, form, side }: { name: string; iso: string; form?: FormMatch[]; side: 'home' | 'away' }) {
  const away = side === 'away'
  return (
    <div className={cn('group/team relative flex min-w-0 items-center gap-2 sm:gap-2.5', away && 'flex-row-reverse text-right')}>
      <Flag iso={iso} className="h-5 w-7 sm:h-6 sm:w-9" />
      <span className={cn('truncate text-[14px] font-bold sm:text-[17px]',
        form?.length && 'cursor-default decoration-dotted underline-offset-4 group-hover/team:underline')} title={name}>{name}</span>
      {!!form?.length && <FormPopover form={form} side={side} team={name} />}
    </div>
  )
}

function FormPopover({ form, side, team }: { form: FormMatch[]; side: 'home' | 'away'; team: string }) {
  const tally = { W: 0, D: 0, L: 0 }
  form.forEach((g) => (tally[g.res] += 1))
  return (
    <div className={cn(
      'pointer-events-none absolute top-full z-40 mt-2 w-64 rounded-xl border border-line bg-card2 p-3 text-left shadow-xl shadow-black/40',
      'translate-y-1 opacity-0 transition-all duration-150 group-hover/team:translate-y-0 group-hover/team:opacity-100',
      side === 'away' ? 'right-0' : 'left-0')}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="truncate text-[10px] font-semibold uppercase tracking-wider text-muted">{team} · last {form.length}</span>
        <span className="flex shrink-0 gap-0.5">
          {form.map((g, i) => (
            <span key={i} title={`${g.res} ${g.venue === 'A' ? '@' : 'vs'} ${g.opp} ${g.gf}–${g.ga}`}
              className={cn('h-4 w-4 rounded-sm text-center text-[9px] font-bold leading-4 text-black/85', RES_BG[g.res])}>{g.res}</span>
          ))}
        </span>
      </div>
      <div className="space-y-1">
        {[...form].reverse().map((g, i) => (
          <div key={i} className="flex items-center gap-2 text-[11.5px]">
            <span className={cn('h-2 w-2 shrink-0 rounded-full', RES_BG[g.res])} />
            <span className="w-3 shrink-0 text-center text-[10px] text-muted">{g.venue === 'A' ? '@' : g.venue === 'N' ? 'N' : ''}</span>
            <Flag iso={g.opp_iso} className="h-3 w-5" />
            <span className="truncate text-muted">{g.opp}</span>
            <span className="ml-auto tnum font-semibold">{g.gf}–{g.ga}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 border-t border-line pt-1.5 text-[10px] text-muted tnum">{tally.W}W · {tally.D}D · {tally.L}L</div>
    </div>
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
        <div className="font-display text-2xl font-bold tnum sm:text-3xl">{hs}–{as}</div>
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
      <div className="font-display text-xl font-bold tnum text-muted sm:text-2xl">{m.pred_score[0]}–{m.pred_score[1]}</div>
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
