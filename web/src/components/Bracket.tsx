import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Play, Zap, Trophy, BarChart3 } from 'lucide-react'
import type { BracketMatch, TeamOdds } from '@/lib/types'
import { cn, flagUrl } from '@/lib/utils'
import { Badge, Card, Flag, SectionTitle } from './ui'

type Res = { win: Record<number, string>; los: Record<number, string>; sc: Record<number, [number, number]> }
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const eloP = (a: number, b: number) => 1 / (1 + Math.pow(10, -(a - b) / 400))

// a few country names are too long for a fixed bracket cell — show a short form
const SHORT: Record<string, string> = {
  'Bosnia and Herzegovina': 'Bosnia', 'Trinidad and Tobago': 'Trinidad',
  'United Arab Emirates': 'UAE', 'Republic of Ireland': 'Ireland', 'United States': 'USA',
}
const disp = (t: string) => SHORT[t] ?? t

// Elo-implied scoreline for a simulated KO game: Poisson goals, forced decisive
// and aligned with the winner the bracket already picked. (Flavour, not the Dixon-Coles model.)
const poisson = (l: number) => { const L = Math.exp(-l); let k = 0, p = 1; do { k++; p *= Math.random() } while (p > L); return k - 1 }
function rollScore(a: number, b: number, homeWin: boolean, base = 1.35): [number, number] {
  const d = (a - b) / 400
  let g1 = poisson(Math.max(0.25, base + 0.8 * d)), g2 = poisson(Math.max(0.25, base - 0.8 * d))
  if (g1 === g2) homeWin ? g1++ : g2++
  else if (g1 > g2 !== homeWin) { const t = g1; g1 = g2; g2 = t }
  return [g1, g2]
}
if (import.meta.env?.DEV) // a KO scoreline must be decisive and match the chosen winner
  for (let i = 0; i < 300; i++) { const w = Math.random() < 0.5, s = rollScore(1600, 1400, w); if (s[0] === s[1] || s[0] > s[1] !== w) throw new Error('rollScore: not decisive / winner mismatch') }

// reveal-on-scroll: fires once when the element scrolls into view (mobile sim flow)
function useInView<T extends Element>(margin = '0px 0px -12% 0px'): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const ob = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); ob.disconnect() } }, { rootMargin: margin })
    ob.observe(el)
    return () => ob.disconnect()
  }, [seen, margin])
  return [ref, seen]
}

const RACE_N = 1000
const PALETTE = ['#ffd84a', '#4aa8ff', '#18e0a0', '#f472b6', '#a78bfa', '#fb923c', '#ff5a78']
// a drawn knockout is decided on penalties (score.p), not by giving the tie to the home side
const koHomeWon = (s: [number, number], p?: [number, number] | null) =>
  s[0] !== s[1] ? s[0] > s[1] : p ? p[0] > p[1] : true
type Race = {
  teams: string[]; colors: Record<string, string>
  series: Record<string, number[]>; pts: Record<string, [number, number][]>; max: number
}

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
    const left = [['R32', col(rng(73, 88), 'l')], ['R16', col(rng(89, 96), 'l')], ['QF', col(rng(97, 100), 'l')], ['SF', col([101], 'l')]] as [string, number[]][]
    const right = [['SF', col([102], 'r')], ['QF', col(rng(97, 100), 'r')], ['R16', col(rng(89, 96), 'r')], ['R32', col(rng(73, 88), 'r')]] as [string, number[]][]
    // mobile: one flat list per round (tree can't fit a phone), feeders keep order
    const mobile = [
      ['Round of 32', [...left[0][1], ...right[3][1]]],
      ['Round of 16', [...left[1][1], ...right[2][1]]],
      ['Quarter-finals', [...left[2][1], ...right[1][1]]],
      ['Semi-finals', [...left[3][1], ...right[0][1]]],
      ['Final', byNum[104] ? [104] : []],
      ['Third place', byNum[103] ? [103] : []],
    ] as [string, number[]][]
    return { left, right, mobile }
  }, [bracket, byNum])

  // seed locked results from real scores (match order so feeders resolve first)
  const seed = useMemo(() => {
    const r: Res = { win: {}, los: {}, sc: {} }
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
      const homeWin = koHomeWon(m.score, m.pens)
      r.win[m.number] = homeWin ? t1 : t2
      r.los[m.number] = homeWin ? t2 : t1
      r.sc[m.number] = m.score          // real played scoreline (pens read from byNum for display)
    })
    return r
  }, [bracket, byNum])

  const [res, setRes] = useState<Res>(seed)
  const [live, setLive] = useState<number | null>(null)
  const [champion, setChampion] = useState<string | null>(null)
  const [tally, setTally] = useState<Record<string, number>>({})
  const [runs, setRuns] = useState(0)
  const [race, setRace] = useState<Race | null>(null)
  const [step, setStep] = useState(0)
  const [rolled, setRolled] = useState(false)   // mobile: a sim has been rolled → reveal on scroll
  const [runId, setRunId] = useState(0)          // bump to re-arm the reveal observers
  const [fun, setFun] = useState(1.35)            // sim goal rate (flavour only — never changes who wins)
  const running = useRef(false)
  const raceTimer = useRef<number | null>(null)
  useEffect(() => () => { if (raceTimer.current) clearInterval(raceTimer.current) }, [])
  const order = useMemo(() => bracket.map((m) => m.number).sort((a, b) => a - b), [bracket])
  // mobile: roll once on open so scrolling reveals the bracket with no tap needed (tap = re-roll)
  useEffect(() => { if (window.matchMedia?.('(max-width: 767px)').matches) rollMobile() }, []) // eslint-disable-line react-hooks/exhaustive-deps

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
    setRace(null)
    const r: Res = { win: { ...seed.win }, los: { ...seed.los }, sc: { ...seed.sc } }
    setRes({ win: { ...r.win }, los: { ...r.los }, sc: { ...r.sc } })
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
      r.sc[n] = rollScore(elo[t1] ?? 1500, elo[t2] ?? 1500, homeWin, fun)
      setRes({ win: { ...r.win }, los: { ...r.los }, sc: { ...r.sc } })
      if (!instant) { setLive(null); await sleep(40) }
    }
    const champ = r.win[104]
    setChampion(champ)
    setTally((t) => ({ ...t, [champ]: (t[champ] ?? 0) + 1 }))
    setRuns((x) => x + 1)
    running.current = false
  }

  // Race: run RACE_N full tournaments up-front, then animate the cumulative
  // championship count of the top teams climbing as the sim counter ticks up.
  function runRace() {
    if (running.current) return
    running.current = true
    // race is purely additive — it never touches res / champion / the bracket below
    const simChampion = () => {
      const r: Res = { win: { ...seed.win }, los: { ...seed.los }, sc: {} }
      for (const n of order) {
        if (r.win[n]) continue
        const t1 = resolveSlot(r, n, 1), t2 = resolveSlot(r, n, 2)
        if (!t1 || !t2) continue
        const homeWin = Math.random() < eloP(elo[t1] ?? 1500, elo[t2] ?? 1500)
        r.win[n] = homeWin ? t1 : t2
        r.los[n] = homeWin ? t2 : t1
      }
      return r.win[104]
    }
    const champs: string[] = []
    for (let i = 0; i < RACE_N; i++) champs.push(simChampion())

    const counts: Record<string, number> = {}
    champs.forEach((c) => c && (counts[c] = (counts[c] ?? 0) + 1))
    const teams = Object.keys(counts).sort((a, b) => counts[b] - counts[a]).slice(0, 7)
    const series: Record<string, number[]> = {}
    const pts: Record<string, [number, number][]> = {}
    const run: Record<string, number> = {}
    teams.forEach((t) => { series[t] = []; pts[t] = [[0, 0]]; run[t] = 0 })
    champs.forEach((c) => {
      if (c in run) run[c]++
      teams.forEach((t) => series[t].push(run[t]))
    })
    teams.forEach((t) => { for (let i = 1; i < RACE_N; i++) if (series[t][i] !== series[t][i - 1]) pts[t].push([i, series[t][i]]) })
    const colors: Record<string, string> = {}
    teams.forEach((t, i) => (colors[t] = PALETTE[i % PALETTE.length]))
    setRace({ teams, colors, series, pts, max: Math.max(1, ...teams.map((t) => counts[t])) })
    setStep(0)

    if (raceTimer.current) clearInterval(raceTimer.current)
    let s = 0
    const inc = Math.max(1, Math.round(RACE_N / 220)) // ~3.5s reveal at 60fps
    raceTimer.current = window.setInterval(() => {
      s += inc
      if (s >= RACE_N - 1) { s = RACE_N - 1; clearInterval(raceTimer.current!); raceTimer.current = null; running.current = false }
      setStep(s)
    }, 16)
  }

  // resolve every remaining match at once (one full Elo roll with scorelines)
  const simulateAll = (): Res => {
    const r: Res = { win: { ...seed.win }, los: { ...seed.los }, sc: { ...seed.sc } }
    for (const n of order) {
      if (r.win[n]) continue
      const t1 = resolveSlot(r, n, 1), t2 = resolveSlot(r, n, 2)
      if (!t1 || !t2) continue
      const homeWin = Math.random() < eloP(elo[t1] ?? 1500, elo[t2] ?? 1500)
      r.win[n] = homeWin ? t1 : t2
      r.los[n] = homeWin ? t2 : t1
      r.sc[n] = rollScore(elo[t1] ?? 1500, elo[t2] ?? 1500, homeWin, fun)
    }
    return r
  }


  // mobile: roll instantly, then let the round list reveal game-by-game on scroll
  function rollMobile() {
    if (running.current) return
    setRace(null)
    const r = simulateAll()
    const champ = r.win[104]
    setRes(r); setChampion(champ)
    setTally((t) => ({ ...t, [champ]: (t[champ] ?? 0) + 1 }))
    setRuns((x) => x + 1)
    setRolled(true); setRunId((x) => x + 1)
  }

  const Match = ({ n }: { n: number }) => {
    const m = byNum[n]
    const slot = (which: 1 | 2) => {
      const team = resolveSlot(res, n, which)
      const decided = !!res.win[n]
      const isWin = decided && res.win[n] === team
      const isLose = decided && !isWin
      const goals = res.sc[n]?.[which - 1]
      return (
        <div className={cn('flex items-center gap-1 px-1.5 py-1 text-[11px] border-b border-line last:border-b-0 transition-colors',
          isWin && 'bg-home/15 text-home font-bold', isLose && 'opacity-40')}>
          {team ? <><Flag iso={iso[team] ?? 'un'} className="h-3 w-4" /><span className="min-w-0 truncate" title={team}>{disp(team)}</span>
            {goals != null && <span className="ml-auto pl-1 tnum">{goals}{m.pens && <span className="text-[9px] font-normal text-muted"> ({m.pens[which - 1]})</span>}</span>}</>
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

  // mobile game card — once rolled, holds its result hidden until it scrolls into view, then pops
  const MobileGame = ({ n }: { n: number }) => {
    const [ref, inView] = useInView<HTMLDivElement>()
    const m = byNum[n]
    const shown = !rolled || inView
    const row = (which: 1 | 2) => {
      const team = resolveSlot(res, n, which)
      const decided = shown && !!res.win[n]
      const isWin = decided && res.win[n] === team
      const isLose = decided && !isWin
      const goals = shown ? res.sc[n]?.[which - 1] : undefined
      return (
        <div className={cn('flex items-center gap-2.5 px-3 py-2.5 text-[13.5px] border-b border-line last:border-b-0 transition-colors duration-300',
          isWin && 'bg-home/15 text-home font-bold', isLose && 'opacity-40')}>
          {team ? <><Flag iso={iso[team] ?? 'un'} className="h-4 w-6" /><span className="min-w-0 truncate" title={team}>{disp(team)}</span>
            <span className={cn('ml-auto pl-2 font-display text-base tnum transition-all duration-300', goals != null ? 'opacity-100' : 'opacity-0')}>{goals ?? '0'}{shown && m.pens && <span className="text-[11px] font-normal text-muted"> ({m.pens[which - 1]})</span>}</span></>
            : <span className="italic text-muted">{(which === 1 ? m.team1 : m.team2).placeholder}</span>}
        </div>
      )
    }
    return (
      <div ref={ref} className={cn('overflow-hidden rounded-xl border bg-card transition-all duration-300',
        shown && !!res.win[n] ? 'border-line' : 'border-line/60', n >= 103 && 'ring-1 ring-brand/30')}>
        {row(1)}{row(2)}
      </div>
    )
  }

  const MobileChampion = ({ team }: { team: string }) => {
    const [ref, inView] = useInView<HTMLDivElement>('0px 0px -8% 0px')
    return (
      <div ref={ref} className={cn('mt-1 rounded-2xl border border-brand/40 bg-gradient-to-b from-brand/15 to-transparent p-6 text-center transition-all duration-500',
        inView ? 'translate-y-0 opacity-100' : 'translate-y-5 opacity-0')}>
        <Trophy className="mx-auto h-12 w-12 text-brand" />
        <Flag iso={iso[team] ?? 'un'} className="mx-auto mt-3 h-12 w-16" />
        <div className="mt-3 font-display text-3xl font-bold">{team}</div>
        <div className="mt-1 text-[11px] uppercase tracking-[0.25em] text-brand">World Champions</div>
      </div>
    )
  }

  const tallyRows = Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 8)

  return (
    <div>
      <SectionTitle>Play the tournament — simulate the bracket to a champion</SectionTitle>
      <div className="mb-4 flex flex-wrap items-center gap-2 sm:gap-3">
        {/* mobile CTA: roll instantly, then reveal on scroll */}
        <button onClick={rollMobile} disabled={running.current}
          className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 font-display font-bold tracking-wide text-black transition hover:brightness-110 disabled:opacity-50 md:hidden">
          <Play className="h-4 w-4 fill-black" /> {rolled ? 'Re-roll' : 'Simulate'}
        </button>
        {/* desktop: animated play + instant */}
        <button onClick={() => play(false)} disabled={running.current}
          className="hidden items-center gap-2 rounded-lg bg-brand px-5 py-2.5 font-display font-bold tracking-wide text-black transition hover:brightness-110 disabled:opacity-50 md:inline-flex">
          <Play className="h-4 w-4 fill-black" /> Play simulation
        </button>
        <button onClick={() => play(true)} disabled={running.current}
          className="hidden items-center gap-2 rounded-lg border border-line bg-card2 px-5 py-2.5 font-display font-bold tracking-wide text-fg transition hover:border-[#36456b] hover:bg-card disabled:opacity-50 md:inline-flex">
          <Zap className="h-4 w-4" /> Instant
        </button>
        <button onClick={runRace} disabled={running.current}
          className="inline-flex items-center gap-2 rounded-lg border border-brand/40 bg-brand/10 px-5 py-2.5 font-display font-bold tracking-wide text-brand transition hover:border-brand hover:bg-brand/20 disabled:opacity-50">
          <BarChart3 className="h-4 w-4" /> Race 1000
        </button>
        <span className="hidden text-sm text-muted md:inline">
          {champion ? `Champion: ${champion}. Play again for a different roll.` : 'Each run samples every remaining match from the model.'}
        </span>
        <span className="w-full text-[12.5px] text-muted md:hidden">
          {rolled ? 'Scroll down to watch each game fill in ↓' : 'Tap Simulate, then scroll to watch the bracket unfold.'}
        </span>
      </div>

      {/* fun-level knob — drag up for more goals; applies to the next Play / Simulate */}
      <div className="mb-4 inline-flex items-center gap-3 rounded-lg border border-line bg-card2/40 px-3 py-2">
        <Knob value={fun} min={0.8} max={2.6} onChange={setFun} />
        <span className="font-display text-[11px] font-semibold uppercase tracking-wider text-muted">Fun level</span>
      </div>

      {race && <RaceChart race={race} step={step} iso={iso} />}

      {/* desktop champion banner (mobile gets the reveal at the bottom of the scroll) */}
      {champion && (
        <Card className="mb-4 hidden animate-pop border-brand/30 bg-gradient-to-b from-brand/10 to-transparent p-4 md:block">
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center">
            <Trophy className="h-9 w-9 text-brand" />
            <Flag iso={iso[champion] ?? 'un'} className="h-8 w-11" />
            <span className="font-display text-3xl font-bold">{champion}</span>
            <span className="text-[11px] uppercase tracking-[0.2em] text-brand">World Champions</span>
          </div>
        </Card>
      )}

      {/* desktop: two-sided tree */}
      <div className="hidden items-stretch gap-1 overflow-x-auto scroll-thin pb-2 md:flex" style={{ minHeight: 430 }}>
        <div className="flex flex-1 gap-1">{layout.left.map(([t, nums], i) => <Column key={'l' + i} title={t} nums={nums} />)}</div>
        <div className="flex w-[116px] shrink-0 flex-col justify-center px-1">
          <h4 className="mb-1 text-center font-display text-[10px] uppercase tracking-wider text-brand">Final</h4>
          <Match n={104} />
          {byNum[103] && <><div className="mt-3 mb-1 text-center text-[9px] uppercase tracking-wider text-muted">3rd place</div><Match n={103} /></>}
        </div>
        <div className="flex flex-1 gap-1">{layout.right.map(([t, nums], i) => <Column key={'r' + i} title={t} nums={nums} />)}</div>
      </div>

      {/* mobile: round-by-round reveal — games fill in as you scroll, champion at the bottom */}
      <div key={runId} className="space-y-6 md:hidden">
        {layout.mobile.filter(([, nums]) => nums.length).map(([title, nums]) => (
          <div key={title}>
            <h4 className="mb-2 font-display text-xs font-semibold uppercase tracking-wider text-brand">{title}</h4>
            <div className="space-y-2.5">{nums.map((n) => <MobileGame key={n} n={n} />)}</div>
          </div>
        ))}
        {rolled && champion && <MobileChampion team={champion} />}
      </div>

      {runs > 0 && (
        <div className="mt-4 text-[12.5px] text-muted">
          <b className="text-fg">{runs}</b> simulation{runs > 1 ? 's' : ''} run — champions tally:
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {tallyRows.map(([t, c]) => (
              <Badge key={t}><Flag iso={iso[t] ?? 'un'} className="h-3 w-4" /> {disp(t)} <b className="text-brand">{c}</b></Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// machine-style knob: tap or drag AROUND it — the pointer angle sets the value
// (works the same with mouse or touch). Bottom 90° is the dead zone between min/max.
function Knob({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (v: number) => void }) {
  const dragging = useRef(false)
  const A0 = -135, A1 = 135, cx = 22, cy = 22, R = 17
  const ang = A0 + ((value - min) / (max - min)) * (A1 - A0)
  const pt = (a: number, r: number): [number, number] => {
    const t = (a - 90) * Math.PI / 180
    return [cx + r * Math.cos(t), cy + r * Math.sin(t)]
  }
  const arc = (a0: number, a1: number) => {
    const [x0, y0] = pt(a0, R), [x1, y1] = pt(a1, R)
    return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`
  }
  const set = (v: number) => onChange(Math.min(max, Math.max(min, v)))
  const fromPointer = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const a = Math.atan2(e.clientX - (r.left + r.width / 2), (r.top + r.height / 2) - e.clientY) * 180 / Math.PI
    set(a >= A1 ? max : a <= A0 ? min : min + ((a - A0) / (A1 - A0)) * (max - min)) // clamp the bottom gap to the nearest end
  }
  const [nx, ny] = pt(ang, R - 3)
  const step = (max - min) / 18
  return (
    <svg viewBox="0 0 44 44" width={44} height={44} role="slider" tabIndex={0}
      aria-label="Fun level" aria-valuemin={min} aria-valuemax={max} aria-valuenow={+value.toFixed(2)}
      className="cursor-pointer touch-none select-none outline-none"
      onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); dragging.current = true; fromPointer(e) }}
      onPointerMove={(e) => { if (dragging.current) fromPointer(e) }}
      onPointerUp={() => { dragging.current = false }}
      onPointerCancel={() => { dragging.current = false }}
      onKeyDown={(e) => { if (e.key === 'ArrowUp' || e.key === 'ArrowRight') set(value + step); if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') set(value - step) }}>
      <path d={arc(A0, A1)} fill="none" stroke="rgb(255 255 255 / 0.10)" strokeWidth={3} strokeLinecap="round" />
      <path d={arc(A0, ang)} fill="none" stroke="rgb(var(--brand))" strokeWidth={3} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={R - 5} fill="rgb(255 255 255 / 0.05)" stroke="rgb(255 255 255 / 0.08)" />
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="rgb(var(--brand))" strokeWidth={2.5} strokeLinecap="round" />
    </svg>
  )
}

function RaceChart({ race, step, iso }: { race: Race; step: number; iso: Record<string, string> }) {
  const W = 1000, H = 380, padL = 30, padR = 104, padT = 16, padB = 28
  const plotW = W - padL - padR, plotH = H - padT - padB
  const i = Math.min(step, RACE_N - 1)
  const x = (k: number) => padL + (k / (RACE_N - 1)) * plotW
  const y = (v: number) => padT + plotH - (v / race.max) * plotH

  // teams ordered by current standing — for the live leaderboard + tip stacking
  const ranked = [...race.teams].sort((a, b) => race.series[b][i] - race.series[a][i])
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * race.max))

  return (
    <Card className="mb-4 overflow-hidden p-4">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <div className="font-display text-sm font-bold uppercase tracking-wide text-fg">
          Race to 1000 — championships pile up
        </div>
        <div className="text-[12px] text-muted">
          sim <b className="tnum text-fg">{i + 1}</b> / {RACE_N} · leader{' '}
          <b className="text-brand">{ranked[0]}</b>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 'auto' }}>
        {ticks.map((t, k) => {
          const yy = y(t)
          return (
            <g key={k}>
              <line x1={padL} x2={padL + plotW} y1={yy} y2={yy} stroke="rgb(255 255 255 / 0.07)" />
              <text x={padL - 6} y={yy + 3} textAnchor="end" fontSize="11" fill="rgb(138 151 180 / 0.9)" className="tnum">{t}</text>
            </g>
          )
        })}
        {/* playhead */}
        <line x1={x(i)} x2={x(i)} y1={padT} y2={padT + plotH} stroke="rgb(255 255 255 / 0.10)" />
        {race.teams.map((t) => {
          const pts = race.pts[t].filter(([k]) => k <= i)
          const cur = race.series[t][i]
          const d = [...pts, [i, cur] as [number, number]]
            .map(([k, v], j) => `${j ? 'L' : 'M'}${x(k).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
          return <path key={t} d={d} fill="none" stroke={race.colors[t]} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" opacity={0.95} />
        })}
        {/* flag + count at each line tip */}
        {race.teams.map((t) => {
          const cur = race.series[t][i]
          return (
            <g key={t} transform={`translate(${x(i)}, ${y(cur)})`}>
              <image href={flagUrl(iso[t] ?? 'un')} x={6} y={-7} width={21} height={14} preserveAspectRatio="xMidYMid slice" />
              <text x={31} y={4} fontSize="13" fontWeight="700" fill={race.colors[t]} className="tnum">{cur}</text>
            </g>
          )
        })}
      </svg>
    </Card>
  )
}
