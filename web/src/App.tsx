import { useEffect, useMemo, useState } from 'react'
import {
  Zap, ClipboardList, Gamepad2, Trophy, LayoutGrid, Users, Target, FlaskConical, ScrollText, Menu, X,
} from 'lucide-react'
import type {
  Accuracy, Benchmark, BracketMatch, GoalBench, HistoryRow, Meta, ModelZoo, OddsProof, Prediction, SquadTeam, Standings, TeamOdds,
} from '@/lib/types'
import { loadJSON, pct } from '@/lib/utils'
import { MatchCard } from '@/components/MatchCard'
import { Bracket } from '@/components/Bracket'
import { AccuracyView, HistoryView, ModelView, OddsView, SquadsView, StandingsView } from '@/components/Views'
import { Card, SectionTitle } from '@/components/ui'

interface Data {
  meta: Meta; predictions: Prediction[]; results: Prediction[]; championship: TeamOdds[]
  bracket: BracketMatch[]; standings: Standings; squads: SquadTeam[]; accuracy: Accuracy
  history: HistoryRow[]; benchmark: Benchmark; modelzoo: ModelZoo | null; oddsProof: OddsProof | null
  goalbench: GoalBench | null
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
    Promise.all([...core.map((n) => loadJSON<unknown>(n)),
                 loadJSON<unknown>('modelzoo').catch(() => null),
                 loadJSON<unknown>('odds_proof').catch(() => null),
                 loadJSON<unknown>('goalbench').catch(() => null)])
      .then(([meta, predictions, results, championship, bracket, standings, squads, accuracy, history, benchmark, modelzoo, oddsProof, goalbench]) =>
        setData({ meta, predictions, results, championship, bracket, standings, squads, accuracy, history, benchmark, modelzoo, oddsProof, goalbench } as unknown as Data))
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
      tabs={TABS} activeTab={tab} onSelect={setTab}
    >

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
        {tab === 'model' && <ModelView b={data.benchmark} zoo={data.modelzoo} odds={data.oddsProof} goals={data.goalbench} />}
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

type Tab = { id: string; label: string; Icon: React.ComponentType<{ className?: string }> }
function Shell({ children, sub, kpis, tabs, activeTab, onSelect }: {
  children: React.ReactNode; sub?: string; kpis?: React.ReactNode
  tabs?: readonly Tab[]; activeTab?: string; onSelect?: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const pick = (id: string) => { onSelect?.(id); setOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-bg/80 backdrop-blur-md">
        <div className="mx-auto max-w-[1080px] px-4">
          <div className="flex items-center gap-3 py-3">
            {tabs && (
              <button onClick={() => setOpen((o) => !o)} aria-label="Menu"
                className="-ml-1 rounded-lg p-2 text-muted transition-colors hover:text-fg md:hidden">
                {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </button>
            )}
            <div className="font-display text-xl font-bold uppercase leading-none tracking-wide md:text-2xl">
              World Cup <span className="text-brand">2026 Oracle</span>
              <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted md:text-[11px]">{sub ?? 'loading…'}</div>
            </div>
            <div className="ml-auto hidden gap-4 sm:flex">{kpis}</div>
          </div>
          {tabs && (
            <nav className="-mb-px hidden gap-1 md:flex">
              {tabs.map(({ id, label, Icon }) => (
                <button key={id} onClick={() => pick(id)}
                  className={`group flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-2.5 text-[13px] font-semibold transition-colors ${
                    activeTab === id ? 'border-brand text-fg' : 'border-transparent text-muted hover:border-line hover:text-fg'}`}>
                  <Icon className={`h-4 w-4 transition-colors ${activeTab === id ? 'text-brand' : 'text-muted group-hover:text-fg'}`} />
                  {label}
                </button>
              ))}
            </nav>
          )}
          {tabs && open && (
            <nav className="grid grid-cols-2 gap-1 pb-3 md:hidden">
              {tabs.map(({ id, label, Icon }) => (
                <button key={id} onClick={() => pick(id)}
                  className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
                    activeTab === id ? 'bg-brand/15 text-brand' : 'text-muted hover:bg-card2 hover:text-fg'}`}>
                  <Icon className="h-4 w-4 shrink-0" /> {label}
                </button>
              ))}
            </nav>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-[1080px] px-4 pb-24 pt-5">{children}</main>
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
