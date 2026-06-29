import { useEffect, useMemo, useState } from 'react'
import {
  Zap, ClipboardList, Gamepad2, Trophy, LayoutGrid, Users, Target, FlaskConical, ScrollText,
} from 'lucide-react'
import type {
  Accuracy, Benchmark, BracketMatch, HistoryRow, Meta, ModelZoo, Prediction, SquadTeam, Standings, TeamOdds,
} from '@/lib/types'
import { loadJSON, pct } from '@/lib/utils'
import { MatchCard } from '@/components/MatchCard'
import { Bracket } from '@/components/Bracket'
import { AccuracyView, HistoryView, ModelView, OddsView, SquadsView, StandingsView } from '@/components/Views'
import { Card, SectionTitle } from '@/components/ui'

interface Data {
  meta: Meta; predictions: Prediction[]; results: Prediction[]; championship: TeamOdds[]
  bracket: BracketMatch[]; standings: Standings; squads: SquadTeam[]; accuracy: Accuracy
  history: HistoryRow[]; benchmark: Benchmark; modelzoo: ModelZoo | null
}

const TABS = [
  { id: 'upcoming', label: 'Upcoming', Icon: Zap },
  { id: 'results', label: 'Results', Icon: ClipboardList },
  { id: 'simulate', label: 'Simulate', Icon: Gamepad2 },
  { id: 'odds', label: 'Odds & Bracket', Icon: Trophy },
  { id: 'groups', label: 'Groups', Icon: LayoutGrid },
  { id: 'squads', label: 'Squads', Icon: Users },
  { id: 'accuracy', label: 'Accuracy', Icon: Target },
  { id: 'model', label: 'Model', Icon: FlaskConical },
  { id: 'history', label: 'History', Icon: ScrollText },
] as const

export default function App() {
  const [data, setData] = useState<Data | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tab, setTab] = useState<string>('upcoming')

  useEffect(() => {
    const core = ['meta', 'predictions', 'results', 'championship', 'bracket', 'standings', 'squads', 'accuracy', 'history', 'benchmark']
    Promise.all([...core.map((n) => loadJSON<unknown>(n)), loadJSON<unknown>('modelzoo').catch(() => null)])
      .then(([meta, predictions, results, championship, bracket, standings, squads, accuracy, history, benchmark, modelzoo]) =>
        setData({ meta, predictions, results, championship, bracket, standings, squads, accuracy, history, benchmark, modelzoo } as unknown as Data))
      .catch((e) => setErr(String(e)))
  }, [])

  const upcoming = useMemo(
    () => data?.predictions.filter((p) => !p.played).sort((a, b) => a.date.localeCompare(b.date)) ?? [],
    [data],
  )

  if (err) return <Shell><Card className="mt-6 p-4 text-muted">Couldn't load data ({err}). If this is a fresh deploy, the pipeline may not have run yet.</Card></Shell>
  if (!data) return <Shell><div className="py-24 text-center text-muted">Loading predictions…</div></Shell>

  const { meta, accuracy, championship } = data
  const fav = championship[0]

  return (
    <Shell
      sub={`${meta.matches_played}/104 played · updated ${meta.updated_utc.replace('T', ' ').replace('Z', ' UTC')}`}
      kpis={
        <>
          <Kpi v={accuracy.rps ?? '–'} l="live RPS" good />
          <Kpi v={pct(accuracy.accuracy)} l="called" />
          <Kpi v={fav ? pct(fav.champion) : '–'} l={fav?.team ?? 'favourite'} />
        </>
      }
    >
      <nav className="flex gap-1.5 overflow-x-auto scroll-thin py-3">
        {TABS.map(({ id, label, Icon }) => (
          <button key={id} onClick={() => { setTab(id); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
            className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-2 text-[13px] font-semibold transition ${
              tab === id ? 'border-brand bg-brand text-black' : 'border-line bg-card text-muted hover:text-fg hover:border-[#36456b]'}`}>
            <Icon className="h-3.5 w-3.5" /> {label}
          </button>
        ))}
      </nav>

      <div className="animate-fade">
        {tab === 'upcoming' && (
          <>
            <SectionTitle>Next {upcoming.length} matches — model forecast</SectionTitle>
            <div className="space-y-3">{upcoming.map((m) => <MatchCard key={m.number} m={m} />)}</div>
          </>
        )}
        {tab === 'results' && (
          <>
            <SectionTitle>Recent results — predicted vs actual</SectionTitle>
            <div className="space-y-3">{data.results.map((m) => <MatchCard key={m.number} m={m} />)}</div>
          </>
        )}
        {tab === 'simulate' && <Bracket bracket={data.bracket} odds={championship} />}
        {tab === 'odds' && <OddsView odds={championship} />}
        {tab === 'groups' && <StandingsView standings={data.standings} />}
        {tab === 'squads' && <SquadsView squads={data.squads} />}
        {tab === 'accuracy' && <AccuracyView acc={accuracy} />}
        {tab === 'model' && <ModelView b={data.benchmark} zoo={data.modelzoo} />}
        {tab === 'history' && <HistoryView history={data.history} />}
      </div>
    </Shell>
  )
}

function Kpi({ v, l, good }: { v: React.ReactNode; l: string; good?: boolean }) {
  return (
    <div className="text-right">
      <div className={`font-display text-xl font-semibold leading-none tnum ${good ? 'text-home' : 'text-fg'}`}>{v}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted">{l}</div>
    </div>
  )
}

function Shell({ children, sub, kpis }: { children: React.ReactNode; sub?: string; kpis?: React.ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-20 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1080px] flex-wrap items-center gap-4 px-4 py-3">
          <div className="font-display text-2xl font-bold uppercase leading-none tracking-wide">
            World Cup <span className="text-brand">2026 Oracle</span>
            <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">{sub ?? 'loading…'}</div>
          </div>
          <div className="ml-auto flex gap-4">{kpis}</div>
        </div>
      </header>
      <main className="mx-auto max-w-[1080px] px-4 pb-24">{children}</main>
      <footer className="mx-auto max-w-[1080px] border-t border-line px-4 py-6 text-center text-[12px] text-muted">
        Elo → Dixon-Coles + gradient-boosting ensemble · Monte-Carlo bracket. Data:{' '}
        <a className="underline" href="https://github.com/martj42/international_results">martj42</a> ·{' '}
        <a className="underline" href="https://github.com/openfootball/worldcup.json">openfootball</a> ·{' '}
        <a className="underline" href="https://open-meteo.com">Open-Meteo</a> (free / public-domain).
        Probabilistic and for fun — not betting advice.
      </footer>
    </>
  )
}
