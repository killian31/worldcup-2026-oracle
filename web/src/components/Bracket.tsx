import { useMemo, useRef, useState } from 'react'
import { Play, Zap, Trophy } from 'lucide-react'
import type { BracketMatch, TeamOdds } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Badge, Card, Flag, SectionTitle } from './ui'

type Res = { win: Record<number, string>; los: Record<number, string> }
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const eloP = (a: number, b: number) => 1 / (1 + Math.pow(10, -(a - b) / 400))

export function Bracket({ bracket, odds }: { bracket: BracketMatch[]; odds: TeamOdds[] }) {
  const byNum = useMemo(() => Object.fromEntries(bracket.map((m) => [m.number, m])), [bracket])
  const elo = useMemo(() => Object.fromEntries(odds.map((t) => [t.team, t.elo])), [odds])
  const iso = useMemo(() => {
    const m: Record<string, string> = {}
    odds.forEach((t) => (m[t.team] = t.iso))
    bracket.forEach((b) => [b.team1, b.team2].forEach((s) => s.team && s.iso && (m[s.team] = s.iso)))
    return m
  }, [bracket, odds])

  // bracket layout: two-sided tree, in-order vertical alignment from feeders
  const layout = useMemo(() => {
    const feed = (n: number) => byNum[n]?.feeders ?? []
    const Y: Record<number, number> = {}
    let yc = 0
    const dfs = (n: number) => { const f = feed(n); if (f.length === 2) { dfs(f[0]); Y[n] = yc++; dfs(f[1]) } else Y[n] = yc++ }
    yc = 0; if (byNum[101]) dfs(101); yc = 0; if (byNum[102]) dfs(102)
    const rng = (a: number, b: number) => bracket.filter((m) => m.number >= a && m.number <= b).map((m) => m.number)
    const col = (nums: number[], side: string) => nums.filter((n) => byNum[n].half === side).sort((a, b) => (Y[a] ?? 0) - (Y[b] ?? 0))
    return {
      left: [['R32', col(rng(73, 88), 'l')], ['R16', col(rng(89, 96), 'l')], ['QF', col(rng(97, 100), 'l')], ['SF', col([101], 'l')]] as [string, number[]][],
      right: [['SF', col([102], 'r')], ['QF', col(rng(97, 100), 'r')], ['R16', col(rng(89, 96), 'r')], ['R32', col(rng(73, 88), 'r')]] as [string, number[]][],
    }
  }, [bracket, byNum])

  // seed locked results from real scores (match order so feeders resolve first)
  const seed = useMemo(() => {
    const r: Res = { win: {}, los: {} }
    const resolve = (n: number, which: 1 | 2): string | undefined => {
      const s = which === 1 ? byNum[n].team1 : byNum[n].team2
      if (s.team) return s.team
      const ref = +s.placeholder!.slice(1)
      return s.placeholder![0] === 'W' ? r.win[ref] : r.los[ref]
    }
    bracket.slice().sort((a, b) => a.number - b.number).forEach((m) => {
      if (!m.score) return
      const t1 = resolve(m.number, 1), t2 = resolve(m.number, 2)
      if (!t1 || !t2) return
      const homeWin = m.score[0] >= m.score[1]
      r.win[m.number] = homeWin ? t1 : t2
      r.los[m.number] = homeWin ? t2 : t1
    })
    return r
  }, [bracket, byNum])

  const [res, setRes] = useState<Res>(seed)
  const [live, setLive] = useState<number | null>(null)
  const [champion, setChampion] = useState<string | null>(null)
  const [tally, setTally] = useState<Record<string, number>>({})
  const [runs, setRuns] = useState(0)
  const running = useRef(false)

  const resolveSlot = (state: Res, n: number, which: 1 | 2): string | undefined => {
    const s = which === 1 ? byNum[n].team1 : byNum[n].team2
    if (s.team) return s.team
    const ref = +s.placeholder!.slice(1)
    return s.placeholder![0] === 'W' ? state.win[ref] : state.los[ref]
  }

  async function play(instant: boolean) {
    if (running.current) return
    running.current = true
    setChampion(null)
    const r: Res = { win: { ...seed.win }, los: { ...seed.los } }
    setRes({ win: { ...r.win }, los: { ...r.los } })
    const order = bracket.map((m) => m.number).sort((a, b) => a - b)
    let lastRound = ''
    for (const n of order) {
      const m = byNum[n]
      if (r.win[n]) continue // locked
      const t1 = resolveSlot(r, n, 1), t2 = resolveSlot(r, n, 2)
      if (!t1 || !t2) continue
      if (!instant && m.round !== lastRound) { lastRound = m.round; await sleep(280) }
      if (!instant) { setLive(n); await sleep(70) }
      const homeWin = Math.random() < eloP(elo[t1] ?? 1500, elo[t2] ?? 1500)
      r.win[n] = homeWin ? t1 : t2
      r.los[n] = homeWin ? t2 : t1
      setRes({ win: { ...r.win }, los: { ...r.los } })
      if (!instant) { setLive(null); await sleep(40) }
    }
    const champ = r.win[104]
    setChampion(champ)
    setTally((t) => ({ ...t, [champ]: (t[champ] ?? 0) + 1 }))
    setRuns((x) => x + 1)
    running.current = false
  }

  const Match = ({ n }: { n: number }) => {
    const m = byNum[n]
    const slot = (which: 1 | 2) => {
      const team = resolveSlot(res, n, which)
      const decided = !!res.win[n]
      const isWin = decided && res.win[n] === team
      const isLose = decided && !isWin
      return (
        <div className={cn('flex items-center gap-1.5 px-2 py-1 text-[11px] border-b border-line last:border-b-0 transition-colors',
          isWin && 'bg-home/15 text-home font-bold', isLose && 'opacity-40')}>
          {team ? <><Flag iso={iso[team] ?? 'un'} className="h-3 w-4" /><span className="truncate">{team}</span></>
            : <span className="italic text-muted">{(which === 1 ? m.team1 : m.team2).placeholder}</span>}
        </div>
      )
    }
    return (
      <div className={cn('my-1 overflow-hidden rounded-md border border-line bg-card transition-shadow',
        n >= 103 && 'ring-1 ring-brand/30', live === n && 'ring-2 ring-brand')}>
        {slot(1)}{slot(2)}
      </div>
    )
  }

  const Column = ({ title, nums }: { title: string; nums: number[] }) => (
    <div className="flex min-w-[104px] flex-1 flex-col">
      <h4 className="mb-1 text-center font-display text-[10px] uppercase tracking-wider text-brand">{title}</h4>
      <div className="flex flex-1 flex-col justify-around">{nums.map((n) => <Match key={n} n={n} />)}</div>
    </div>
  )

  const tallyRows = Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 8)

  return (
    <div>
      <SectionTitle>Play the tournament — simulate the bracket to a champion</SectionTitle>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button onClick={() => play(false)}
          className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 font-display font-bold tracking-wide text-black transition hover:brightness-110 disabled:opacity-50"
          disabled={running.current}>
          <Play className="h-4 w-4 fill-black" /> Play simulation
        </button>
        <button onClick={() => play(true)}
          className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-4 py-2 text-sm font-semibold text-muted transition hover:text-fg">
          <Zap className="h-4 w-4" /> Instant
        </button>
        <span className="text-sm text-muted">
          {champion ? `Champion: ${champion}. Play again for a different roll.` : 'Each run samples every remaining match from the model.'}
        </span>
      </div>

      {champion && (
        <Card className="mb-4 animate-pop border-brand/30 bg-gradient-to-b from-brand/10 to-transparent p-4">
          <div className="flex items-center justify-center gap-3">
            <Trophy className="h-9 w-9 text-brand" />
            <Flag iso={iso[champion] ?? 'un'} className="h-8 w-11" />
            <span className="font-display text-2xl font-bold sm:text-3xl">{champion}</span>
            <span className="text-[11px] uppercase tracking-[0.2em] text-brand">World Champions</span>
          </div>
        </Card>
      )}

      <div className="flex items-stretch gap-1 overflow-x-auto scroll-thin pb-2" style={{ minHeight: 430 }}>
        <div className="flex flex-1 gap-1">{layout.left.map(([t, nums], i) => <Column key={'l' + i} title={t} nums={nums} />)}</div>
        <div className="flex shrink-0 flex-col justify-center px-1">
          <h4 className="mb-1 text-center font-display text-[10px] uppercase tracking-wider text-brand">Final</h4>
          <Match n={104} />
          {byNum[103] && <><div className="mt-3 mb-1 text-center text-[9px] uppercase tracking-wider text-muted">3rd place</div><Match n={103} /></>}
        </div>
        <div className="flex flex-1 gap-1">{layout.right.map(([t, nums], i) => <Column key={'r' + i} title={t} nums={nums} />)}</div>
      </div>

      {runs > 0 && (
        <div className="mt-4 text-[12.5px] text-muted">
          <b className="text-fg">{runs}</b> simulation{runs > 1 ? 's' : ''} run — champions tally:
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {tallyRows.map(([t, c]) => (
              <Badge key={t}><Flag iso={iso[t] ?? 'un'} className="h-3 w-4" /> {t} <b className="text-brand">{c}</b></Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
